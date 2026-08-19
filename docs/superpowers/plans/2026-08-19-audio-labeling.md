# Audio Labeling Widgets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `AudioPlayer` and `AudioSegmentField` widgets for audio playback and timeline-based segment annotation.

**Architecture:** Two React components following the existing widget pattern (BBoxField is the closest analog). Both fetch audio via Web Audio API for waveform rendering; AudioSegmentField uses a `<canvas>` for waveform drawing, HTMLAudioElement for playback, and registers with AnnotationContext for annotation data. Widgets auto-export to template scope via `index.ts`.

**Tech Stack:** React, TypeScript, Web Audio API, Canvas, HTMLAudioElement, Tailwind CSS

---

### Task 1: AudioPlayer widget (playback-only)

**Files:**
- Create: `frontend/src/widgets/AudioPlayer.tsx`
- Modify: `frontend/src/widgets/index.ts`
- Modify: `frontend/src/components/WidgetDocs.tsx`

- [ ] **Step 1: Create AudioPlayer.tsx**

```tsx
import { useEffect, useRef, useState } from 'react';

interface Props {
  url: string;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function AudioPlayer({ url }: Props) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    const onTime = () => setCurrentTime(audio.currentTime);
    const onLoaded = () => setDuration(audio.duration);
    audio.addEventListener('play', onPlay);
    audio.addEventListener('pause', onPause);
    audio.addEventListener('timeupdate', onTime);
    audio.addEventListener('loadedmetadata', onLoaded);
    return () => {
      audio.removeEventListener('play', onPlay);
      audio.removeEventListener('pause', onPause);
      audio.removeEventListener('timeupdate', onTime);
      audio.removeEventListener('loadedmetadata', onLoaded);
    };
  }, []);

  useEffect(() => {
    setPlaying(false);
    setCurrentTime(0);
    setDuration(0);
  }, [url]);

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) { audio.pause(); } else { audio.play(); }
  };

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    const audio = audioRef.current;
    if (!audio || !duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const frac = (e.clientX - rect.left) / rect.width;
    audio.currentTime = frac * duration;
  };

  const pct = duration ? (currentTime / duration) * 100 : 0;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0' }}>
      <audio ref={audioRef} src={url} preload="auto" />
      <button onClick={togglePlay}
              style={{
                width: 32, height: 32, borderRadius: '50%', border: 'none', cursor: 'pointer',
                background: 'linear-gradient(135deg, #F97316, #EC4899)', color: '#fff',
                fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
              }}>
        {playing ? '⏸' : '▶'}
      </button>
      <div onClick={handleSeek}
           style={{
             flex: 1, height: 6, background: '#e5e7eb', borderRadius: 3, cursor: 'pointer',
             position: 'relative',
           }}>
        <div style={{
          width: `${pct}%`, height: '100%',
          background: 'linear-gradient(90deg, #F97316, #EC4899)', borderRadius: 3,
        }} />
        <div style={{
          position: 'absolute', left: `${pct}%`, top: -3,
          width: 12, height: 12, borderRadius: '50%',
          background: '#F97316', border: '2px solid #fff',
          boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
          transform: 'translateX(-50%)',
        }} />
      </div>
      <span style={{ fontSize: 12, color: '#374151', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', flexShrink: 0 }}>
        {formatTime(currentTime)} / {formatTime(duration)}
      </span>
    </div>
  );
}
```

- [ ] **Step 2: Export in index.ts**

Edit `frontend/src/widgets/index.ts` — add the two new exports:

```ts
export { default as AudioPlayer } from './AudioPlayer';
export { default as AudioSegmentField } from './AudioSegmentField';
```

- [ ] **Step 3: Add widget docs in WidgetDocs.tsx**

Add to the `WIDGETS` array in `frontend/src/components/WidgetDocs.tsx`, after the BBoxField entry (before the closing `]`):

