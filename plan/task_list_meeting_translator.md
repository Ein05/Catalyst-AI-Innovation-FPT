# Task List — Real-Time Vietnamese–English Meeting Translator
> Nguồn: Product & Technical Plan (AI Singapore Hackathon, 2-day build)
> Mục đích file này: giao trực tiếp cho AI coding agent (Claude Code / tương tự) để implement từng task theo thứ tự. Mỗi task tự chứa đủ context, schema, config để agent không cần hỏi lại.

## Locked decisions (đọc trước khi code bất kỳ task nào)
Các quyết định sau đã được chốt để loại bỏ ambiguity. Nếu người dùng nói khác, ưu tiên chỉ dẫn mới của người dùng.

- **Architecture:** Cascade pipeline (Audio → VAD → ASR → Translation → UI). KHÔNG build end-to-end model (SeamlessM4T) trong core path — chỉ để sau như experimental branch nếu còn thời gian.
- **Backend:** Python 3.11 + FastAPI + WebSocket.
- **Frontend:** React + Vite (TypeScript), Tailwind cho styling. KHÔNG dùng Gradio cho bản chính.
- **ASR:** `faster-whisper`, model `medium` mặc định (fallback `small` nếu CPU-only hoặc GPU <8GB).
- **VAD:** Silero VAD (torch.hub hoặc onnx runtime), chạy trên CPU.
- **Translation:** Interface-based, 2 provider ban đầu — `llm_api` (dùng Anthropic Claude API qua `/v1/messages`, model mặc định `claude-sonnet-4-6`) làm primary, và một `local_model` (EnViT5 hoặc NLLB — chọn EnViT5 trước, benchmark sau) làm fallback/offline.
- **Storage:** SQLite (metadata/session/history) + JSONL (event log). Không lưu raw audio mặc định (`privacy.mode: ephemeral`).
- **Transport:** WebSocket, binary audio frames (PCM16, 16kHz, mono) + JSON control/event messages trên cùng connection (dùng subprotocol phân biệt bằng 1 byte header hoặc 2 kênh message type: `type: "audio_chunk"` base64 hoặc binary frame riêng — xem Task 2).
- **Vietnamese sentence normalization:** dùng `underthesea` cho word/sentence segmentation + basic punctuation restoration heuristic (không cần model riêng cho hackathon).
- **Glossary matching:** longest-match-first, case-insensitive theo `case_sensitive` flag trong schema, áp dụng trước khi gửi text vào translation provider (không phải sau).
- **Stable-prefix algorithm:** token-level LCS (longest common prefix theo word-tokenized text) giữa lần ASR partial hiện tại và lần trước đó; phần trùng = stable, phần còn lại = unstable (in nghiêng/mờ ở UI).

---

## Phase 1 — Day 1: Core reliable pipeline (P0/P1)
Mục tiêu bắt buộc cuối Phase 1: nói tiếng Việt → thấy transcript → thấy bản dịch tiếng Anh, và ngược lại. Chạy ổn định liên tục ≥20 phút.

### Task 1 — Project scaffolding
**Mục tiêu:** Tạo cấu trúc thư mục monorepo đúng theo module structure đã định.
**Yêu cầu:**
- Tạo cấu trúc:
```
project/
├── apps/api/ (FastAPI app: main.py, websocket.py, routes/)
├── apps/web/ (React + Vite + TS)
├── core/audio/ (capture.py, resample.py, vad.py, segmenter.py)
├── core/asr/ (base.py, faster_whisper.py, mock.py)
├── core/translation/ (base.py, local_model.py, llm_api.py, glossary.py, validator.py)
├── core/tts/ (base.py, local_tts.py) — stub, không implement logic thật ở Phase 1
├── core/session/ (manager.py, state.py, events.py)
├── core/observability/ (metrics.py, logging.py, tracing.py)
├── config/ (default.yaml, demo.yaml, offline.yaml)
├── tests/ (unit/, integration/, audio_samples/, evaluation/)
├── scripts/ (download_models.py, benchmark.py, preflight.py, run_demo.py)
├── data/ (glossary/, sessions/, evaluation/)
├── docker-compose.yml, Makefile, README.md, pyproject.toml
```
- Python deps qua `pyproject.toml`: fastapi, uvicorn[standard], websockets, faster-whisper, torch, silero-vad deps, underthesea, pydantic, sqlite3 (stdlib), httpx (gọi Anthropic API), pyyaml, numpy, scipy (resample).
- Frontend: React + Vite + TypeScript + Tailwind, `npm install` phải chạy sạch.
**DoD:** `python -m apps.api.main` khởi động FastAPI không lỗi (dù các module core còn là stub trả mock data). `npm run dev` ở `apps/web` chạy được trang trắng.

