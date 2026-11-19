"""
captcha_solver.py — CLI CAPTCHA solver using ddddocr OCR engine.

Usage:
    # Solve from a file path
    python captcha_solver.py --file captcha.png

    # Solve from base64 string
    python captcha_solver.py --base64 "iVBORw0KGgo..."

    # Solve from stdin (pipe image bytes)
    cat captcha.png | python captcha_solver.py --stdin

Output:
    Prints JSON to stdout:
    {"success": true, "captcha_text": "Ab3Xy5"}
"""

import sys
import types
import io
import re
import json
import argparse
import base64
import time
import numpy as np
from PIL import Image
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# CV2 Stub (PIL-based) — avoids needing OpenCV C++ binaries
# ─────────────────────────────────────────────────────────────────────────────
if "cv2" not in sys.modules:
    try:
        import cv2
    except ImportError:
        fake_cv2 = types.ModuleType("cv2")

        def _imdecode(buf, flags):
            img = Image.open(io.BytesIO(buf))
            return np.array(img)

        def _cvtColor(src, code):
            if len(src.shape) == 3 and src.shape[2] == 3:
                return np.dot(src[..., :3], [0.2989, 0.5870, 0.1140]).astype(np.uint8)
            return src

        def _resize(src, dsize, fx=0, fy=0, interpolation=None):
            img = Image.fromarray(src)
            w, h = dsize
            if w == 0 or h == 0:
                w = int(src.shape[1] * fx)
                h = int(src.shape[0] * fy)
            res = img.resize((w, h), Image.Resampling.BILINEAR)
            return np.array(res)

        def _threshold(src, thresh, maxval, type):
            res = (src > thresh).astype(np.uint8) * maxval
            return thresh, res

        fake_cv2.imdecode = _imdecode
        fake_cv2.cvtColor = _cvtColor
        fake_cv2.resize = _resize
        fake_cv2.threshold = _threshold
        fake_cv2.COLOR_BGR2GRAY = 6
        fake_cv2.COLOR_RGB2GRAY = 7
        fake_cv2.INTER_AREA = 3
        fake_cv2.INTER_LINEAR = 1
        fake_cv2.THRESH_BINARY = 0

        sys.modules["cv2"] = fake_cv2

import ddddocr


# ─────────────────────────────────────────────────────────────────────────────
# OCR Engine
# ─────────────────────────────────────────────────────────────────────────────

def solve_captcha(image_bytes: bytes) -> Optional[str]:
    """
    Solve a CAPTCHA image using ddddocr.

    Returns the solved text string, or None on failure.
    """
    if not image_bytes:
        return None

    try:
        ocr = ddddocr.DdddOcr(show_ad=False)
        result = ocr.classification(image_bytes)

        if not result:
            return None

        answer = result.strip()

        # Validate: 5-6 alphanumeric characters (COA pattern)
        if re.fullmatch(r"[A-Za-z0-9]{5,6}", answer):
            return answer

        # Try to extract a valid substring
        matches = re.findall(r"[A-Za-z0-9]{5,6}", answer)
        if matches:
            return matches[0]

        # Return raw result even if it doesn't match the pattern
        return answer if answer else None

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}), file=sys.stderr)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# CLI Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Solve a CAPTCHA image using ddddocr OCR engine (CLI tool)"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=str, help="Path to the captcha image file")
    group.add_argument("--base64", type=str, help="Base64-encoded image string")
    group.add_argument("--stdin", action="store_true", help="Read image bytes from stdin")

    args = parser.parse_args()

    start = time.time()

    # Read image bytes from the chosen source
    image_bytes = None

    if args.file:
        try:
            with open(args.file, "rb") as f:
                image_bytes = f.read()
        except FileNotFoundError:
            print(json.dumps({"success": False, "error": f"File not found: {args.file}"}))
            sys.exit(1)
        except IOError as e:
            print(json.dumps({"success": False, "error": str(e)}))
            sys.exit(1)

    elif args.base64:
        try:
            image_bytes = base64.b64decode(args.base64)
        except Exception as e:
            print(json.dumps({"success": False, "error": f"Invalid base64: {e}"}))
            sys.exit(1)

    elif args.stdin:
        image_bytes = sys.stdin.buffer.read()

    if not image_bytes:
        print(json.dumps({"success": False, "error": "No image data received"}))
        sys.exit(1)

    # Solve
    result = solve_captcha(image_bytes)
    elapsed_ms = round((time.time() - start) * 1000)

    if result:
        print(json.dumps({
            "success": True,
            "captcha_text": result,
            "time_ms": elapsed_ms
        }))
    else:
        print(json.dumps({
            "success": False,
            "error": "OCR failed to solve captcha",
            "time_ms": elapsed_ms
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
