# Real-Time Vietnamese-English Meeting Translator

Backend implementation for a product-oriented meeting translator. The codebase focuses on the backend only, per project scope: FastAPI, WebSocket protocol, session orchestration, audio preprocessing, VAD, ASR interface, translation providers, glossary/entity guardrails, privacy-aware storage, observability, scripts, and tests.

## Backend Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
python -m apps.api.main
```

API defaults to `http://127.0.0.1:8000`.

Useful endpoints:

- `GET /health`
- `GET /debug`
- `WS /ws`

Profiles:

```powershell
$env:APP_PROFILE="offline"
python -m apps.api.main
```

Config files live in `config/default.yaml`, `config/demo.yaml`, and `config/offline.yaml`. Nested overrides use `APP_SECTION__FIELD`, for example `APP_TRANSLATION__TIMEOUT_MS=3000`.

## Implemented Backend Scope

- FastAPI app with WebSocket control/audio protocol.
- Pydantic config loader and language registry.
- Session manager with allowed utterance lifecycle:
  `created -> recording -> transcribing -> transcript_final -> translating -> completed`, or `failed`.
- Bounded priority queues that drop partial jobs before final jobs.
- Audio preprocessing: PCM16LE conversion, mono mix, resampling, high-pass filter.
- VAD state machine with hysteresis, speech padding, and hard cutoff support.
- Turn segmentation rules for silence, punctuation boundary, duration, language/speaker change, and manual end turn.
- ASR provider interface plus `faster-whisper` lazy wrapper and mock provider.
- Translation provider interface plus Anthropic `/v1/messages` provider and local model fallback.
- Entity protection/restoration, glossary longest-match-first matching, stable-prefix algorithm.
- Validators for missing entities, possible negation loss, and possible added content.
- Circuit breaker for cloud translation fallback.
- SQLite transcript metadata and JSONL event log, respecting privacy config.
- `/debug` route with queue and metrics snapshot.
- Preflight, model download placeholder, benchmark placeholder, demo runner.
- Unit tests for config, protocol events, session transitions, audio, VAD/segmentation, queue behavior, translation guardrails.

## WebSocket Contract

Client sends JSON control messages:

```json
{"type":"session.start","session_id":"meeting-001","mode":"auto"}
{"type":"session.end","session_id":"meeting-001"}
{"type":"session.set_mode","session_id":"meeting-001","mode":"manual_vi"}
{"type":"turn.end","session_id":"meeting-001"}
{"type":"mic.select","device_id":"..."}
{"type":"glossary.update","entries":[{"source":"bien ban ghi nho","target":"memorandum of understanding","direction":"vi-en","case_sensitive":false,"category":"legal","priority":10}]}
{"type":"transcript.correct","utterance_id":"utt-102","corrected_text":"..."}
{"type":"translation.retry","utterance_id":"utt-102"}
```

For audio, send a JSON metadata frame immediately before each binary frame:

```json
{"type":"audio.chunk_meta","session_id":"meeting-001","sequence":124,"timestamp_ms":17342,"sample_rate":16000,"channels":1,"byte_length":3200}
```

Then send binary PCM16LE mono audio, 16kHz, chunk size 20-100ms.

Server event names:

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

## Frontend Requirements

The frontend is intentionally not implemented in this repo pass. Build it as `React + Vite + TypeScript + Tailwind`, and connect to the backend contract above.

Required frontend behavior:

- Use Web Audio API with `AudioWorklet`, not `ScriptProcessorNode`.
- Capture raw mic PCM, resample to 16kHz mono, send chunks every 20-100ms.
- Send `audio.chunk_meta` before each binary audio frame with increasing `sequence`.
- Provide microphone selector using `navigator.mediaDevices.enumerateDevices()`.
- Send `mic.select` when mic changes, but do not auto-switch mic during an active session.
- Show VU meter, muted warning, and clipping warning.
- Main layout: two columns, `ORIGINAL` on the left and `TRANSLATION` on the right.
- Header must show session status, selected mic, active mode, and processing badge.
- Footer controls: Pause, Push to Talk, Correct, End Meeting.
- Manual fallback controls: Hold to Speak Vietnamese, Hold to Speak English.
- Support modes: `auto`, `manual_vi`, `manual_en`, `seat_a`, `seat_b`.
- Render transcript states distinctly: Listening, Transcribing, Partial, Final, Translating, Completed, Low confidence, Error.
- Render unstable partial transcript text dim/italic using backend stable-prefix semantics.
- Do not mutate a final transcript except after user correction via `transcript.correct`.
- Display translation warnings from `translation.completed.payload.warnings`.
- Badge privacy/provider clearly: local processing vs cloud translation.
- Add Clear session, Export JSON, and Export Markdown actions.
- Add `/debug` page outside the main UI showing backend health, queue depth, last error, p50/p95 latency, model/backend status, and network status.
- UI must remain responsive while receiving updates every 500-800ms.

## Testing

```powershell
python -m pytest
python -m py_compile apps\api\main.py core\config.py
```

The heavyweight ASR/local translation models are lazy-loaded so the backend and tests can run before model cache warmup. Use `scripts/download_models.py` and real audio samples before production demo.

## Connected Frontend

The current frontend lives at `Fontend/translator-app`.

Local run:

```powershell
python -m pip install fastapi "uvicorn[standard]"
python -m apps.api.main
cd Fontend\translator-app
npm install
npm run dev -- --host 0.0.0.0
```

Open `http://127.0.0.1:5173`. Vite proxies `/ws`, `/health`, and `/debug` to the backend at `http://127.0.0.1:8000`, so frontend and backend can be exposed through one public URL.

Simple public sharing:

```powershell
ngrok http 5173
```

Share the HTTPS ngrok URL. On ngrok free domains, external users may see a trust/interstitial page first; after accepting it, the React app and WebSocket proxy use the same public origin.
