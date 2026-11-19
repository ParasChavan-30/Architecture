"""
captcha_solver.py — CAPTCHA solver using ddddocr OCR engine.

Dual Mode:
1. Web API Mode (FastAPI):
   - Starts HTTP server on $PORT (default 8000) for Railway / cloud deployment.
   - Accepts POST /solve with {"image_base64": "..."}.
   - Returns {"success": true, "captcha_text": "...", "time_ms": ...}.
   - Health check on GET /health and GET /.

2. CLI Mode:
   - python captcha_solver.py --file captcha.png
   - python captcha_solver.py --base64 "iVBORw0KGgo..."
   - cat captcha.png | python captcha_solver.py --stdin
"""

import os
import sys
import types
import io
import re
import json
import argparse
import base64
import time
import threading
import numpy as np
from PIL import Image
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# CV2 Stub (PIL-based) — avoids needing OpenCV C++ binaries on Linux / Windows
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
# OCR Engine (Cached singleton for fast sub-50ms inference)
# ─────────────────────────────────────────────────────────────────────────────
_ocr = None
_ocr_lock = threading.Lock()


def get_ocr_instance():
    """Lazy-load and cache the ddddocr model to avoid reloading on each request."""
    global _ocr
    if _ocr is None:
        with _ocr_lock:
            if _ocr is None:
                _ocr = ddddocr.DdddOcr(show_ad=False)
    return _ocr


def solve_captcha(image_bytes: bytes) -> Optional[str]:
    """
    Solve a CAPTCHA image using ddddocr.

    Returns the solved text string, or None on failure.
    """
    if not image_bytes:
        return None

    # Pre-validate that bytes form a readable image to protect OCR engine from corrupt payloads
    try:
        with Image.open(io.BytesIO(image_bytes)) as test_img:
            test_img.verify()
    except Exception:
        return None

    try:
        ocr = get_ocr_instance()
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

        # Return raw result even if it doesn't match the exact pattern
        return answer if answer else None

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}), file=sys.stderr)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Web Server (Exposed for Uvicorn & Railway)
# ─────────────────────────────────────────────────────────────────────────────
try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel

    app = FastAPI(
        title="COA CAPTCHA Solver API",
        description="High-speed ddddocr CAPTCHA solver microservice",
        version="1.0.0"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class SolvePayload(BaseModel):
        image_base64: Optional[str] = None
        base64: Optional[str] = None
        image: Optional[str] = None

    @app.get("/")
    @app.get("/health")
    def health_check():
        return {
            "status": "ok",
            "service": "ddddocr-captcha-solver",
            "version": "1.0.0"
        }

    @app.post("/solve")
    @app.post("/")
    def solve_api(payload: SolvePayload):
        start = time.time()
        raw_b64 = payload.image_base64 or payload.base64 or payload.image

        if not raw_b64:
            elapsed_ms = round((time.time() - start) * 1000)
            return {
                "success": False,
                "error": "Missing 'image_base64' in JSON request body",
                "time_ms": elapsed_ms
            }

        # Strip Data URL header if present (e.g. data:image/png;base64,...)
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]

        try:
            image_bytes = base64.b64decode(raw_b64)
        except Exception as e:
            elapsed_ms = round((time.time() - start) * 1000)
            return {
                "success": False,
                "error": f"Invalid base64 string: {str(e)}",
                "time_ms": elapsed_ms
            }

        text = solve_captcha(image_bytes)
        elapsed_ms = round((time.time() - start) * 1000)

        if text:
            return {
                "success": True,
                "captcha_text": text,
                "time_ms": elapsed_ms
            }
        else:
            return {
                "success": False,
                "error": "OCR failed to solve captcha",
                "time_ms": elapsed_ms
            }

except ImportError:
    app = None


# ─────────────────────────────────────────────────────────────────────────────
# CLI & Server Runner Entry Point
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Solve a CAPTCHA image using ddddocr OCR engine (CLI or FastAPI Server)"
    )

    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--file", type=str, help="Path to the captcha image file")
    group.add_argument("--base64", type=str, help="Base64-encoded image string")
    group.add_argument("--stdin", action="store_true", help="Read image bytes from stdin")
    group.add_argument("--server", action="store_true", help="Start the FastAPI web server")
    parser.add_argument("--port", type=int, default=None, help="Port to listen on (defaults to PORT env or 8000)")

    args = parser.parse_args()

    # If any CLI argument is provided for solving, execute CLI mode
    if args.file or args.base64 or args.stdin:
        start = time.time()
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
                clean_b64 = args.base64.split(",", 1)[1] if "," in args.base64 else args.base64
                image_bytes = base64.b64decode(clean_b64)
            except Exception as e:
                print(json.dumps({"success": False, "error": f"Invalid base64: {e}"}))
                sys.exit(1)

        elif args.stdin:
            image_bytes = sys.stdin.buffer.read()

        if not image_bytes:
            print(json.dumps({"success": False, "error": "No image data received"}))
            sys.exit(1)

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
        return

    # No CLI solving flags provided -> Launch FastAPI Web Server (Railway default)
    if app is None:
        print("Error: FastAPI/Uvicorn not installed. Please run: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)

    port = args.port or int(os.environ.get("PORT", 8000))
    print(f"[*] Starting COA CAPTCHA Solver API on http://0.0.0.0:{port}")
    import uvicorn
    uvicorn.run("captcha_solver:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
