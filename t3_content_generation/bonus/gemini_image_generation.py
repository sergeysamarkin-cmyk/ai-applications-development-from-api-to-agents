import base64
import os
from datetime import datetime

import requests

from commons.constants import GEMINI_API_KEY, GEMINI_ENDPOINT

# https://ai.google.dev/gemini-api/docs/image-generation
# Gemini native image generation: the response contains interleaved text and inline image data (base64)

MODEL = "gemini-2.5-flash-image"
PROMPT = "Smiling catdog"

if not GEMINI_API_KEY:
    raise ValueError("API key cannot be null or empty")

response = requests.post(
    url=f"{GEMINI_ENDPOINT}/{MODEL}:generateContent",
    headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
    json={
        "contents": [{"role": "user", "parts": [{"text": PROMPT}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    },
)
if response.status_code != 200:
    raise Exception(f"HTTP {response.status_code}: {response.text}")

parts = response.json()["candidates"][0]["content"]["parts"]
saved = 0
for part in parts:
    if "text" in part:
        print("Text part:", part["text"])
    # The REST API returns camelCase `inlineData`
    inline = part.get("inlineData") or part.get("inline_data")
    if inline:
        file_name = os.path.join(
            os.path.dirname(__file__), f"gemini_catdog_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{saved}.png"
        )
        with open(file_name, "wb") as image_file:
            image_file.write(base64.b64decode(inline["data"]))
        print(f"Image saved to: {file_name} ({inline.get('mimeType')})")
        saved += 1

if not saved:
    raise ValueError("No image in the response")