---

### Task 2 — Config system + language registry
**Mục tiêu:** Load config từ YAML theo profile, hỗ trợ override qua env var.
**Schema config (default.yaml):**
```yaml
profile: demo
audio:
  sample_rate: 16000
  channels: 1
vad:
  provider: silero
  frame_ms: 32
  speech_threshold: 0.55
  min_speech_ms: 180
  min_silence_ms: 450
  speech_pad_ms: 180
  max_turn_seconds: 15
asr:
  provider: faster_whisper
  model: medium
  device: cuda
  compute_type: float16
translation:
  provider: llm_api
  timeout_ms: 2500
  fallback: local
queues:
  audio_max_items: 200
  asr_max_items: 10
  translation_max_items: 20
timeouts:
  partial_asr_ms: 1500
  final_asr_ms: 4000
  translation_ms: 3000
  tts_ms: 5000
privacy:
  mode: ephemeral
  store_audio: false
  store_transcript: false
languages:
  vi: { display_name: Vietnamese, asr_code: vi, translation_code: vi }
  en: { display_name: English, asr_code: en, translation_code: en }
```
- Cung cấp `offline.yaml` (asr provider giữ nguyên, translation.provider = local, privacy.mode = local_only) và `demo.yaml` (override cụ thể cho demo machine).
- Code KHÔNG được hardcode `if language == "vi"` ở bất kỳ đâu — luôn tra qua `languages` registry.
**DoD:** `core/config.py` expose hàm `load_config(profile: str) -> Config` (pydantic model), unit test load cả 3 profile không lỗi, test override qua env var (`APP_PROFILE=offline`).

---

### Task 3 — WebSocket protocol contract
**Mục tiêu:** Định nghĩa đầy đủ message contract giữa frontend và backend (đây là phần doc gốc chưa spec chi tiết — chốt tại đây).
**Client → Server messages (JSON, trừ audio là binary frame riêng):**
```json
// Control
{"type": "session.start", "session_id": "meeting-001", "mode": "auto|manual_vi|manual_en|seat_a|seat_b"}
{"type": "session.end", "session_id": "meeting-001"}
{"type": "session.set_mode", "session_id": "meeting-001", "mode": "manual_vi"}
{"type": "turn.end", "session_id": "meeting-001"}  // manual end-turn button
{"type": "mic.select", "device_id": "..."}
{"type": "glossary.update", "entries": [{"source": "...", "target": "...", "direction": "vi-en", "case_sensitive": false, "category": "legal", "priority": 10}]}
{"type": "transcript.correct", "utterance_id": "utt-102", "corrected_text": "..."}
{"type": "translation.retry", "utterance_id": "utt-102"}
```
- Audio: binary WebSocket frames, mỗi frame = PCM16LE mono 16kHz chunk (20–100ms) kèm 1 JSON metadata frame gửi trước đó theo schema:
```json
{"type": "audio.chunk_meta", "session_id": "meeting-001", "sequence": 124, "timestamp_ms": 17342, "sample_rate": 16000, "channels": 1, "byte_length": 3200}
```
**Server → Client messages (theo event names ở core/session/events.py):**
```
audio.received, speech.started, asr.partial, asr.final,
translation.started, translation.completed, translation.failed,
utterance.corrected, session.status, error
```
- Ví dụ `asr.partial`/`asr.final` payload phải theo đúng ASR output schema (xem Task 8).
- Ví dụ `translation.completed`:
```json
{"event": "translation.completed", "session_id": "meeting-001", "utterance_id": "utt-102",
 "timestamp": "2026-07-17T10:45:22.412Z",
 "payload": {"source": "...", "translation": "...", "latency_ms": 483, "warnings": []}}
```
- Mọi server→client message phải kèm `revision` số nguyên tăng dần theo utterance để frontend loại bỏ stale result (nếu revision mới hơn đã nhận thì bỏ qua message cũ).
**DoD:** File `core/session/events.py` định nghĩa dataclass/pydantic model cho từng event type + hàm serialize/deserialize. Unit test round-trip serialize cho mỗi event type.

