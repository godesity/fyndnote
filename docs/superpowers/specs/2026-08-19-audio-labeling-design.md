# Audio Labeling Widgets — Design

## Goal
Add two new annotation widgets — `AudioPlayer` for playback display, `AudioSegmentField` for timeline-based segment labeling — following the same pattern as existing widgets (register with `AnnotationContext`, return data via `getValue()`).

## Architecture

### New files
- `frontend/src/widgets/AudioPlayer.tsx` — simple playback-only widget
- `frontend/src/widgets/AudioSegmentField.tsx` — waveform + segment annotation
- `frontend/src/widgets/index.ts` — add both exports

### Shared utility (extracted into AudioSegmentField file, or separate module if needed later)
- `decodeAudio(url)` — fetches audio as ArrayBuffer, decodes via `AudioContext.decodeAudioData()`, returns `{ duration, channelData, sampleRate }`
- `computeWaveform(channelData, numBars)` — downsamples to N peak-amplitude bars (avg of both channels), returns `number[]`

## AudioPlayer

Props:
```
url: string
``` 

Renders a compact playback bar with:
- Play/pause button (▶/⏸)
- Seekable progress bar
- Current / total time display (mm:ss)
- Volume slider

Implementation:
- Owns a hidden `<audio>` element, sets `src` from `url`
- Tracks `playing`, `currentTime`, `duration` via event listeners
- No `registerField` — display-only, no annotation data

## AudioSegmentField

Props:
```
name: string
url: string
labels: string[]
colors?: string[]
defaultValue?: Segment[]
```

Segment data type:
```typescript
interface Segment {
  start: number;   // seconds from start
  end: number;     // seconds from start (== start for point annotations)
  label: string;
}
```

### Rendering (top to bottom)

1. **Label chips** — one per label, click to select active label (like BBox categories)
2. **Waveform canvas** — `<canvas>` element, full width, ~80px height
   - Background: light gray (#f3f4f6)
   - Bars: thin (~1px), 1px gap, peak amplitude per bucket, neutral gray (#9ca3af)
   - Active segments: colored overlay with 3px left/right border in label color
   - Playhead: 3px bright orange line (#EA580C), extends ~6px above and below waveform bounds
   - Top handle circle on playhead
3. **Time ruler** — 0:00, 0:30, 1:00... below waveform
4. **Playback controls** — same layout as AudioPlayer
5. **Segment list** — one row per segment, shows color dot, time range, label name, ▶ play-segment button, ✕ delete

### Waveform rendering
- On mount / `url` change: fetch audio → decode → compute waveform → draw canvas
- Cache waveform (redraw only on dimension change)
- Canvas draws bars from center out (bars grow vertically from midline)

### Interaction

Label chips are rendered as `<button>` elements so the label view's global keyboard handler picks them up — pressing **1, 2, 3...** will click the Nth button in the annotation area, setting it as the active label (same behavior as other widgets).

| Gesture | Action |
|---------|--------|
| Click-label chip | Set active label (for next created segment) |
| Click on empty waveform | Move playhead to that position |
| Click-drag on empty waveform (Range mode) | Create new segment (start=drag start, end=drag end) |
| Click on empty waveform (Point mode) | Create point annotation at click position (start=end=time) |
| Click-drag segment edge | Resize segment |
| Drag segment body | Move segment (shift start+end) |
| Click segment body (no drag) | Select segment, seek playhead |
| Click ▶ on segment row | Play from segment start to end (using `timeupdate` to pause at end) |
| Click ✕ on segment row | Delete segment |

**Range/Point mode toggle** — small segmented toggle button bar above the waveform:
- "Range" (default) — drag creates start/end segments
- "Point" — single click creates a zero-width point (shown as a thin vertical line on the waveform)

### Playback integration
- Owns a hidden `<audio>` element
- Play/pause toggles the player
- "Play segment" mode: seek to segment start, play, stop on `timeupdate` when currentTime >= segment end
- Playhead position updates from `timeupdate`, canvas redraws playhead line

### AnnotationContext integration
- `useEffect` to `registerField({ name, getValue: () => segments })` — same pattern as BBoxField
- `useEffect` to update from `defaultValue` when it changes (row navigation)

### Error handling
- Audio decode failure → show error message in waveform area
- Audio fetch failure → show error message
- Empty/zero-duration audio → show "No audio data" message

## Template usage

```jsx
{/* Just playback */}
<AudioPlayer url={data.audio_url} />

{/* Full segment labeling */}
<AudioSegmentField
  name="segments"
  url={data.audio_url}
  labels={['speaker_a', 'speaker_b', 'music', 'silence']}
  colors={['#F97316', '#3b82f6', '#10b981', '#6b7280']}
/>
```

## Out of scope (v1)
- Real-time waveform streaming (audio fully loaded on mount)
- Spectrogram / frequency visualization (amplitude waveform only)
- Multi-track / stereo split visualization
- Keyboard shortcuts beyond what the label view already provides
- Audio recording
- Export to annotation formats (already handled by existing annotation export)

## Implementation order
1. `AudioPlayer` widget (simple, no canvas)
2. `computeWaveform` utility
3. `AudioSegmentField` widget (waveform canvas + segment interaction + playback)
4. Export both in `index.ts`
5. Verify in label view
