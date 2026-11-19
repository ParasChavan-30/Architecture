# CAPTCHA Solver — Microservice & CLI

A dual-mode CAPTCHA solver using the `ddddocr` OCR engine:
1. **HTTP REST API (FastAPI / Uvicorn)** — for Railway, Docker, and Cloudflare Worker integration.
2. **CLI Utility** — for local command-line tests and scripts.

---

## 1. Installation

```bash
pip install -r requirements.txt
```

---

## 2. Running as Web API (Railway / Docker / Local)

```bash
# Direct Python:
python captcha_solver.py

# Or via Uvicorn:
uvicorn captcha_solver:app --host 0.0.0.0 --port 8000
```

### Endpoints

#### Health Check
```http
GET /health
```
Response:
```json
{"status": "ok", "service": "ddddocr-captcha-solver", "version": "1.0.0"}
```

#### Solve CAPTCHA
```http
POST /solve
Content-Type: application/json

{
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```
Response (Success):
```json
{
  "success": true,
  "captcha_text": "Ab3Xy5",
  "time_ms": 42
}
```
Response (Failure):
```json
{
  "success": false,
  "error": "OCR failed to solve captcha",
  "time_ms": 110
}
```

---

## 3. Running as CLI Tool

```bash
# From file:
python captcha_solver.py --file captcha.png

# From base64 string:
python captcha_solver.py --base64 "iVBORw0KGgo..."

# From stdin:
cat captcha.png | python captcha_solver.py --stdin
```

---

## 4. Railway Deployment

1. Push this folder to a GitHub repository.
2. On Railway (`railway.com`), click **New Project** -> **Deploy from GitHub repo**.
3. In service **Settings** -> **Networking**, click **Generate Domain**.
4. Set the domain in your Cloudflare Worker `wrangler.toml`:
   ```toml
   CAPTCHA_SOLVER_URL = "https://your-railway-domain.up.railway.app/solve"
   ```