---

### Task 4 — Session Orchestrator
**Mục tiêu:** Quản lý state của một meeting session và điều phối giữa audio/ASR/translation pipeline.
**Yêu cầu:**
- `core/session/manager.py`: class `SessionManager` giữ dict `session_id -> SessionState`.
- `SessionState` gồm: session_id, mode (auto/manual_vi/manual_en/seat_a/seat_b), current speaker, sequence counters, active utterances, glossary version, config snapshot.
- Utterance lifecycle bắt buộc theo đúng thứ tự: `created → recording → transcribing → transcript_final → translating → completed` (hoặc `→ failed` ở bất kỳ bước nào với lý do rõ ràng).
- Orchestrator nhận audio chunk từ WebSocket handler, đẩy vào audio queue (không xử lý trực tiếp trong WS handler — xem Task 14).
**DoD:** Unit test: tạo session, feed các event theo thứ tự, assert state transition đúng; test transition sai thứ tự bị reject với lỗi rõ ràng.

---

### Task 5 — Frontend audio capture
**Mục tiêu:** Capture mic audio trên browser, gửi qua WebSocket đúng theo Task 3 contract.
**Yêu cầu:**
- Dùng Web Audio API (`AudioWorklet`, không dùng deprecated `ScriptProcessorNode`) để lấy raw PCM, resample về 16kHz mono trước khi gửi (nếu browser input khác rate).
- Gửi chunk 20–100ms, kèm metadata JSON đúng schema Task 3.
- UI hiển thị input level (VU meter đơn giản), cảnh báo nếu mic muted hoặc clipping (peak > threshold).
- Cho phép chọn microphone qua `navigator.mediaDevices.enumerateDevices()`, gửi `mic.select` khi đổi. KHÔNG tự động đổi mic giữa phiên đang chạy.
**DoD:** Có thể nói vào mic, thấy VU meter phản ứng, WebSocket server log nhận được audio chunk metadata đúng sequence tăng dần liên tục.

---

### Task 6 — Audio preprocessing (backend)
**Mục tiêu:** Nhận raw PCM từ WS, chuẩn hóa trước khi đưa vào VAD.
**Pipeline:** raw audio → channel conversion (nếu cần) → resample về 16kHz nếu client gửi rate khác → high-pass filter (loại bỏ <80Hz) → (optional, nhẹ) noise suppression → VAD.
**Yêu cầu:**
- KHÔNG áp dụng aggressive denoising mặc định (theo nguyên tắc 9.2 trong plan — audio enhancement mạnh có thể làm giảm chất lượng ASR). Noise suppression chỉ bật ở mức nhẹ, có flag để tắt hoàn toàn qua config.
- Duy trì circular buffer pre-roll 200–300ms để không cắt mất âm đầu câu khi VAD phát hiện speech start.
**DoD:** Unit test resample từ 44100→16000 giữ đúng độ dài audio kỳ vọng (±1 sample). Test high-pass filter loại bỏ tần số thấp trên synthetic sine wave.

---

