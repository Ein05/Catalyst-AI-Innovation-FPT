# Real-Time Vietnamese-English Meeting Translator

Ứng dụng dịch họp thời gian thực Việt-Anh gồm:

- Backend: Python + FastAPI + WebSocket.
- Frontend: React + Vite + TypeScript trong `Fontend/translator-app`.
- Public sharing: dùng ngrok expose một port frontend, Vite proxy `/ws`, `/health`, `/debug` về backend.

> Trạng thái hiện tại: app đã nối frontend-backend và chạy được demo protocol. ASR thật bằng Whisper/VAD/model dịch local đã có wrapper nhưng WebSocket demo hiện đang dùng mock ASR để chạy nhẹ, không cần tải model nặng.

## 1. Chạy Backend

Từ root repo:

```powershell
cd D:\Work\HackerThonFpt
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install fastapi "uvicorn[standard]" pydantic PyYAML httpx numpy scipy
python -m apps.api.main
```

Backend chạy tại:

```text
http://127.0.0.1:8000
```

Kiểm tra:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Endpoint chính:

- `GET /health`
- `GET /debug`
- `WS /ws`
- `WS /ws/ws` compatibility route

Nếu port `8000` bị chiếm:

```powershell
netstat -ano | Select-String ':8000'
Stop-Process -Id <PID_8000>
```

## 2. Chạy Frontend

Mở terminal khác:

```powershell
cd D:\Work\HackerThonFpt\Fontend\translator-app
npm install
npm run dev -- --host 0.0.0.0
```

Frontend chạy tại:

```text
http://127.0.0.1:5173
```

Vite config đã proxy:

- `/ws` -> `ws://127.0.0.1:8000/ws`
- `/health` -> `http://127.0.0.1:8000/health`
- `/debug` -> `http://127.0.0.1:8000/debug`

Vì vậy frontend và backend có thể public qua một link duy nhất.

Nếu port `5173` bị chiếm:

```powershell
netstat -ano | Select-String ':5173'
Stop-Process -Id <PID_5173>
```

## 3. Public Link Cho Người Khác Dùng

Cách đơn giản nhất hiện tại là ngrok:

```powershell
ngrok http 5173
```

Ngrok sẽ in ra một HTTPS URL, ví dụ:

```text
https://xxxx.ngrok-free.dev
```

Gửi link đó cho người dùng bên thứ ba. Họ có thể vào từ máy khác, miễn là:

- Máy chạy app vẫn bật.
- Backend vẫn chạy.
- Frontend vẫn chạy.
- Ngrok vẫn chạy.

Lưu ý: ngrok free thường hiện trang cảnh báo/trust page lần đầu. Người dùng chỉ cần bấm tiếp để vào app. Mỗi lần restart ngrok free có thể đổi link.

## 4. Cấu Hình Profile

Config nằm trong:

- `config/default.yaml`
- `config/demo.yaml`
- `config/offline.yaml`

Chạy profile offline:

```powershell
$env:APP_PROFILE="offline"
python -m apps.api.main
```

Override config bằng env:

```powershell
$env:APP_TRANSLATION__TIMEOUT_MS="3000"
```

## 5. Bật Model Thật

### ASR thật: faster-whisper

Cài dependency:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install faster-whisper torch underthesea
```

Model config ở `config/default.yaml`:

```yaml
asr:
  provider: faster_whisper
  model: medium
  device: auto
  compute_type: auto
```

Gợi ý model:

- CPU/demo nhẹ: `small` hoặc `base`
- GPU 6-8GB: `medium`
- GPU 12GB+: `large-v3`

Wrapper đã có ở:

```text
core/asr/faster_whisper.py
```

Hiện WebSocket demo đang dùng mock ASR tại:

```python
self.asr = MockASRProvider()
```

trong:

```text
apps/api/websocket.py
```

Để dùng Whisper thật, đổi sang provider factory hoặc thay bằng:

```python
from core.asr.faster_whisper import FasterWhisperProvider
self.asr = FasterWhisperProvider(self.manager.config.asr)
```

### VAD thật: Silero VAD

Cài dependency:

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

Code VAD nằm ở:

```text
core/audio/vad.py
```

Hiện pipeline demo transcribe theo audio chunk để dễ test kết nối. Giai đoạn production cần nối flow:

```text
WebSocket audio -> audio queue -> preprocess -> VAD -> segmenter -> ASR final -> translation
```

### Dịch bằng cloud Anthropic

Cài `httpx` nếu chưa có:

```powershell
python -m pip install httpx
```

Set API key:

```powershell
$env:ANTHROPIC_API_KEY="your_api_key_here"
```

Config:

```yaml
translation:
  provider: llm_api
  model: claude-sonnet-4-6
  timeout_ms: 2500
  fallback: local
```

Provider nằm ở:

```text
core/translation/llm_api.py
```

### Dịch local/offline

Cài dependency:

```powershell
python -m pip install transformers sentencepiece accelerate
```

Config:

```yaml
translation:
  provider: local
  local_model: VietAI/envit5-translation
```

Chạy offline:

```powershell
$env:APP_PROFILE="offline"
python -m apps.api.main
```

Provider nằm ở:

```text
core/translation/local_model.py
```

Nếu local model chưa tải được, code có rule-based fallback để app không crash, nhưng chất lượng chỉ đủ demo kỹ thuật.

## 6. Kiểm Tra Trước Demo

Backend:

```powershell
cd D:\Work\HackerThonFpt
.\.venv\Scripts\Activate.ps1
python scripts\preflight.py
python -m apps.api.main
```

Frontend:

```powershell
cd D:\Work\HackerThonFpt\Fontend\translator-app
npm run build
npm run dev -- --host 0.0.0.0
```

WebSocket smoke test:

```powershell
python -c "import asyncio,json,websockets; async def main():`n async with websockets.connect('ws://127.0.0.1:5173/ws') as ws:`n  await ws.send(json.dumps({'type':'session.start','session_id':'smoke','mode':'auto'})); print(await ws.recv())`nasyncio.run(main())"
```

## 7. Tests

Cài test deps:

```powershell
python -m pip install pytest pytest-asyncio
```

Chạy:

```powershell
python -m pytest
python -m py_compile apps\api\main.py core\config.py
```

## 8. WebSocket Contract

Client gửi JSON control:

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

Audio gửi theo cặp:

```json
{"type":"audio.chunk_meta","session_id":"meeting-001","sequence":124,"timestamp_ms":17342,"sample_rate":16000,"channels":1,"byte_length":3200}
```

Sau đó gửi binary PCM16LE mono audio.

Server event:

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

Mỗi event có `session_id`, `timestamp`, `revision`, `payload`, và optional `utterance_id`.

## 9. Backend Scope Đã Có

- FastAPI app + WebSocket.
- Config YAML + env override.
- Session manager, lifecycle, revision chống stale result.
- Bounded priority queue.
- Audio preprocessing.
- VAD state machine.
- Turn segmenter.
- ASR interface, mock, faster-whisper wrapper.
- Translation interface, Anthropic provider, local provider.
- Entity protection, glossary, validators.
- Circuit breaker cloud fallback.
- SQLite transcript metadata + JSONL event log.
- `/debug` observability route.
