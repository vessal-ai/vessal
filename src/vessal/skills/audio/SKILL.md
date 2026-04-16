---
name: audio
description: Audio to text transcription
---

## Audio to Text

audio.transcribe(file_path)

Transcribes an audio file to text, returning the transcribed string.

Example:
text = audio.transcribe("/path/to/recording.mp3")
print(text)

## Supported Formats

wav, mp3

## Limits

- File size ≤ 25MB
- Audio duration ≤ 30 seconds

## Environment Variables

- `API_302AI_KEY` — 302AI API key (required)

## Notes

Requires the environment variable API_302AI_KEY. Calls will fail if it is not set.