### Task 7 — VAD module
**Mục tiêu:** Tích hợp Silero VAD với logic hysteresis, không dùng single-frame threshold.
**Params (từ config, xem Task 2):** `speech_threshold: 0.55, min_speech_ms: 180, min_silence_ms: 450, speech_pad_ms: 180, max_turn_seconds: 15, frame_ms: 32`.
**Logic:**
- Không kết thúc turn ngay khi 1 frame báo silence — cần `min_silence_ms` liên tục silence mới đóng turn.
- Áp dụng `speech_pad_ms` trước và sau đoạn speech thực tế (dùng pre-roll buffer từ Task 6).
- Hard cutoff tại `max_turn_seconds` để tránh turn vô hạn (force commit).
**DoD:** Unit test với synthetic audio (silence-speech-silence pattern) trả về đúng speech start/end timestamps theo params trên. Test hard cutoff kích hoạt đúng tại 15s nếu speech liên tục không dừng.

---

### Task 8 — Turn segmentation
**Mục tiêu:** Quyết định khi nào commit một segment sang ASR final / translation.
**Commit rules (OR logic — bất kỳ điều kiện nào đúng thì commit):**
- `silence >= 450–700ms` (lấy từ VAD)
- `punctuation_boundary AND stable_transcript` (dấu câu + ASR partial đã ổn định qua ≥2 lần liên tiếp)
- `segment_duration >= 8–12s`
- `speaker_or_language_change`
- `manual_end_turn_action` (từ event `turn.end` — Task 3)
**Yêu cầu:** Semantic chunking — không commit ngay khi gặp punctuation giữa mệnh đề phụ thuộc rõ ràng (vd sau "We propose to deliver..." chưa commit, chờ đến hết mệnh đề chính). Với hackathon: rule đơn giản là chỉ commit ở dấu `.`, `?`, `!`, không commit ở dấu `,`.
**DoD:** Unit test đưa vào chuỗi các mock VAD/ASR partial events, assert đúng thời điểm commit event được emit theo từng rule riêng lẻ và kết hợp.

---

### Task 9 — ASR service (faster-whisper)
**Mục tiêu:** Wrapper cho faster-whisper theo `ASRProvider` interface, chạy cả partial và final.
**Interface (bắt buộc dùng nguyên):**
```python
from dataclasses import dataclass
from typing import Protocol

@dataclass
class TranscriptionResult:
    text: str
    language: str
    confidence: float | None
    is_final: bool
    start_ms: int
    end_ms: int

class ASRProvider(Protocol):
    async def transcribe(self, audio: bytes, sample_rate: int, language_hint: str | None = None) -> TranscriptionResult: ...
```
**Output event schema (cho `asr.partial`/`asr.final`):**
```json
{
  "utterance_id": "utt-102", "speaker_id": "speaker-a", "language": "vi",
  "language_confidence": 0.96, "partial_text": "...", "final_text": "...",
  "start_ms": 12400, "end_ms": 17150, "asr_latency_ms": 610
}
```
**Model config theo hardware (implement như config lookup, không hardcode if/else dài):**
| Hardware | Model | Fallback |
|---|---|---|
| CPU laptop | small/medium quantized | base |
| GPU 6-8GB | medium/large-v3 quantized | small |
| GPU 12GB+ | large-v3 | medium |
**Partial transcript strategy:** chạy partial mỗi 500–800ms trên rolling window có overlap, KHÔNG chạy full buffer mỗi 100ms. Final pass chạy khi turn segmentation (Task 8) báo commit.
**DoD:** Given 1 sample audio file tiếng Việt và 1 tiếng Anh trong `tests/audio_samples/`, `transcribe()` trả về text đúng ngôn ngữ với `language_confidence > 0.8`. Integration test đo `asr_latency_ms` được ghi log.

---