```ts
  {
    name: 'AudioPlayer',
    description: 'Simple audio playback — play, pause, seek.',
    props: [
      { name: 'url', type: 'string', required: true, desc: 'URL to the audio file.' },
    ],
  },
  {
    name: 'AudioSegmentField',
    description: 'Timeline-based segment labeling on audio waveform.',
    props: [
      { name: 'name', type: 'string', required: true, desc: 'Field key stored in annotations.' },
      { name: 'url', type: 'string', required: true, desc: 'URL to the audio file.' },
      { name: 'labels', type: 'string[]', required: true, desc: 'Category labels, e.g. ["speaker_a","music"].' },
      { name: 'colors', type: 'string[]', desc: 'Override category colors (CSS color strings).' },
      { name: 'defaultValue', type: 'Segment[]', desc: 'Pre-existing segments [{start,end,label}].' },
    ],
  },
```

- [ ] **Step 4: Verify frontend compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/widgets/AudioPlayer.tsx frontend/src/widgets/index.ts frontend/src/components/WidgetDocs.tsx
git commit -m "feat: add AudioPlayer widget"
```

---

### Task 2: AudioSegmentField — audio decode utility & waveform canvas

**Files:**
- Create: `frontend/src/widgets/AudioSegmentField.tsx`

- [ ] **Step 1: Create initial file with Segment types, decode utility, and waveform canvas shell**

Add the complete audio decode + waveform compute logic:

```tsx
import { useEffect, useRef, useState } from 'react';
import { useAnnotationContext } from '../context/AnnotationContext';

interface Segment {
  start: number;
  end: number;
  label: string;
}

interface Props {
  name: string;
  url: string;
  labels: string[];
  colors?: string[];
  defaultValue?: Segment[];
}

const DEFAULT_COLORS = ['#F97316', '#3b82f6', '#10b981', '#8b5cf6', '#e74c3c', '#f39c12'];

