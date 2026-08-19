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
  const duration = audioBuffer.duration;
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

  // -- drawing state for creating/editing segments
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
    }).catch((e: Error) => {
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
      ctx.fillStyle = color + '1A';
      ctx.fillRect(sx, 0, ex - sx, h);
      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(sx, 0);
      ctx.lineTo(sx, h + 6);
      ctx.stroke();
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
      ctx.beginPath();
      ctx.arc(px, -6, 5.5, 0, Math.PI * 2);
      ctx.fillStyle = '#EA580C';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  }, [waveform, duration, segments, currentTime, colors]);

  const mouseToTime = (clientX: number): number => {
    const canvas = canvasRef.current;
    if (!canvas || !duration) return 0;
    const rect = canvas.getBoundingClientRect();
    const frac = (clientX - rect.left) / rect.width;
    return Math.max(0, Math.min(duration, frac * duration));
  };

  const handleCanvasMouseDown = (e: React.MouseEvent) => {
    const t = mouseToTime(e.clientX);
    const canvas = canvasRef.current;
    if (!canvas || !duration) return;
    const rect = canvas.getBoundingClientRect();
    const xf = (e.clientX - rect.left) / rect.width;

    // check if clicking on existing segment edge
    for (let i = 0; i < segments.length; i++) {
      const seg = segments[i];
      const sx = seg.start / duration;
      const ex = seg.end / duration;
      const edgeThreshold = 8 / rect.width;
      if (Math.abs(xf - sx) < edgeThreshold) {
        setResizeIndex(i);
        setResizeSide('left');
        return;
      }
      if (Math.abs(xf - ex) < edgeThreshold) {
        setResizeIndex(i);
        setResizeSide('right');
        return;
      }
      if (xf >= sx && xf <= ex) {
        setDragIndex(i);
        setDragOffset(t - seg.start);
        return;
      }
    }

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
        setSegments(prev => {
          const filtered = prev.filter(s => s.start !== -1 || s.end !== -1);
          const start = Math.min(drawStart, t);
          const end = Math.max(drawStart, t);
          if (end - start < 0.05) return prev;
          return [...filtered, { start, end, label: activeLabel }];
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

  return (
    <div ref={containerRef} style={{ userSelect: 'none' }}>
      <audio ref={audioRef} src={url} preload="auto"
             onPlay={() => setPlaying(true)}
             onPause={() => { setPlaying(false); setPlaySegmentOnly(null); }}
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
                  onMouseDown={handleCanvasMouseDown}
                  style={{ width: '100%', height: 80, display: 'block', borderRadius: 6, cursor: 'crosshair' }}
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
                      onClick={(e: React.MouseEvent) => { e.stopPropagation(); setSegments(prev => prev.filter((_, j) => j !== i)); }}>
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