### Task 10 — Stable-prefix algorithm
**Mục tiêu:** Từ chuỗi các partial transcript liên tiếp, tính phần "stable" (hiển thị rõ) vs "unstable" (hiển thị mờ/italic).
**Thuật toán (chốt cứng):** Tokenize cả 2 chuỗi (partial mới, partial trước) theo whitespace-split (tiếng Việt: dùng `underthesea.word_tokenize` để tránh cắt sai từ ghép). Tính longest common prefix theo token. Token nằm trong common prefix = stable; phần còn lại của chuỗi mới = unstable.
**DoD:** Unit test với ví dụ chính xác từ plan:
- Lần 1: "Chúng tôi sẽ giao"
- Lần 2: "Chúng tôi sẽ giao hàng vào"
- Lần 3: "Chúng tôi sẽ giao hàng vào thứ sáu"
→ Stable prefix tại lần 3 phải là "Chúng tôi sẽ giao" (theo đúng ví dụ trong plan gốc — lưu ý: đây là ví dụ đơn giản hoá, common prefix thực tế giữa lần 2 và 3 dài hơn "Chúng tôi sẽ giao" nên assert theo logic thuật toán, không copy y nguyên kết luận của plan nếu thuật toán cho kết quả khác — ưu tiên tính đúng theo thuật toán đã chốt).

---

### Task 11 — Translation interface + providers
**Interface (bắt buộc dùng nguyên):**
```python
@dataclass
class TranslationResult:
    source_text: str
    translated_text: str
    source_language: str
    target_language: str
    latency_ms: int
    warnings: list[str]

class TranslationProvider(Protocol):
    async def translate(self, text: str, source_language: str, target_language: str,
                         glossary: dict[str, str] | None = None) -> TranslationResult: ...
```
**Provider 1 — `llm_api` (primary):** Gọi Anthropic API (`POST https://api.anthropic.com/v1/messages`, model `claude-sonnet-4-6`, max_tokens 1000). System/user prompt PHẢI theo template này (không tự sáng tạo lại):
```
Translate the following business meeting utterance from {source_lang} to {target_lang}.
Requirements:
- Preserve meaning, intent, names, numbers, dates and commercial terms.
- Do not summarize.
- Do not explain.
- Do not add information.
- Produce only the translation.
- Use concise professional business language.

Glossary:
{glossary_entries_as_bullet_list}

Text:
{{source_text}}
```
- Timeout theo config `translation.timeout_ms` (2500ms). Nếu timeout hoặc lỗi → raise để orchestrator xử lý fallback (Task 15).
**Provider 2 — `local_model` (fallback):** Wrapper cho EnViT5 (HuggingFace) chạy local, không gọi network. Dùng cho `offline` profile và circuit-breaker fallback.
**DoD:** Cả 2 provider implement cùng interface, có thể swap qua config (`translation.provider: llm_api | local`) mà không đổi code orchestration. Integration test: câu tiếng Việt có tên riêng + số → bản dịch giữ nguyên số.

---

### Task 12 — Input normalization & entity protection
**Mục tiêu:** Bảo vệ số, ngày, tiền tệ, tên riêng khỏi bị translation model làm sai lệch.
**Pipeline (trước khi gửi vào translation provider):**
1. Chuẩn hóa khoảng trắng, không lowercase toàn bộ, không tự sửa số.
2. Extract entities theo schema:
```json
{"numbers": ["25", "2.5 million", "30%"], "dates": ["17 July", "Q4"], "currencies": ["SGD"], "entities": ["AI Singapore", "NTU"]}
```
3. Thay thế bằng placeholder: `<NUM_1>`, `<CUR_1>`, `<TERM_1>`, v.v. trước khi dịch.
4. Sau khi dịch, restore lại giá trị gốc vào đúng vị trí placeholder trong bản dịch.
5. **Validator (Task 13) sẽ kiểm tra tất cả entity trong bước 2 còn tồn tại trong output cuối cùng, không phải kiểm tra placeholder** (vì placeholder đã được restore ở bước 4).
**Ví dụ bắt buộc pass được:**
- Input: `Chúng tôi đặt mục tiêu doanh thu 2.5 triệu SGD trong Q4`
- Output: `We are targeting revenue of SGD 2.5 million in Q4.`
**DoD:** Unit test extract/protect/restore round-trip cho câu ví dụ trên và ít nhất 5 câu khác chứa ngày/số/currency/tên công ty.

---

