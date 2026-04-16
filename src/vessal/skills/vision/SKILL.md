---
name: vision
description: Image understanding
---

## Describe an Image

vision.describe(image_path)

Returns a text description of the image content.

Example:
text = vision.describe("/path/to/chart.png")
print(text)

## Ask a Question About an Image

vision.ask(image_path, question)

Ask a specific question about an image and return the answer.

Example:
answer = vision.ask("/path/to/figure.png", "What are the x-axis and y-axis of this chart?")
print(answer)

## Supported Formats

png, jpg, jpeg, gif, webp

Other formats (e.g. tiff, bmp) are sent as image/png. It is recommended to convert them to png/jpg first before calling.

## Notes

The image file must exist on the local filesystem. URLs are not supported; download the file locally and pass the path.

## Environment Variables

- `VISION_BASE_URL` — VL server address (default: `http://192.168.40.42:8001/v1`)
- `VISION_API_KEY` — API key (default: `sk-wx`)
