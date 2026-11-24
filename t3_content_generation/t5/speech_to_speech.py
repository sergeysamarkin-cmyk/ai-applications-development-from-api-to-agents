import base64
import os
from datetime import datetime

import requests

from commons.constants import OPENAI_API_KEY, OPENAI_HOST


# https://developers.openai.com/api/docs/guides/audio#add-audio-to-your-existing-application

QUESTION_PATH = os.path.join(os.path.dirname(__file__), "question.mp3")

if not OPENAI_API_KEY:
    raise ValueError("API key cannot be null or empty")


def encode_audio(audio_path: str) -> str:
    with open(audio_path, "rb") as audio_file:
        return base64.b64encode(audio_file.read()).decode("utf-8")


response = requests.post(
    url=f"{OPENAI_HOST}/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    },
    json={
        "model": "gpt-4o-audio-preview",
        "modalities": ["text", "audio"],
        "audio": {"voice": "ballad", "format": "mp3"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "input_audio", "input_audio": {"data": encode_audio(QUESTION_PATH), "format": "mp3"}}
                ],
            }
        ],
    },
)

if response.status_code != 200:
    raise Exception(f"HTTP {response.status_code}: {response.text}")

# The answer is in message.audio (base64), not in message.content
audio = response.json()["choices"][0]["message"]["audio"]
print("Transcript of the answer:", audio.get("transcript"))

file_name = os.path.join(os.path.dirname(__file__), f"answer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3")
with open(file_name, "wb") as audio_file:
    audio_file.write(base64.b64decode(audio["data"]))

print(f"Audio answer saved to: {file_name}")