### Task 13 — Glossary system + business guardrails/validators
**Glossary schema:**
```json
{"source": "biên bản ghi nhớ", "target": "memorandum of understanding", "direction": "vi-en", "case_sensitive": false, "category": "legal", "priority": 10}
```
**Matching:** longest-match-first trên source text, filter theo `direction` (vi-en hoặc en-vi) và `case_sensitive`. Priority cao hơn thắng nếu overlap.
**Storage:** JSON file trong `data/glossary/{session_id}.json`, load vào memory khi session start, update qua event `glossary.update` (Task 3).
**Validators (chạy sau khi có bản dịch, trước khi emit `translation.completed`):**
1. **Entity check:** tất cả numbers/dates/currencies/entities extract ở Task 12 phải xuất hiện trong bản dịch. Nếu thiếu → thêm warning, trigger retry với prompt mạnh hơn (nhấn mạnh "MUST include all numbers and names exactly").
2. **Negation check:** nếu source chứa 1 trong các từ phủ định tiếng Việt (`không`, `chưa`, `không thể`) hoặc tiếng Anh (`not`, `cannot`, `do not`, `have not`) mà bản dịch KHÔNG có tín hiệu phủ định tương ứng → warning `"possible negation lost"`.
3. **No-added-information check (best-effort cho hackathon):** so sánh độ dài câu nguồn/đích, nếu bản dịch dài hơn bất thường (>1.8x số từ) → warning `"possible added content"`.
- Nếu có warning nghiêm trọng (entity mất) → tự động retry translation 1 lần. Nếu vẫn lỗi → emit `translation.completed` kèm `warnings` để UI hiển thị cảnh báo (KHÔNG silent-fail).
**DoD:** Unit test validator với câu ví dụ trong plan: `"We cannot deliver before Friday."` dịch sai thành `"Chúng tôi có thể giao trước thứ Sáu."` → validator PHẢI flag negation warning.

---

### Task 14 — Concurrency & queue architecture
**Mục tiêu:** WebSocket handler không được block chạy model trực tiếp.
**Pipeline:** `WS receiver → audio queue → VAD worker → ASR queue → ASR worker → translation queue → translation worker → WS publisher`.
**Bounded queues** (limits từ config Task 2): `audio_max_items: 200, asr_max_items: 10, translation_max_items: 20`.
**Khi queue đầy:**
- Không crash.
- Drop partial jobs trước (final utterance không bao giờ bị drop).
- Emit `session.status` với message "processing delayed".
- Giảm tần suất partial ASR tạm thời.
**Priority order (worker pool xử lý theo priority, không phải FIFO thuần):** 1) Final ASR, 2) Final translation, 3) Partial ASR, 4) TTS, 5) Summary.
**DoD:** Load test: feed queue vượt `asr_max_items`, assert không crash, assert final utterance vẫn được xử lý đầy đủ trong khi partial bị drop, assert `session.status` "processing delayed" được emit.

---

### Task 15 — Failure handling
**Timeouts (từ config):** `partial_asr_ms: 1500, final_asr_ms: 4000, translation_ms: 3000, tts_ms: 5000`.
**Retry policy:**
- ASR local: không retry vô hạn (max 1 retry với timeout ngắn hơn).
- API translation: tối đa 1 retry, exponential backoff nhỏ (vd 300ms).
- Không retry nếu input rỗng hoặc partial đã stale (revision cũ hơn — xem Task 3).
**Circuit breaker (cho cloud translation):** 3 failures trong 30 giây → mở circuit → tự động chuyển `translation.provider` sang `local` → thử lại cloud provider sau 60 giây.
**Stale result protection:** mỗi request có `session_id + utterance_id + revision`. Nếu response về sau khi đã có revision mới hơn cho cùng utterance_id → discard, không emit lên UI.
**DoD:** Integration test giả lập translation API fail liên tục 3 lần trong 30s → assert circuit breaker chuyển sang local provider tự động; test 1 request cũ trả về sau request mới → assert bị discard.

---

