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
