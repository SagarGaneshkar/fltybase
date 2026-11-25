"""Optional BLIP image-captioning demo, separate from the main pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any


_CAPTIONER: Any = None


def caption_images(image_paths: list[str | Path]) -> list[tuple[str, str]]:
    """Caption local images using BLIP; install transformers and torch separately."""
    global _CAPTIONER
    try:
        from transformers import pipeline
    except ImportError as error:
        raise RuntimeError(
            "The optional caption demo needs transformers and torch. "
            "Install them separately before running `python main.py caption ...`."
        ) from error

    if _CAPTIONER is None:
        _CAPTIONER = pipeline(
            "image-to-text",
            model="Salesforce/blip-image-captioning-base",
        )
    results = []
    for image_path in image_paths:
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Image does not exist: {path}")
        prediction = _CAPTIONER(str(path))
        results.append((str(path), prediction[0]["generated_text"]))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Optional BLIP demo for three to five local sample images."
    )
    parser.add_argument("images", nargs="+", help="Three to five image paths")
    args = parser.parse_args()
    if not 3 <= len(args.images) <= 5:
        parser.error("provide between three and five image paths")
    for image_path, caption in caption_images(args.images):
        print(f"{image_path}: {caption}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
