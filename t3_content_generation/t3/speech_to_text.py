import os

import requests

from commons.constants import OPENAI_API_KEY, OPENAI_HOST


# https://developers.openai.com/api/docs/guides/speech-to-text

AUDIO_PATH = os.path.join(os.path.dirname(__file__), "audio_sample.mp3")
MODELS = ["whisper-1", "gpt-4o-transcribe"]

if not OPENAI_API_KEY:
    raise ValueError("API key cannot be null or empty")


def transcribe(model: str) -> str:
    with open(AUDIO_PATH, "rb") as audio_file:
        # multipart/form-data: the file goes to `files`, plain fields to `data`
        response = requests.post(
            url=f"{OPENAI_HOST}/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            files={"file": ("audio_sample.mp3", audio_file, "audio/mpeg")},
            data={"model": model},
        )
    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}: {response.text}")
    return response.json()["text"]


# Compare both models on the same audio
for model_name in MODELS:
    print(f"\n=== {model_name} ===")
    print(transcribe(model_name))
