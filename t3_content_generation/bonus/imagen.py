import base64
import os
from datetime import datetime

import requests

from commons.constants import GEMINI_API_KEY, GEMINI_ENDPOINT

# https://ai.google.dev/gemini-api/docs/imagen
# All generated images include a SynthID watermark

MODELS = ["imagen-4.0-generate-001", "imagen-4.0-fast-generate-001", "imagen-4.0-ultra-generate-001"]
PROMPT = "Smiling catdog"

if not GEMINI_API_KEY:
    raise ValueError("API key cannot be null or empty")


def generate(model: str) -> list[str]:
    response = requests.post(
        url=f"{GEMINI_ENDPOINT}/{model}:predict",
        headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
        json={
            "instances": [{"prompt": PROMPT}],
            # REST name of the SDK's `numberOfImages` is `sampleCount`
            "parameters": {"sampleCount": 1, "aspectRatio": "1:1"},
        },
    )
    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}: {response.text[:400]}")

    files = []
    for i, prediction in enumerate(response.json().get("predictions", [])):
        file_name = os.path.join(
            os.path.dirname(__file__), f"{model}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}.png"
        )
        with open(file_name, "wb") as image_file:
            image_file.write(base64.b64decode(prediction["bytesBase64Encoded"]))
        files.append(file_name)
    return files


for model_name in MODELS:
    try:
        print(f"{model_name}: saved {generate(model_name)}")
    except Exception as e:
        print(f"{model_name}: ERROR {e}")
