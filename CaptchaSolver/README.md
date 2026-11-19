# CAPTCHA Solver — CLI Tool

A standalone CLI Python script that solves CAPTCHA images using `ddddocr` OCR.  
**No server, no API framework.** Just call it, it solves, it prints JSON and exits.

## Install

```bash
pip install -r requirements.txt
```

## Usage

### From a file
```bash
python captcha_solver.py --file captcha.png
```

### From base64 string
```bash
python captcha_solver.py --base64 "iVBORw0KGgo..."
```

### From stdin (pipe)
```bash
cat captcha.png | python captcha_solver.py --stdin
```

## Output

Always prints JSON to stdout:

```json
{"success": true, "captcha_text": "Ab3Xy5", "time_ms": 45}
```

On failure:
```json
{"success": false, "error": "OCR failed to solve captcha", "time_ms": 120}
```

## Calling from other languages

### From PHP
```php
$image_base64 = base64_encode(file_get_contents('captcha.png'));
$cmd = "python captcha_solver.py --base64 " . escapeshellarg($image_base64);
$output = shell_exec($cmd);
$result = json_decode($output, true);
echo $result['captcha_text'];
```

### From Node.js
```js
const { execSync } = require('child_process');
const fs = require('fs');
const b64 = fs.readFileSync('captcha.png').toString('base64');
const result = JSON.parse(execSync(`python captcha_solver.py --base64 "${b64}"`).toString());
console.log(result.captcha_text);
```
