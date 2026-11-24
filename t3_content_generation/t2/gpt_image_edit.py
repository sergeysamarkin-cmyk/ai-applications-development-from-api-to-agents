import base64
import os
from datetime import datetime

import requests

from commons.constants import OPENAI_API_KEY, OPENAI_HOST


# https://developers.openai.com/api/reference/resources/images/methods/edit
# ---
# Request (multipart/form-data, NOT json):
# curl -X POST "https://api.openai.com/v1/images/edits" \
#     -H "Authorization: Bearer $OPENAI_API_KEY" \
#     -F "model=gpt-image-1" \
#     -F "image=@logo.png" \
#     -F "prompt=Add magical sparkles and glowing aura around the logo"
# Response:
# {
#   "created": 1699900000,
#   "data": [
#     {
#       "b64_json": "Qt0n6ArYAEABGOhEoYgVAJFdt8jM79uW2DO..."
#     }
#   ]
# }

LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo.png")
PROMPT = "Add magical sparkles, a glowing mystical aura and floating light particles around the logo"

if not OPENAI_API_KEY:
    raise ValueError("API key cannot be null or empty")

with open(LOGO_PATH, "rb") as logo_file:
    # No "Content-Type" header: requests sets multipart/form-data with the right boundary itself
    response = requests.post(
        url=f"{OPENAI_HOST}/v1/images/edits",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        files={"image": ("logo.png", logo_file, "image/png")},
        data={"model": "gpt-image-2", "prompt": PROMPT},
    )

if response.status_code != 200:
    raise Exception(f"HTTP {response.status_code}: {response.text}")

image_bytes = base64.b64decode(response.json()["data"][0]["b64_json"])
file_name = os.path.join(os.path.dirname(__file__), f"logo_edited_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
with open(file_name, "wb") as image_file:
    image_file.write(image_bytes)

print(f"Edited image saved to: {file_name}")
