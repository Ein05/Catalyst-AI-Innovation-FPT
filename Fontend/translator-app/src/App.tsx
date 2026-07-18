import React, { useState, useEffect } from 'react';

// Types for the translator state
type SessionMode = 'auto' | 'manual_vi' | 'manual_en' | 'seat_a' | 'seat_b';
type TranscriptState = 'Listening' | 'Transcribing' | 'Partial' | 'Final' | 'Translating' | 'Completed' | 'Error';

export default function App() {
  const [mode, setMode] = useState<SessionMode>('auto');
  const [status] = useState<TranscriptState>('Listening');
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedMic, setSelectedMic] = useState<string>('');
  
  // Dummy transcripts for UI demonstration
  const [originalText] = useState('Xin chào, đây là bản ghi nháp thử nghiệm giao diện.');
  const [translatedText] = useState('Hello, this is a draft recording to test the interface.');

  useEffect(() => {
    // Mock device fetching
    navigator.mediaDevices?.enumerateDevices().then(devices => {
      const audioInputs = devices.filter(d => d.kind === 'audioinput');
      setDevices(audioInputs);
      if (audioInputs.length > 0) {
        setSelectedMic(audioInputs[0].deviceId);
      }
    }).catch(err => console.error("Could not get media devices", err));
  }, []);

  return (
    <div className="min-h-screen flex flex-col p-8 md:p-12 gap-8 max-w-[var(--page-max)] mx-auto">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-4 card p-4 md:px-8 border-b-4 border-b-emerald-200" style={{ '--color-accent': 'var(--color-mint)' } as React.CSSProperties}>
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 bg-[var(--color-accent)] rounded-full flex items-center justify-center text-2xl animate-pulse">
            ✨
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">Meeting Translator</h1>
            <span className="eyebrow inline-block mt-1">Status: <span className="text-[var(--color-accent-deep)]">{status}</span></span>
          </div>
        </div>
        
        <div className="flex items-center gap-4 text-sm font-medium">
          <select 
            className="bg-transparent border-2 border-[var(--color-paper-3)] rounded-lg px-3 py-2 outline-none focus:border-[var(--color-accent)]"
            value={selectedMic}
            onChange={(e) => setSelectedMic(e.target.value)}
          >
            <option value="">Default Microphone</option>
            {devices.map(d => (
              <option key={d.deviceId} value={d.deviceId}>{d.label || 'Unknown Device'}</option>
            ))}
          </select>
          
          <div className="bg-[var(--color-paper-2)] p-1 rounded-xl flex gap-1">
            <button onClick={() => setMode('auto')} className={`px-4 py-2 rounded-lg transition-colors ${mode === 'auto' ? 'bg-white shadow-sm font-semibold' : 'hover:bg-black/5'}`}>Auto</button>
            <button onClick={() => setMode('manual_vi')} className={`px-4 py-2 rounded-lg transition-colors ${mode === 'manual_vi' ? 'bg-white shadow-sm font-semibold' : 'hover:bg-black/5'}`}>VI</button>
            <button onClick={() => setMode('manual_en')} className={`px-4 py-2 rounded-lg transition-colors ${mode === 'manual_en' ? 'bg-white shadow-sm font-semibold' : 'hover:bg-black/5'}`}>EN</button>
          </div>
        </div>
      </header>

      {/* Main Workspace: 2 Columns */}
      <main className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Original Column */}
        <section className="card flex flex-col overflow-hidden relative">
          <div className="bg-[var(--color-paper-2)] px-6 py-4 flex items-center justify-between">
            <span className="eyebrow">Original (VI)</span>
            <span className="flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-3 w-3 rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
            </span>
          </div>
          <div className="p-8 flex-1 text-2xl md:text-3xl font-medium leading-relaxed">
            {originalText}
            <span className="opacity-40 italic ml-2">đang lắng nghe...</span>
          </div>
          {/* Decorative highlight */}
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-[var(--color-accent)] opacity-20"></div>
        </section>

        {/* Translation Column */}
        <section className="card flex flex-col overflow-hidden relative" style={{ '--color-paper': 'var(--color-paper-2)', '--color-accent': 'var(--color-accent-2)' } as React.CSSProperties}>
          <div className="bg-[var(--color-paper-3)] px-6 py-4 flex items-center justify-between">
            <span className="eyebrow text-[var(--color-accent-deep)]">Translation (EN)</span>
            <div className="text-xs bg-[var(--color-paper)] px-2 py-1 rounded-md text-[var(--color-ink-2)] font-mono">
              LOCAL MODEL
            </div>
          </div>
          <div className="p-8 flex-1 text-2xl md:text-3xl font-medium leading-relaxed text-[var(--color-accent-deep)]">
            {translatedText}
          </div>
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-[var(--color-accent)] opacity-20"></div>
        </section>
      </main>

      {/* Footer Controls */}
      <footer className="flex flex-wrap items-center justify-center md:justify-between gap-4 py-4 border-t-2 border-[var(--color-paper-2)]">
        <div className="flex gap-4">
          <button className="btn btn--soft">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>
            Pause
          </button>
          <button className="btn btn--soft" style={{ '--color-accent': 'var(--color-accent-3)' } as React.CSSProperties}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>
            Correct
          </button>
        </div>
        
        <div className="flex gap-4">
          <button className="btn" style={{ '--color-accent': 'var(--color-accent)' } as React.CSSProperties}>
            <span className="hl">Hold to Speak VI</span>
          </button>
          <button className="btn" style={{ '--color-accent': 'var(--color-accent-2)' } as React.CSSProperties}>
            <span className="hl" style={{ '--hl': 'var(--color-accent-deep)' } as React.CSSProperties}>Hold to Speak EN</span>
          </button>
        </div>

        <div>
          <button className="btn" style={{ '--color-accent': 'var(--color-accent-3)' } as React.CSSProperties}>
            End Meeting
          </button>
        </div>
      </footer>
    </div>
  );
}
