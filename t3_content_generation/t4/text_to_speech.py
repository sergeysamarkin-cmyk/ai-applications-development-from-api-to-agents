import os
from datetime import datetime

import requests

from commons.constants import OPENAI_API_KEY, OPENAI_HOST


class Voice:
    alloy: str = 'alloy'
    ash: str = 'ash'
    ballad: str = 'ballad'
    coral: str = 'coral'
    echo: str = 'echo'
    fable: str = 'fable'
    nova: str = 'nova'
    onyx: str = 'onyx'
    sage: str = 'sage'
    shimmer: str = 'shimmer'


# https://developers.openai.com/api/docs/guides/text-to-speech
# Request:
# curl https://api.openai.com/v1/audio/speech \
#   -H "Authorization: Bearer $OPENAI_API_KEY" \
#   -H "Content-Type: application/json" \
#   -d '{
#     "model": "gpt-4o-mini-tts",
#     "input": "Why can't we say that black is white?",
#     "voice": "coral",
#     "instructions": "Speak in a cheerful and positive tone."
#   }' \
# Response:
#   bytes with audio

TEXT = "Why can't we say that black is white?"
INSTRUCTIONS = "Speak in a cheerful and positive tone."
# Try several voices with the same text and speaking style
VOICES = [Voice.coral, Voice.nova, Voice.onyx]

if not OPENAI_API_KEY:
    raise ValueError("API key cannot be null or empty")


def text_to_speech(text: str, voice: str, instructions: str) -> str:
    response = requests.post(
        url=f"{OPENAI_HOST}/v1/audio/speech",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-4o-mini-tts",
            "input": text,
            "voice": voice,
            "instructions": instructions,
            "response_format": "mp3",
        },
    )
    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}: {response.text}")

    # The response body is the raw audio, not JSON
    file_name = os.path.join(
        os.path.dirname(__file__), f"speech_{voice}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
    )
    with open(file_name, "wb") as audio_file:
        audio_file.write(response.content)
    return file_name


for voice_name in VOICES:
    print(f"Voice '{voice_name}' saved to: {text_to_speech(TEXT, voice_name, INSTRUCTIONS)}")

