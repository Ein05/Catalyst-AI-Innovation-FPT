# Real-Time Vietnamese-English Meeting Translator

Backend + frontend app for a real-time Vietnamese-English meeting translator.

- Backend: Python, FastAPI, WebSocket.
- Frontend: React, Vite, TypeScript, Tailwind.
- Stable public deploy for demo: Render for backend, Vercel for frontend.

Current demo mode uses `MockASRProvider` so the deployed app can run without heavy speech models. The real model wrappers are already in the repo and can be enabled later.

## Repository Layout

```text
apps/api/                  FastAPI backend
core/                      Backend core modules
config/                    YAML profiles
Fontend/translator-app/    React Vite frontend
requirements-render.txt    Lightweight backend deps for Render demo
render.yaml                Optional Render Blueprint config
```

## Local Backend

```powershell
cd D:\Work\HackerThonFpt
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-render.txt
python -m apps.api.main
```

Backend URL:

```text
http://127.0.0.1:8000
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

If port `8000` is busy:

```powershell
netstat -ano | Select-String ':8000'
Stop-Process -Id <PID_8000>
```

## Local Frontend

Open another terminal:

```powershell
cd D:\Work\HackerThonFpt\Fontend\translator-app
npm install
npm run dev -- --host 0.0.0.0
```

Frontend URL:

```text
http://127.0.0.1:5173
```

In local dev, Vite proxies:

- `/ws` to `ws://127.0.0.1:8000/ws`
- `/health` to `http://127.0.0.1:8000/health`
- `/debug` to `http://127.0.0.1:8000/debug`

## Deploy Backend To Render

Render is the backend host because it supports long-running FastAPI web services and public WebSocket connections. Render web services must bind to `0.0.0.0` and should use the `PORT` env var. This app already does that in `apps/api/main.py`. Render also supports WebSockets on web services. Sources: Render Web Services docs and Render WebSocket docs.

Recommended quick deploy:

1. Push this repo to GitHub.
2. Open Render Dashboard.
3. Create `New Web Service`.
4. Connect the GitHub repo.
5. Use these settings:

```text
Name: meeting-translator-api
Root Directory: leave empty
Runtime: Python
Build Command: python -m pip install --upgrade pip && python -m pip install -r requirements-render.txt
Start Command: python -m apps.api.main
Health Check Path: /health
```

Environment variables on Render:

```text
PYTHON_VERSION=3.11.9
APP_PROFILE=demo
```

Optional, only if using cloud translation:

```text
ANTHROPIC_API_KEY=your_api_key_here
```

After deploy, Render gives a backend URL like:

```text
https://meeting-translator-api.onrender.com
```

Check:

```text
https://meeting-translator-api.onrender.com/health
```

Expected:

```json
{"status":"ok","profile":"demo"}
```

WebSocket URL:

```text
wss://meeting-translator-api.onrender.com/ws
```

## Deploy Frontend To Vercel

Vercel is the frontend host. Vite exposes client-side env vars only when they are prefixed with `VITE_`, so the frontend uses `VITE_API_URL` and `VITE_WS_URL`.

1. Open Vercel Dashboard.
2. Import the same GitHub repo.
3. Set project root directory:

```text
Fontend/translator-app
```

4. Use Vercel defaults for Vite, or set manually:

```text
Framework Preset: Vite
Build Command: npm run build
Output Directory: dist
Install Command: npm install
```

5. Add environment variables:

```text
VITE_API_URL=https://meeting-translator-api.onrender.com
VITE_WS_URL=wss://meeting-translator-api.onrender.com/ws
```

Replace `meeting-translator-api.onrender.com` with your real Render backend URL.

6. Deploy.

Vercel gives a frontend URL like:

```text
https://translator-app.vercel.app
```

This is the public link to send to users.

## Deploy Order

Use this order:

1. Deploy backend on Render.
2. Open `/health` on the Render URL and confirm it returns `ok`.
3. Copy the Render backend URL.
4. Deploy frontend on Vercel with `VITE_API_URL` and `VITE_WS_URL`.
5. Open the Vercel frontend URL.
6. Click `Start Meeting`.