### Task 16 — Bilingual UI (React)
**Layout:** 2 cột — ORIGINAL (trái) / TRANSLATION (phải), header hiển thị session status + mic đang chọn + mode (Auto VI↔EN). Footer có 4 nút: Pause, Push to Talk, Correct, End Meeting.
**Transcript states cần phân biệt bằng style riêng:** Listening, Transcribing, Partial (mờ/italic — dùng kết quả Task 10 để tô riêng phần unstable), Final (rõ, không đổi trừ khi user sửa), Translating, Completed, Low confidence (viền cảnh báo), Error.
**Yêu cầu UX quan trọng:** Transcript final KHÔNG được tự thay đổi sau khi đã final, trừ khi qua event `transcript.correct` từ chính user.
**Manual fallback buttons:** "Hold to Speak Vietnamese" / "Hold to Speak English" — khi giữ nút, gửi `session.set_mode` tương ứng và audio route trực tiếp không qua auto-detection.
**DoD:** Demo được đúng flow: nói VI → thấy transcript VI (partial mờ → final rõ) → thấy translation EN xuất hiện sau. Chạy responsive, không giật khi update liên tục mỗi 500-800ms.

---

### Task 17 — Language direction detection modes
**3 chế độ (đều phải hoạt động, không chỉ auto):**
1. Auto-detection: dùng `language` + `language_confidence` từ ASR (Task 9).
2. Manual seat mode: mic A cố định = Vietnamese, mic B cố định = English (chọn qua UI).
3. Push-to-talk: 2 nút giữ để nói (Task 16), override hoàn toàn auto-detection khi đang giữ.
**DoD:** Test chuyển đổi qua lại giữa 3 mode trong 1 session không cần restart, state được giữ đúng.

---

## Phase 2 — Day 2: Hardening, testing, packaging (P2)

### Task 18 — Speaker handling
**Mục tiêu:** Label người nói mà KHÔNG bắt buộc full diarization.
**3 cách hỗ trợ:** (1) 2 mic riêng cho mỗi bên — ổn định nhất; (2) seat assignment chọn qua UI; (3) basic diarization (optional/nice-to-have, có thể bỏ nếu thiếu thời gian).
**Labels dùng:** "Vietnamese Delegate", "Singapore Delegate", "Moderator" — không cố đoán tên cụ thể.
**Overlapping speech:** khi phát hiện 2 nguồn nói cùng lúc (hoặc VAD phát hiện bất thường), hiển thị cảnh báo "Overlapping speech detected", KHÔNG tạo bản dịch tự tin giả, lưu audio để replay, có thể yêu cầu nói lại.
**DoD:** Test với 2 mic input giả lập nói chồng nhau → UI hiển thị warning, không emit translation sai.

---

### Task 19 — Data storage & privacy
**Storage modes theo config:**
```yaml
privacy:
  mode: ephemeral
  store_audio: false
  store_transcript: false
# hoặc
privacy:
  mode: meeting_record
  store_audio: true
  store_transcript: true
  retention_days: 7
```
**Yêu cầu:** SQLite lưu session metadata + transcript history (nếu mode cho phép), JSONL lưu event log. Nút "Clear session" xóa toàn bộ data của session đó. Export transcript ra Markdown hoặc JSON qua UI. UI có badge rõ ràng "📍 Local processing" hoặc "☁ Translation uses cloud service" tùy provider đang active — không được giấu việc dữ liệu gửi ra ngoài.
**DoD:** Test ephemeral mode không ghi file audio nào xuống disk. Test export transcript ra file JSON hợp lệ.

---

### Task 20 — Observability
**Structured log format:**
```json
{"level": "INFO", "event": "asr.final", "utterance_id": "utt-12", "audio_duration_ms": 4520, "processing_ms": 680, "real_time_factor": 0.15, "language": "vi"}
```
**Metrics cần track:** `audio_chunk_lag_ms, vad_turn_duration_ms, asr_partial_latency_ms, asr_final_latency_ms, translation_latency_ms, end_to_end_latency_ms, queue_depth, dropped_partial_count, translation_retry_count, language_detection_errors, session_crash_count`.
**`/debug` page (route riêng, KHÔNG hiển thị trong UI chính):** GPU memory, CPU, model loaded, queue depth, mic input, last error, latency p50/p95, network status, current backend.
**DoD:** Trang `/debug` load được, hiển thị số liệu real-time trong khi 1 session đang chạy.