function getColor(label: string, colors: string[]): string {
  let hash = 0;
  for (let i = 0; i < label.length; i++) hash = label.charCodeAt(i) + ((hash << 5) - hash);
  return colors[Math.abs(hash) % colors.length];
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

async function decodeAudio(url: string): Promise<{ duration: number; waveform: number[] }> {
  const res = await fetch(url);
  const buffer = await res.arrayBuffer();
  const ctx = new AudioContext();
  const audioBuffer = await ctx.decodeAudioData(buffer);
  ctx.close();
  const { duration, numberOfChannels, sampleRate } = audioBuffer;
  const numBars = 300;
  const waveform: number[] = [];
  const channelData = audioBuffer.getChannelData(0);
  const samplesPerBar = Math.floor(channelData.length / numBars);
  for (let i = 0; i < numBars; i++) {
    let peak = 0;
    const start = i * samplesPerBar;
    const end = Math.min(start + samplesPerBar, channelData.length);
    for (let j = start; j < end; j++) {
      const abs = Math.abs(channelData[j]);
      if (abs > peak) peak = abs;
    }
    waveform.push(peak);
  }
  return { duration, waveform };
}
```

Then add the component scaffold with waveform canvas, label chips, segment state, playhead, and a simple canvas render:

```tsx
export default function AudioSegmentField({ name, url, labels, colors: colorOverride, defaultValue }: Props) {
  const colors = colorOverride || DEFAULT_COLORS;
  const [segments, setSegments] = useState<Segment[]>(defaultValue || []);
  const [activeLabel, setActiveLabel] = useState(labels[0]);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [waveform, setWaveform] = useState<number[]>([]);
  const [playing, setPlaying] = useState(false);
  const [playSegmentOnly, setPlaySegmentOnly] = useState<Segment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<'range' | 'point'>('range');
  const audioRef = useRef<HTMLAudioElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { registerField, unregisterField } = useAnnotationContext();

  // -- drawing state for creating/editing segments (next task)
  const [drawing, setDrawing] = useState(false);
  const [drawStart, setDrawStart] = useState(0);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOffset, setDragOffset] = useState(0);
  const [resizeSide, setResizeSide] = useState<'left' | 'right' | null>(null);
  const [resizeIndex, setResizeIndex] = useState<number | null>(null);

  useEffect(() => {
    if (defaultValue !== undefined) setSegments(defaultValue);
  }, [defaultValue]);

  useEffect(() => {
    registerField({ name, getValue: () => segments });
    return () => unregisterField(name);
  }, [name, segments]);

  // -- decode audio on url change
  useEffect(() => {
    setWaveform([]);
    setDuration(0);
    setCurrentTime(0);
    setPlaying(false);
    setError(null);
    decodeAudio(url).then(({ duration: d, waveform: w }) => {
      setDuration(d);
      setWaveform(w);
    }).catch((e) => {
      setError(`Failed to decode audio: ${e.message}`);
    });
  }, [url]);

  // -- draw waveform canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || waveform.length === 0) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const w = rect.width;
    const h = rect.height;
    const mid = h / 2;

    ctx.clearRect(0, 0, w, h);

    // background
    ctx.fillStyle = '#f3f4f6';
    ctx.fillRect(0, 0, w, h);

    // waveform bars
    const barWidth = 2;
    const gap = 1;
    const step = barWidth + gap;
    const totalBars = Math.floor(w / step);
    for (let i = 0; i < Math.min(totalBars, waveform.length); i++) {
      const barH = waveform[i] * mid * 0.9;
      const x = i * step + gap;
      ctx.fillStyle = '#9ca3af';
      ctx.fillRect(x, mid - barH, barWidth, barH * 2);
    }

    // segment overlays
    for (const seg of segments) {
      const sx = (seg.start / duration) * w;
      const ex = (seg.end / duration) * w;
      const color = getColor(seg.label, colors);
      ctx.fillStyle = color + '1A'; // 10% opacity
      ctx.fillRect(sx, 0, ex - sx, h);
      // left border (extends below by 6px)
      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(sx, 0);
      ctx.lineTo(sx, h + 6);
      ctx.stroke();
      // right border
      ctx.beginPath();
      ctx.moveTo(ex, 0);
      ctx.lineTo(ex, h + 6);
      ctx.stroke();
    }

    // playhead (extends outside by 6px on both ends)
    if (duration) {
      const px = (currentTime / duration) * w;
      ctx.strokeStyle = '#EA580C';
      ctx.lineWidth = 3;
      ctx.shadowColor = 'rgba(234,88,12,0.4)';
      ctx.shadowBlur = 4;
      ctx.beginPath();
      ctx.moveTo(px, -6);
      ctx.lineTo(px, h + 6);
      ctx.stroke();
      ctx.shadowBlur = 0;
      // circle knob
      ctx.beginPath();
      ctx.arc(px, -6, 5.5, 0, Math.PI * 2);
      ctx.fillStyle = '#EA580C';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  }, [waveform, duration, segments, currentTime, colors]);

  return (
    <div ref={containerRef} style={{ userSelect: 'none' }}>
      <audio ref={audioRef} src={url} preload="auto"
             onTimeUpdate={() => {
               if (audioRef.current) {
                 setCurrentTime(audioRef.current.currentTime);
                 if (playSegmentOnly && audioRef.current.currentTime >= playSegmentOnly.end) {
                   audioRef.current.pause();
                   setPlaySegmentOnly(null);
                 }
               }
             }}
             onLoadedMetadata={() => { if (audioRef.current) setDuration(audioRef.current.duration); }}
      />

      {/* Label chips */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}>
        {labels.map((label) => {
          const active = activeLabel === label;
          const c = getColor(label, colors);
          return (
            <button key={label} onClick={() => setActiveLabel(label)}
                    style={{
                      padding: '3px 10px', borderRadius: 12, fontSize: 11, fontWeight: 600,
                      border: 'none', cursor: 'pointer',
                      background: active ? c : '#e5e7eb',
                      color: active ? '#fff' : '#374151',
                    }}>
              {label}
            </button>
          );
        })}
        {/* Range/Point toggle */}
        <div style={{ marginLeft: 'auto', display: 'flex', borderRadius: 6, overflow: 'hidden', border: '1px solid #e5e7eb' }}>
          <button onClick={() => setMode('range')}
                  style={{
                    padding: '3px 8px', fontSize: 10, border: 'none', cursor: 'pointer',
                    background: mode === 'range' ? '#F97316' : '#fff',
                    color: mode === 'range' ? '#fff' : '#374151',
                  }}>
            Range
          </button>
          <button onClick={() => setMode('point')}
                  style={{
                    padding: '3px 8px', fontSize: 10, border: 'none', cursor: 'pointer',
                    background: mode === 'point' ? '#F97316' : '#fff',
                    color: mode === 'point' ? '#fff' : '#374151',
                  }}>
            Point
          </button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div style={{ padding: 16, textAlign: 'center', color: '#dc2626', fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* Waveform canvas */}
      {!error && (
        <div style={{ position: 'relative' }}>
          <canvas ref={canvasRef}
                  style={{ width: '100%', height: 80, display: 'block', borderRadius: 6 }}
          />
        </div>
      )}

      {/* Time labels */}
      {!error && (
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#6b7280', margin: '4px 0 8px' }}>
          <span>{formatTime(0)}</span>
          <span>{formatTime(duration * 0.25)}</span>
          <span>{formatTime(duration * 0.5)}</span>
          <span>{formatTime(duration * 0.75)}</span>
          <span>{formatTime(duration)}</span>
        </div>
      )}

      {/* Playback controls */}
      {!error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <button onClick={() => {
            const audio = audioRef.current;
            if (!audio) return;
            if (playing) { audio.pause(); } else { audio.play(); }
          }}
                  style={{
                    width: 32, height: 32, borderRadius: '50%', border: 'none', cursor: 'pointer',
                    background: 'linear-gradient(135deg, #F97316, #EC4899)', color: '#fff',
                    fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    flexShrink: 0,
                  }}>
            {playing ? '⏸' : '▶'}
          </button>
          <span style={{ fontSize: 12, color: '#374151', fontVariantNumeric: 'tabular-nums' }}>
            {formatTime(currentTime)} / {formatTime(duration)}
          </span>
          {playSegmentOnly && (
            <span style={{ fontSize: 11, padding: '3px 8px', borderRadius: 4, background: '#fef3c7', color: '#92400e' }}>
              Playing segment: {playSegmentOnly.label}
            </span>
          )}
        </div>
      )}

      {/* Segment list */}
      {segments.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {segments.map((seg, i) => {
            const c = getColor(seg.label, colors);
            const isPoint = seg.start === seg.end;
            return (
              <div key={i}
                   style={{
                     display: 'flex', alignItems: 'center', gap: 8, fontSize: 12,
                     background: '#f9fafb', padding: '5px 8px', borderRadius: 4, cursor: 'pointer',
                   }}
                   onClick={() => {
                     if (audioRef.current) {
                       audioRef.current.currentTime = seg.start;
                       audioRef.current.play();
                       setPlaySegmentOnly(seg);
                     }
                   }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: c, flexShrink: 0 }} />
                <span style={{ flex: 1, fontVariantNumeric: 'tabular-nums' }}>
                  {isPoint ? `@ ${formatTime(seg.start)}` : `${formatTime(seg.start)} – ${formatTime(seg.end)}`}
                </span>
                <span style={{ fontWeight: 600, color: c }}>{seg.label}</span>
                <span style={{ fontSize: 10, color: '#9ca3af', cursor: 'pointer' }}>▶</span>
                <span style={{ fontSize: 10, color: '#9ca3af', cursor: 'pointer' }}
                      onClick={(e) => { e.stopPropagation(); setSegments(prev => prev.filter((_, j) => j !== i)); }}>
                  ✕
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Empty state */}
      {segments.length === 0 && !error && (
        <div style={{ textAlign: 'center', padding: 12, color: '#9ca3af', fontSize: 12 }}>
          {mode === 'range' ? 'Click and drag on waveform to create a labeled segment' : 'Click on waveform to place a labeled point'}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify frontend compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/widgets/AudioSegmentField.tsx
git commit -m "feat: add AudioSegmentField widget (waveform canvas, decode, playback, label chips, segment list)"
```

---

### Task 3: AudioSegmentField — waveform interaction (create, resize, drag segments)

**Files:**
- Modify: `frontend/src/widgets/AudioSegmentField.tsx`

Add mouse handlers for the waveform canvas. Add these handlers inside the component (before the return statement):

- [ ] **Step 1: Add canvas mouse-down/move/up handlers**

Add between the canvas draw `useEffect` and the `return`:

```tsx
  // -- convert mouse position to time
  const mouseToTime = (clientX: number): number => {
    const canvas = canvasRef.current;
    if (!canvas || !duration) return 0;
    const rect = canvas.getBoundingClientRect();
    const frac = (clientX - rect.left) / rect.width;
    return Math.max(0, Math.min(duration, frac * duration));
  };

  const handleCanvasMouseDown = (e: React.MouseEvent) => {
    const t = mouseToTime(e.clientX);
    // check if clicking on existing segment edge
    for (let i = 0; i < segments.length; i++) {
      const seg = segments[i];
      const xf = (e.clientX - canvasRef.current!.getBoundingClientRect().left) / canvasRef.current!.getBoundingClientRect().width;
      const sx = seg.start / duration;
      const ex = seg.end / duration;
      const x = xf;
      const edgeThreshold = 8 / canvasRef.current!.getBoundingClientRect().width;
      if (Math.abs(x - sx) < edgeThreshold) {
        setResizeIndex(i);
        setResizeSide('left');
        return;
      }
      if (Math.abs(x - ex) < edgeThreshold) {
        setResizeIndex(i);
        setResizeSide('right');
        return;
      }
      if (x >= sx && x <= ex) {
        setDragIndex(i);
        setDragOffset(t - seg.start);
        return;
      }
    }
    // start drawing a new segment (range) or place point
    if (mode === 'point') {
      setSegments(prev => [...prev, { start: t, end: t, label: activeLabel }]);
    } else {
      setDrawing(true);
      setDrawStart(t);
    }
  };

  // document-level mousemove/mouseup
  useEffect(() => {
    if (!drawing && dragIndex === null && resizeIndex === null) return;

    const handleMouseMove = (e: MouseEvent) => {
      const t = mouseToTime(e.clientX);

      if (drawing) {
        // Remove any existing in-progress "drawing" segment and replace with current
        setSegments(prev => {
          const withoutDrawing = prev.filter(s => s.start !== -1 || s.end !== -1);
          const start = Math.min(drawStart, t);
          const end = Math.max(drawStart, t);
          if (end - start < 0.05) return prev; // too small
          return [...withoutDrawing, { start, end, label: activeLabel }];
        });
        return;
      }

      if (dragIndex !== null) {
        const seg = segments[dragIndex];
        const span = seg.end - seg.start;
        let newStart = t - dragOffset;
        newStart = Math.max(0, Math.min(duration - span, newStart));
        setSegments(prev => {
          const next = [...prev];
          next[dragIndex] = { ...next[dragIndex], start: newStart, end: newStart + span };
          return next;
        });
        return;
      }

      if (resizeIndex !== null) {
        setSegments(prev => {
          const next = [...prev];
          const seg = { ...next[resizeIndex] };
          if (resizeSide === 'left') {
            seg.start = Math.max(0, Math.min(seg.end - 0.05, t));
          } else {
            seg.end = Math.min(duration, Math.max(seg.start + 0.05, t));
          }
          next[resizeIndex] = seg;
          return next;
        });
      }
    };

    const handleMouseUp = () => {
      // remove zero-width drawing segments
      setSegments(prev => prev.filter(s => s.end - s.start >= 0.05));
      setDrawing(false);
      setDragIndex(null);
      setResizeIndex(null);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [drawing, dragIndex, resizeIndex, resizeSide, drawStart, activeLabel, duration, segments, mouseToTime]);

  // need mouseToTime as a ref to avoid stale closure
  const mouseToTimeRef = useRef(mouseToTime);
  mouseToTimeRef.current = mouseToTime;
```

Also add `onMouseDown={handleCanvasMouseDown}` to the `<canvas>` element in the JSX:

Edit the canvas JSX to add `onMouseDown`:
```tsx
          <canvas ref={canvasRef}
                  onMouseDown={handleCanvasMouseDown}
                  style={{ width: '100%', height: 80, display: 'block', borderRadius: 6, cursor: 'crosshair' }}
          />
```

- [ ] **Step 2: Verify frontend compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/widgets/AudioSegmentField.tsx
git commit -m "feat: add waveform interaction (create, drag, resize segments)"
```

---

### Task 4: Build, run & verify

**Files:** None (verification only)

- [ ] **Step 1: Build frontend**

Run: `cd frontend && npm run build 2>&1`
Expected: Build succeeds (may show chunk size warnings, ignore those)

- [ ] **Step 2: Commit final**

```bash
git commit -am "feat: add audio labeling widgets (AudioPlayer + AudioSegmentField)"
```
