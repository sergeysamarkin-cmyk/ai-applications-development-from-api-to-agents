import base64
import os
from datetime import datetime

from commons.constants import OPENAI_HOST
from t3_content_generation._openai_client import OpenAIClientT3


# https://developers.openai.com/api/reference/resources/images/methods/generate
# ---
# Request:
# curl -X POST "https://api.openai.com/v1/images/generations" \
#     -H "Authorization: Bearer $OPENAI_API_KEY" \
#     -H "Content-type: application/json" \
#     -d '{
#         "model": "gpt-image-2",
#         "prompt": "smiling catdog."
#     }'
# Response:
# {
#   "created": 1699900000,
#   "data": [
#     {
#       "b64_json": Qt0n6ArYAEABGOhEoYgVAJFdt8jM79uW2DO...,
#     }
#   ]
# }

client = OpenAIClientT3(endpoint=f"{OPENAI_HOST}/v1/images/generations")

# print_response=False: the response contains a huge base64 string
response = client.call(
    print_response=False,
    model="gpt-image-2",
    prompt="Smiling catdog",
)

image_bytes = base64.b64decode(response["data"][0]["b64_json"])
file_name = os.path.join(os.path.dirname(__file__), f"catdog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
with open(file_name, "wb") as image_file:
    image_file.write(image_bytes)

print(f"Image saved to: {file_name}")