---

### Task 21 — Testing suite
**Unit tests:** audio resampling, VAD state transitions, segment merging, glossary replacement, number extraction, language routing, timeout logic, retry logic, stale result rejection, event serialization.
**Integration test:** audio file → ASR → translation → final event, assert không crash, đúng thứ tự event, không mất utterance, translation không rỗng, latency trong giới hạn config.
**Golden test set:** tạo 50–100 câu business meeting trong `tests/evaluation/golden_set.json`, phủ các nhóm: Greeting, Company intro, Product discussion, Pricing, Delivery, Contract, Investment, Technical integration, Security, Next steps. Mỗi câu gắn nhãn entity (tên/số/ngày/currency/negative/modal verb) để đo entity preservation rate riêng.
**Noise test:** tạo/thu bộ audio với các điều kiện: clean, air_conditioner, office_noise, keyboard, background_speech, reverberation, low_volume, high_volume — đo WER/CER degradation.
**Soak test:** chạy audio liên tục 30–60 phút, theo dõi memory leak, GPU memory tăng dần, queue backlog, WebSocket disconnect, model crash, transcript duplication.
**DoD:** Toàn bộ unit + integration tests pass trong CI/local run. Golden set có script chạy batch và xuất báo cáo entity-preservation rate.

---

### Task 22 — Packaging & preflight
**`scripts/preflight.py` phải check và in rõ hành động khắc phục nếu lỗi:**
```
Python version, CUDA available, GPU memory, ASR model exists,
Translation model/API available, Microphone detected, Sample rate supported,
Web port available, Disk space, Internet connectivity (nếu cần), Local fallback loaded
```
Ví dụ output khi lỗi: `ERROR: Translation API unavailable. ACTION: Run with --profile offline.`
**Makefile target `demo`:** chạy preflight rồi `scripts/run_demo.py` (khởi động cả backend + frontend build, mở browser).
**Docker Compose:** có nhưng KHÔNG bắt buộc — phải có native run path (`python -m apps.api.main` + `npm run dev`) hoạt động song song, vì CUDA passthrough qua Docker chưa chắc test kỹ trên máy demo.
**DoD:** `make demo` chạy thành công trên máy sạch (sau khi model đã cache sẵn qua `download_models.py`).

---

### Task 23 — Demo failure playbook wiring
**Mục tiêu:** Đảm bảo các fallback trong plan thực sự hoạt động được bằng 1 hành động UI, không cần restart app.
| Sự cố | Hành động UI cần có sẵn |
|---|---|
| Mic không nhận | Dropdown chọn lại mic, không cần reload trang |
| Auto language sai | Nút chuyển Manual VI / Manual EN ngay trên UI chính |
| VAD cắt câu sai | Nút chuyển Push-to-talk |
| Cloud translation lỗi | Tự động chuyển local (Task 15), có badge hiển thị đang dùng backend nào |
| GPU lỗi | Preflight/script chuyển sang model nhỏ hơn hoặc CPU quantized qua config, không cần sửa code |
**DoD:** Diễn tập thủ công từng dòng trong bảng trên, xác nhận không dòng nào yêu cầu restart toàn bộ backend hoặc sửa code.

---

## Ghi chú cho AI coding agent
- Thực hiện task theo đúng thứ tự trong Phase 1 trước — đây là các task quyết định milestone "12:00 Day 1" (basic end-to-end: nói → thấy transcript → thấy bản dịch).
- Nếu thiếu thời gian, được phép cắt: Task 18 (basic diarization phần nice-to-have), TTS (không có task riêng — không làm), Task 21 (soak test có thể rút gọn xuống 10 phút thay vì 30-60), Task 22 Docker Compose (native run path là bắt buộc, Docker là optional).
- KHÔNG được cắt: Task 13 (validators) và Task 15 (failure handling) — đây là phần tạo khác biệt "product" so với demo AI thông thường theo đúng định hướng gốc của plan.
- Mọi model/threshold phải qua YAML config (Task 2), không hardcode trong code logic (nguyên tắc 33.1 của plan gốc).
