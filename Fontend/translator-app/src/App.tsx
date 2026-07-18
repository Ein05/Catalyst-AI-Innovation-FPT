import { useEffect, useMemo, useRef, useState } from 'react';

type SessionMode = 'auto' | 'manual_vi' | 'manual_en' | 'seat_a' | 'seat_b';
type TranscriptState =
  | 'Idle'
  | 'Listening'
  | 'Transcribing'
  | 'Final'
  | 'Translating'
  | 'Completed'
  | 'Error';

type ServerEvent = {
  event: string;
  session_id: string;
  utterance_id?: string;
  revision: number;
  payload: Record<string, unknown>;
};

const SESSION_ID = `meeting-${Date.now()}`;

function normalizeBaseUrl(value: string) {
  return value.replace(/\/$/, '');
}

function getApiUrl(path: string) {
  const explicit = import.meta.env.VITE_API_URL as string | undefined;
  if (explicit) return `${normalizeBaseUrl(explicit)}${path}`;
  return path;
}

function getWsUrl() {
  const explicit = import.meta.env.VITE_WS_URL as string | undefined;
  const apiUrl = import.meta.env.VITE_API_URL as string | undefined;
  const base = explicit || apiUrl;
  if (base) {
    const normalized = normalizeBaseUrl(base)
      .replace(/^https:\/\//, 'wss://')
      .replace(/^http:\/\//, 'ws://');
    return normalized.endsWith('/ws') ? normalized : `${normalized}/ws`;
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws`;
}

export default function App() {
  const [mode, setMode] = useState<SessionMode>('auto');
  const [status, setStatus] = useState<TranscriptState>('Idle');
  const [connection, setConnection] = useState<'disconnected' | 'connecting' | 'connected'>(
    'disconnected',
  );
  const [backendOnline, setBackendOnline] = useState(false);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedMic, setSelectedMic] = useState('');
  const [originalText, setOriginalText] = useState('');
  const [translatedText, setTranslatedText] = useState('');
  const [warnings, setWarnings] = useState<string[]>([]);
  const [level, setLevel] = useState(0);
  const [sequence, setSequence] = useState(0);
  const [error, setError] = useState('');

  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const sessionStartedRef = useRef(false);
  const sequenceRef = useRef(0);

  const providerBadge = useMemo(() => {
    if (connection === 'connected') return warnings.length ? 'CHECK WARNINGS' : 'SESSION LIVE';
    if (backendOnline) return 'BACKEND ONLINE';
    return 'BACKEND OFFLINE';
  }, [backendOnline, connection, warnings.length]);

  useEffect(() => {
    fetch(getApiUrl('/health'))
      .then((response) => setBackendOnline(response.ok))
      .catch(() => setBackendOnline(false));

    navigator.mediaDevices
      ?.enumerateDevices()
      .then((items) => {
        const audioInputs = items.filter((device) => device.kind === 'audioinput');
        setDevices(audioInputs);
        setSelectedMic(audioInputs[0]?.deviceId ?? '');
      })
      .catch((err: unknown) => setError(`Cannot list microphones: ${String(err)}`));

    return () => {
      stopAudio();
      wsRef.current?.close();
    };
  }, []);

  function sendJson(payload: Record<string, unknown>) {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
    }
  }

  async function startMeeting(nextMode = mode) {
    setError('');
    setStatus('Listening');
    setConnection('connecting');

    const ws = new WebSocket(getWsUrl());
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;

    ws.onopen = async () => {
      setConnection('connected');
      sendJson({ type: 'session.start', session_id: SESSION_ID, mode: nextMode });
      sessionStartedRef.current = true;
      await startAudio();
    };

    ws.onmessage = (message) => {
      const event = JSON.parse(message.data) as ServerEvent;
      handleServerEvent(event);
    };

    ws.onerror = () => {
      setStatus('Error');
      setConnection('disconnected');
      setError('WebSocket connection failed. Check backend or tunnel.');
    };

    ws.onclose = () => {
      setConnection('disconnected');
      setStatus((current) => (current === 'Error' ? current : 'Idle'));
      sessionStartedRef.current = false;
    };
  }

  function endMeeting() {
    sendJson({ type: 'session.end', session_id: SESSION_ID });
    stopAudio();
    wsRef.current?.close();
    setStatus('Idle');
  }

  function changeMode(nextMode: SessionMode) {
    setMode(nextMode);
    sendJson({ type: 'session.set_mode', session_id: SESSION_ID, mode: nextMode });
  }

  function handleMicChange(deviceId: string) {
    setSelectedMic(deviceId);
    sendJson({ type: 'mic.select', device_id: deviceId });
    if (sessionStartedRef.current) {
      void restartAudio(deviceId);
    }
  }

  async function restartAudio(deviceId: string) {
    stopAudio();
    await startAudio(deviceId);
  }

  async function startAudio(deviceId = selectedMic) {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: deviceId ? { deviceId: { exact: deviceId } } : true,
    });
    streamRef.current = stream;

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    const audioContext = new AudioContextClass();
    audioContextRef.current = audioContext;
    await audioContext.audioWorklet.addModule('/audio-processor.js');

    const source = audioContext.createMediaStreamSource(stream);
    const worklet = new AudioWorkletNode(audioContext, 'audio-processor');
    source.connect(worklet);
    worklet.connect(audioContext.destination);

    sourceRef.current = source;
    workletRef.current = worklet;

    worklet.port.onmessage = (message) => {
      const pcm = message.data as ArrayBuffer;
      const view = new Int16Array(pcm);
      let peak = 0;
      for (const sample of view) peak = Math.max(peak, Math.abs(sample) / 32768);
      setLevel(peak);

      if (wsRef.current?.readyState !== WebSocket.OPEN) return;
      const nextSequence = sequenceRef.current + 1;
      sequenceRef.current = nextSequence;
      setSequence(nextSequence);
      sendJson({
        type: 'audio.chunk_meta',
        session_id: SESSION_ID,
        sequence: nextSequence,
        timestamp_ms: Math.round(performance.now()),
        sample_rate: audioContext.sampleRate,
        channels: 1,
        byte_length: pcm.byteLength,
      });
      wsRef.current.send(pcm);
    };
  }

  function stopAudio() {
    workletRef.current?.disconnect();
    sourceRef.current?.disconnect();
    void audioContextRef.current?.close();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    workletRef.current = null;
    sourceRef.current = null;
    audioContextRef.current = null;
    streamRef.current = null;
    setLevel(0);
  }

  function handleServerEvent(event: ServerEvent) {
    if (event.event === 'session.status') {
      return;
    }
    if (event.event === 'audio.received') {
      setStatus('Listening');
      return;
    }
    if (event.event === 'asr.final') {
      setStatus('Final');
      const finalText = event.payload.final_text;
      if (typeof finalText === 'string') setOriginalText(finalText);
      return;
    }
    if (event.event === 'translation.started') {
      setStatus('Translating');
      return;
    }
    if (event.event === 'translation.completed') {
      setStatus('Completed');
      const translation = event.payload.translation;
      const eventWarnings = event.payload.warnings;
      if (typeof translation === 'string') setTranslatedText(translation);
      if (Array.isArray(eventWarnings)) setWarnings(eventWarnings.map(String));
      return;
    }
    if (event.event === 'error') {
      setStatus('Error');
      setError(String(event.payload.message ?? 'Backend error'));
    }
  }

  const isRunning = connection === 'connected';
  const clipping = level > 0.92;
  const muted = isRunning && level < 0.01;

  return (
    <div className="min-h-screen flex flex-col p-6 md:p-10 gap-6 max-w-[var(--page-max)] mx-auto">
      <header className="flex flex-wrap items-center justify-between gap-4 card p-4 md:px-6 border-b-4 border-b-emerald-200">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Meeting Translator</h1>
          <span className="eyebrow inline-block mt-1">
            {connection} · {status} · seq {sequence}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-sm font-medium">
          <select
            className="bg-transparent border-2 border-[var(--color-paper-3)] rounded-lg px-3 py-2 outline-none focus:border-[var(--color-accent)]"
            value={selectedMic}
            onChange={(event) => handleMicChange(event.target.value)}
          >
            <option value="">Default Microphone</option>
            {devices.map((device) => (
              <option key={device.deviceId} value={device.deviceId}>
                {device.label || 'Microphone'}
              </option>
            ))}
          </select>

          <div className="bg-[var(--color-paper-2)] p-1 rounded-xl flex gap-1">
            {(['auto', 'manual_vi', 'manual_en'] as const).map((item) => (
              <button
                key={item}
                onClick={() => changeMode(item)}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  mode === item ? 'bg-white shadow-sm font-semibold' : 'hover:bg-black/5'
                }`}
              >
                {item === 'auto' ? 'Auto' : item === 'manual_vi' ? 'VI' : 'EN'}
              </button>
            ))}
          </div>
        </div>
      </header>

      {error && (
        <div className="rounded-lg bg-red-100 text-red-900 px-4 py-3 text-sm font-medium">{error}</div>
      )}

      <div className="card p-4 flex items-center gap-4">
        <span className="eyebrow w-24">Mic Level</span>
        <div className="h-3 flex-1 rounded-full bg-[var(--color-paper-3)] overflow-hidden">
          <div
            className={`h-full ${clipping ? 'bg-red-500' : 'bg-emerald-500'}`}
            style={{ width: `${Math.round(level * 100)}%` }}
          />
        </div>
        <span className="eyebrow w-36 text-right">
          {clipping ? 'Clipping' : muted ? 'Muted?' : providerBadge}
        </span>
      </div>

      <main className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-6">
        <section className="card flex flex-col overflow-hidden relative">
          <div className="bg-[var(--color-paper-2)] px-6 py-4 flex items-center justify-between">
            <span className="eyebrow">Original</span>
            <span className="eyebrow">{mode}</span>
          </div>
          <div className="p-8 flex-1 text-2xl md:text-3xl font-medium leading-relaxed">
            {originalText || <span className="opacity-40 italic">Waiting for speech...</span>}
          </div>
        </section>

        <section className="card flex flex-col overflow-hidden relative">
          <div className="bg-[var(--color-paper-3)] px-6 py-4 flex items-center justify-between">
            <span className="eyebrow text-[var(--color-accent-deep)]">Translation</span>
            <div className="text-xs bg-[var(--color-paper)] px-2 py-1 rounded-md text-[var(--color-ink-2)] font-mono">
              {providerBadge}
            </div>
          </div>
          <div className="p-8 flex-1 text-2xl md:text-3xl font-medium leading-relaxed text-[var(--color-accent-deep)]">
            {translatedText || <span className="opacity-40 italic">Translation will appear here...</span>}
          </div>
          {warnings.length > 0 && (
            <div className="px-6 py-3 bg-yellow-100 text-yellow-900 text-sm">
              {warnings.join(' · ')}
            </div>
          )}
        </section>
      </main>

      <footer className="flex flex-wrap items-center justify-between gap-4 py-4 border-t-2 border-[var(--color-paper-2)]">
        <div className="flex gap-3">
          <button className="btn btn--soft" onClick={() => sendJson({ type: 'turn.end', session_id: SESSION_ID })}>
            End Turn
          </button>
          <button
            className="btn btn--soft"
            onClick={() => {
              setOriginalText('');
              setTranslatedText('');
              setWarnings([]);
            }}
          >
            Clear
          </button>
        </div>

        <div className="flex gap-3">
          <button
            className="btn"
            disabled={!isRunning}
            onMouseDown={() => changeMode('manual_vi')}
            onMouseUp={() => changeMode('auto')}
          >
            <span className="hl">Hold to Speak VI</span>
          </button>
          <button
            className="btn"
            disabled={!isRunning}
            onMouseDown={() => changeMode('manual_en')}
            onMouseUp={() => changeMode('auto')}
            style={{ '--color-accent': 'var(--color-accent-2)' } as React.CSSProperties}
          >
            <span className="hl">Hold to Speak EN</span>
          </button>
        </div>

        <div className="flex gap-3">
          {!isRunning ? (
            <button className="btn" onClick={() => void startMeeting()}>
              Start Meeting
            </button>
          ) : (
            <button className="btn" onClick={endMeeting} style={{ '--color-accent': 'var(--color-accent-3)' } as React.CSSProperties}>
              End Meeting
            </button>
          )}
        </div>
      </footer>
    </div>
  );
}

declare global {
  interface Window {
    webkitAudioContext?: typeof AudioContext;
  }
}
