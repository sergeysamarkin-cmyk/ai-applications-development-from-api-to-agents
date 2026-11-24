import base64
import os

from commons.constants import OPENAI_HOST, OPENAI_TERRA_MODEL
from t3_content_generation._openai_client import OpenAIClientT3


# https://developers.openai.com/api/docs/guides/images-vision?format=url&lang=curl
# https://developers.openai.com/api/docs/guides/images-vision?format=base64-encoded

IMAGE_URL = "https://a-z-animals.com/media/2019/11/Elephant-male-1024x535.jpg"
LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo.png")


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


client = OpenAIClientT3(endpoint=f"{OPENAI_HOST}/v1/chat/completions")

# print_request/print_response are off: the request contains the whole base64-encoded logo
response = client.call(
    print_request=False,
    print_response=False,
    model=OPENAI_TERRA_MODEL,
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Generate poem based on images"},
                # Image by URL
                {"type": "image_url", "image_url": {"url": IMAGE_URL}},
                # Local image, sent as a base64 data URL
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encode_image(LOGO_PATH)}"}},
            ],
        }
    ],
)

print("\n" + "=" * 30 + " MODEL ANSWER " + "=" * 30)
print(response["choices"][0]["message"]["content"])