If the frontend shows `BACKEND OFFLINE`, check these first:

- `VITE_API_URL` must be the Render HTTPS URL.
- `VITE_WS_URL` must start with `wss://`, not `ws://`.
- Render backend might be sleeping on free plan; open `/health` once and wait for it to wake up.
- Redeploy Vercel after changing env vars. Vite env vars are baked into the build.

## Model Setup

### Current Demo Mode

The current deployed demo uses:

```text
MockASRProvider
```

This means:

- No real Whisper model is loaded.
- No GPU is required.
- Render deploy is fast and cheap.
- Audio flow and WebSocket events work for integration demo.

The mock is created in:

```text
apps/api/websocket.py
```

Current line:

```python
self.asr = MockASRProvider()
```

### Enable Real ASR With faster-whisper

Install model dependencies:

```powershell
python -m pip install faster-whisper torch underthesea
```

Config:

```yaml
asr:
  provider: faster_whisper
  model: medium
  device: auto
  compute_type: auto
```

Wrapper:

```text
core/asr/faster_whisper.py
```

To switch the WebSocket demo from mock to real Whisper, replace:

```python
self.asr = MockASRProvider()
```

with:

```python
from core.asr.faster_whisper import FasterWhisperProvider
self.asr = FasterWhisperProvider(self.manager.config.asr)
```

Model recommendations:

- CPU only: `base` or `small`
- GPU 6-8GB: `medium`
- GPU 12GB+: `large-v3`

For Render free/cheap instances, real Whisper is not recommended. Use a GPU server or a stronger paid instance.

### Enable VAD With Silero

Install:

```powershell
python -m pip install silero-vad torch
```

Config:

```yaml
vad:
  provider: silero
  frame_ms: 32
  speech_threshold: 0.55
  min_speech_ms: 180
  min_silence_ms: 450
  speech_pad_ms: 180
  max_turn_seconds: 15
```

Code:

```text
core/audio/vad.py
```

Production pipeline target:

```text
WebSocket audio -> audio queue -> preprocess -> VAD -> segmenter -> ASR final -> translation
```

### Enable Cloud Translation

The Anthropic provider is implemented in:

```text
core/translation/llm_api.py
```

Set:

```powershell
$env:ANTHROPIC_API_KEY="your_api_key_here"
```

On Render, add the same env var in service settings.

Config:

```yaml
translation:
  provider: llm_api
  model: claude-sonnet-4-6
  timeout_ms: 2500
  fallback: local
```

### Enable Local Translation

Install:

```powershell
python -m pip install transformers sentencepiece accelerate
```

Config:

```yaml
translation:
  provider: local
  local_model: VietAI/envit5-translation
```

Run:

```powershell
$env:APP_PROFILE="offline"
python -m apps.api.main
```

Local translation is not recommended on small Render instances because model download and memory usage can be large.

## WebSocket Contract

Client control messages:

```json
{"type":"session.start","session_id":"meeting-001","mode":"auto"}
{"type":"session.end","session_id":"meeting-001"}
{"type":"session.set_mode","session_id":"meeting-001","mode":"manual_vi"}
{"type":"turn.end","session_id":"meeting-001"}
{"type":"mic.select","device_id":"..."}
```

Audio is sent as JSON metadata followed by binary PCM16LE:

```json
{"type":"audio.chunk_meta","session_id":"meeting-001","sequence":124,"timestamp_ms":17342,"sample_rate":16000,"channels":1,"byte_length":3200}
```

Server events:

- `audio.received`
- `speech.started`
- `asr.partial`
- `asr.final`
- `translation.started`
- `translation.completed`
- `translation.failed`
- `utterance.corrected`
- `session.status`
- `error`

Every server event includes `session_id`, `timestamp`, `revision`, `payload`, and optional `utterance_id`.

## Tests

```powershell
python -m pip install pytest pytest-asyncio
python -m pytest
python -m py_compile apps\api\main.py core\config.py
```

