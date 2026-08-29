import { useEffect, useState, useRef } from 'react';
import { useAnnotationContext } from '../context/AnnotationContext';

export interface Point { x: number; y: number; }
export interface Shape {
  id: string;
  category: string;
  type: 'closed' | 'open' | 'point';
  points: Point[];
}

interface Props {
  name: string;
  imageUrl: string;
  categories: string[];
  defaultValue?: Shape[];
  colors?: string[];
}

const DEFAULT_COLORS = [
  '#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6',
  '#1abc9c', '#e67e22', '#34495e', '#16a085', '#c0392b',
];

function getColor(category: string, categories: string[], colors: string[]): string {
  const idx = categories.indexOf(category);
  return colors[(idx >= 0 ? idx : 0) % colors.length];
}

function minFor(type: Shape['type']): number {
  if (type === 'point') return 1;
  return type === 'closed' ? 3 : 2;
}

let idCounter = 0;
function makeId(): string {
  idCounter += 1;
  return `poly-${Date.now().toString(36)}-${idCounter}`;
}

export default function PolygonField({ name, imageUrl, categories, defaultValue, colors: colorOverride }: Props) {
  const colors = colorOverride || DEFAULT_COLORS;
  const [shapes, setShapes] = useState<Shape[]>(defaultValue || []);
  const [activeCategory, setActiveCategory] = useState<string>(categories[0]);
  const [mode, setMode] = useState<'closed' | 'open' | 'point'>('closed');
  const [draft, setDraft] = useState<Point[]>([]);
  const [cursor, setCursor] = useState<Point | null>(null);
  const [drag, setDrag] = useState<{ shapeId: string; kind: 'vertex' | 'shape'; pointIndex?: number; offset: Point } | null>(null);
  const [showLabels, setShowLabels] = useState(true);
  const imgRef = useRef<HTMLDivElement>(null);
  const clickTimer = useRef<number | null>(null);
  const { registerField, unregisterField } = useAnnotationContext();

  useEffect(() => {
    if (defaultValue !== undefined) setShapes(defaultValue);
  }, [defaultValue]);

  useEffect(() => {
    registerField({ name, getValue: () => shapes });
    return () => unregisterField(name);
  }, [name, shapes]);

  // Enter finishes a draft shape.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Enter') finishShape();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  // Document-level drag listeners for vertex move / whole-shape move.
  useEffect(() => {
    if (!drag) return;
    const handleMove = (e: MouseEvent) => {
      const rect = imgRef.current!.getBoundingClientRect();
      const cur = { x: (e.clientX - rect.left) / rect.width, y: (e.clientY - rect.top) / rect.height };
      setShapes((prev) => {
        const idx = prev.findIndex((s) => s.id === drag.shapeId);
        if (idx < 0) return prev;
        return prev.map((s, i) => {
          if (i !== idx) return s;
          if (drag.kind === 'vertex' && drag.pointIndex !== undefined) {
            const pts = s.points.map((p, j) =>
              j === drag.pointIndex
                ? { x: Math.max(0, Math.min(1, cur.x - drag.offset.x)), y: Math.max(0, Math.min(1, cur.y - drag.offset.y)) }
                : p
            );
            return { ...s, points: pts };
          }
          const dx = cur.x - drag.offset.x;
          const dy = cur.y - drag.offset.y;
          const pts = s.points.map((p) => ({ x: Math.max(0, Math.min(1, p.x + dx)), y: Math.max(0, Math.min(1, p.y + dy)) }));
          return { ...s, points: pts };
        });
      });
    };
    const handleUp = () => setDrag(null);
    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleUp);
    return () => {
      document.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseup', handleUp);
    };
  }, [drag]);

  function pointFromEvent(e: React.MouseEvent): Point {
    const rect = imgRef.current!.getBoundingClientRect();
    return { x: (e.clientX - rect.left) / rect.width, y: (e.clientY - rect.top) / rect.height };
  }

  function addPoint(p: Point) {
    if (mode === 'point') {
      setShapes((prev) => [...prev, { id: makeId(), category: activeCategory, type: 'point', points: [p] }]);
      return;
    }
    setDraft((prev) => [...prev, p]);
  }

  function finishShape() {
    if (mode === 'point') return;
    if (draft.length < minFor(mode)) return;
    setShapes((prev) => [...prev, { id: makeId(), category: activeCategory, type: mode, points: draft }]);
    setDraft([]);
  }

  function handleImageClick(e: React.MouseEvent) {
    if (drag) return;
    const p = pointFromEvent(e);
    if (clickTimer.current !== null) {
      window.clearTimeout(clickTimer.current);
      clickTimer.current = null;
      finishShape();
      return;
    }
    clickTimer.current = window.setTimeout(() => {
      clickTimer.current = null;
      addPoint(p);
    }, 250);
  }

  function handleImageMove(e: React.MouseEvent) {
    if (drag) return;
    setCursor(pointFromEvent(e));
  }

  function deleteVertex(shapeId: string, pointIndex: number) {
    setShapes((prev) => {
      const shape = prev.find((s) => s.id === shapeId);
      if (!shape) return prev;
      const remaining = shape.points.filter((_, i) => i !== pointIndex);
      if (remaining.length < minFor(shape.type)) {
        return prev.filter((s) => s.id !== shapeId);
      }
      return prev.map((s) => (s.id === shapeId ? { ...s, points: remaining } : s));
    });
  }

  function deleteShape(shapeId: string) {
    setShapes((prev) => prev.filter((s) => s.id !== shapeId));
  }

  function startVertexDrag(e: React.MouseEvent, shape: Shape, pointIndex: number) {
    e.stopPropagation();
    const cur = pointFromEvent(e);
    const p = shape.points[pointIndex];
    setDrag({ shapeId: shape.id, kind: 'vertex', pointIndex, offset: { x: cur.x - p.x, y: cur.y - p.y } });
  }

  function startShapeDrag(e: React.MouseEvent, shape: Shape) {
    e.stopPropagation();
    const cur = pointFromEvent(e);
    const first = shape.points[0];
    setDrag({ shapeId: shape.id, kind: 'shape', offset: { x: cur.x - first.x, y: cur.y - first.y } });
  }

  const activeColor = getColor(activeCategory, categories, colors);
  const modeHint =
    mode === 'point'
      ? 'Click to add a point.'
      : `Click to add points (${mode} needs ${minFor(mode)}); double-click or Enter to finish.`;

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8 }}>
        {categories.map((cat) => {
          const c = getColor(cat, categories, colors);
          return (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 10px',
                borderRadius: 4, border: activeCategory === cat ? '2px solid #F97316' : '1px solid #ccc',
                background: '#fff', cursor: 'pointer',
              }}
            >
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: c, display: 'inline-block' }} />
              {cat}
            </button>
          );
        })}
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
        {(['closed', 'open', 'point'] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            style={{
              padding: '2px 10px', borderRadius: 4,
              border: mode === m ? '2px solid #F97316' : '1px solid #ccc',
              background: '#fff', cursor: 'pointer', fontWeight: mode === m ? 600 : 400,
            }}
          >
            {m}
          </button>
        ))}
        <button onClick={() => setShowLabels((v) => !v)} style={{ padding: '2px 10px', borderRadius: 4, border: '1px solid #ccc', background: '#fff', cursor: 'pointer' }}>
          {showLabels ? 'Hide labels' : 'Show labels'}
        </button>
      </div>
      <div
        ref={imgRef}
        onClick={handleImageClick}
        onMouseMove={handleImageMove}
        style={{ position: 'relative', display: 'inline-block', userSelect: 'none' }}
      >
        <img src={imageUrl} alt="annotate" draggable={false} style={{ maxWidth: '100%', cursor: 'crosshair' }} />
        <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} viewBox="0 0 1 1" preserveAspectRatio="none">
          {shapes.map((shape) => {
            const color = getColor(shape.category, categories, colors);
            const pts = shape.points.map((p) => `${p.x},${p.y}`).join(' ');
            const body = (() => {
              if (shape.type === 'closed') {
                return (
                  <polygon
                    key={shape.id}
                    points={pts}
                    fill={`${color}22`}
                    stroke={color}
                    strokeWidth={0.002}
                    onMouseDown={(e) => startShapeDrag(e, shape)}
                    onClick={(e) => { e.stopPropagation(); deleteShape(shape.id); }}
                  />
                );
              }
              if (shape.type === 'open') {
                return (
                  <polyline
                    key={shape.id}
                    points={pts}
                    fill="none"
                    stroke={color}
                    strokeWidth={0.002}
                    onMouseDown={(e) => startShapeDrag(e, shape)}
                    onClick={(e) => { e.stopPropagation(); deleteShape(shape.id); }}
                  />
                );
              }
              return (
                <circle
                  key={shape.id}
                  cx={shape.points[0].x}
                  cy={shape.points[0].y}
                  r={0.008}
                  fill={color}
                  stroke={color}
                  strokeWidth={0.001}
                  onMouseDown={(e) => startShapeDrag(e, shape)}
                  onClick={(e) => { e.stopPropagation(); deleteShape(shape.id); }}
                />
              );
            })();
            const vertices = shape.points.map((p, i) => (
              <circle
                key={`${shape.id}-v${i}`}
                cx={p.x}
                cy={p.y}
                r={0.005}
                fill="#fff"
                stroke={color}
                strokeWidth={0.002}
                onMouseDown={(e) => startVertexDrag(e, shape, i)}
                onClick={(e) => { e.stopPropagation(); deleteVertex(shape.id, i); }}
              />
            ));
            return (
              <g key={shape.id}>
                {body}
                {vertices}
                {showLabels && shape.type !== 'point' && (
                  <text x={shape.points[0].x} y={Math.max(0.01, shape.points[0].y - 0.01)} fontSize={0.01} fill={color} textAnchor="middle">
                    {shape.category}
                  </text>
                )}
              </g>
            );
          })}
          {draft.length > 0 && cursor && (
            <g>
              {mode === 'closed' ? (
                <polygon
                  points={[...draft, cursor].map((p) => `${p.x},${p.y}`).join(' ')}
                  fill="none"
                  stroke={activeColor}
                  strokeWidth={0.002}
                  strokeDasharray="0.002 0.002"
                />
              ) : (
                <polyline
                  points={[...draft, cursor].map((p) => `${p.x},${p.y}`).join(' ')}
                  fill="none"
                  stroke={activeColor}
                  strokeWidth={0.002}
                  strokeDasharray="0.002 0.002"
                />
              )}
              {draft.map((p, i) => (
                <circle key={`d${i}`} cx={p.x} cy={p.y} r={0.004} fill="#fff" stroke={activeColor} strokeWidth={0.002} />
              ))}
            </g>
          )}
        </svg>
      </div>
      <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>{modeHint}</div>
    </div>
  );
}
