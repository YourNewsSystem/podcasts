import os
import requests
import random
import time
from datetime import datetime
from dotenv import load_dotenv
import base64

# Load .env in local, GitHub Actions will inject via secrets
load_dotenv()

GATEWAY_TOKEN = os.getenv("GATEWAY_TOKEN")
GH_TOKEN = os.getenv("GH_TOKEN")
GH_REPO = os.getenv("GH_REPO")
CATEGORY = os.getenv("CATEGORY", "sport")
BASE_URL = "https://yn.j-ai.ir/newsletter/latest"

# Step 1: Get podcast text
res = requests.get(f"{BASE_URL}/{CATEGORY}")
data = res.json()
podcast_text = data.get("podcast")

if not podcast_text:
    print("❌ No podcast text found.")
    exit(1)

# Step 2: Send to TTS
headers = {
    "gateway-token": GATEWAY_TOKEN,
    "Content-Type": "application/json"
}

speaker_id = random.randint(1, 4)
payload = {
    "data": podcast_text,
    "filePath": True,
    "base64": False,
    "checksum": False,
    "speaker": speaker_id
}

tts_response = requests.post(
    "https://partai.gw.isahab.ir/TextToSpeech/v1/speech-synthesys",
    headers=headers,
    json=payload
)

if tts_response.status_code != 200:
    print("❌ TTS Request failed:", tts_response.text)
    exit(1)

token = tts_response.json().get("token")
if not token:
    print("❌ No token received.")
    exit(1)

# Step 3: Wait until audio is ready
status_url = f"https://partai.gw.isahab.ir/TextToSpeech/v1/speech-response-check?token={token}"
print("⏳ Waiting for audio...")

audio_url = None
for _ in range(10):  # Retry for ~5 minutes
    time.sleep(30)
    check = requests.get(status_url, headers=headers)
    try:
        audio_url = check.json().get("data", {}).get("filePath")
        if audio_url:
            print("✅ Audio ready:", audio_url)
            break
    except Exception as e:
        print("⚠️ Retry failed:", e)

if not audio_url:
    print("❌ Timeout: Audio not ready.")
    exit(1)

# Step 4: Download audio
audio_res = requests.get(audio_url)
now = datetime.now()
year = now.strftime("%Y")
month = now.strftime("%m")
day = now.strftime("%d")
filename = f"{day}.mp3"
gh_path = f"files/{CATEGORY}/{year}/{month}/{filename}"
upload_url = f"https://api.github.com/repos/{GH_REPO}/contents/{gh_path}"

# Step 5: Upload to GitHub
encoded_content = base64.b64encode(audio_res.content).decode("utf-8")
commit_message = f"Add podcast for {year}-{month}-{day} ({CATEGORY})"

upload_response = requests.put(
    upload_url,
    headers={
        "Authorization": f"Bearer {GH_TOKEN}",
        "Content-Type": "application/json"
    },
    json={
        "message": commit_message,
        "content": encoded_content
    }
)

if upload_response.status_code in [200, 201]:
    print("🚀 File uploaded successfully:", gh_path)
else:
    print("❌ GitHub upload failed:", upload_response.text)
