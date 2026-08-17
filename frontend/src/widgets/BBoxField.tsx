import { useEffect, useState, useRef, useCallback } from 'react';
import { useAnnotationContext } from '../context/AnnotationContext';

interface BBox {
  x: number; y: number; w: number; h: number; category: string;
}

interface Props {
  name: string;
  imageUrl: string;
  categories: string[];
  defaultValue?: BBox[];
  colors?: string[];
}

const DEFAULT_COLORS = [
  '#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6',
  '#1abc9c', '#e67e22', '#34495e', '#16a085', '#c0392b',
];

function getColor(category: string, colors: string[]): string {
  let hash = 0;
  for (let i = 0; i < category.length; i++) {
    hash = category.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

type Handle = 'tl' | 'tr' | 'bl' | 'br';

export default function BBoxField({ name, imageUrl, categories, defaultValue, colors: colorOverride }: Props) {
  const colors = colorOverride || DEFAULT_COLORS;
  const [boxes, setBoxes] = useState<BBox[]>(defaultValue || []);
  const [activeCategory, setActiveCategory] = useState(categories[0]);
  const [drawing, setDrawing] = useState(false);
  const [start, setStart] = useState({ x: 0, y: 0 });
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [dragMoved, setDragMoved] = useState(false);
  const resizeMovedRef = useRef(false);
  const [resizeIndex, setResizeIndex] = useState<number | null>(null);
  const [resizeHandle, setResizeHandle] = useState<Handle | null>(null);
  const [resizeStart, setResizeStart] = useState({ x: 0, y: 0, boxX: 0, boxY: 0, boxW: 0, boxH: 0 });
  const [showLabels, setShowLabels] = useState(true);
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { registerField, unregisterField } = useAnnotationContext();

  useEffect(() => {
    registerField({ name, getValue: () => boxes });
    return () => unregisterField(name);
  }, [name, boxes]);

  // Document-level mousemove/mouseup for box dragging
  useEffect(() => {
    if (dragIndex === null) return;
    const handleMouseMove = (e: MouseEvent) => {
      const rect = imgRef.current!.getBoundingClientRect();
      setDragMoved(true);
      setBoxes((prev) => {
        const next = [...prev];
        const box = { ...next[dragIndex] };
        const mx = (e.clientX - rect.left) / rect.width - dragOffset.x;
        const my = (e.clientY - rect.top) / rect.height - dragOffset.y;
        box.x = Math.max(0, Math.min(1 - box.w, mx));
        box.y = Math.max(0, Math.min(1 - box.h, my));
        next[dragIndex] = box;
        return next;
      });
    };
    const handleMouseUp = () => {
      setDragIndex(null);
      setTimeout(() => setDragMoved(false), 0);
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [dragIndex, dragOffset]);

  // Document-level mousemove/mouseup for resize
  useEffect(() => {
    if (resizeIndex === null || !resizeHandle) return;
    const handleMouseMove = (e: MouseEvent) => {
      resizeMovedRef.current = true;
      const rect = imgRef.current!.getBoundingClientRect();
      const mx = (e.clientX - rect.left) / rect.width;
      const my = (e.clientY - rect.top) / rect.height;
      setBoxes((prev) => {
        const next = [...prev];
        let x = resizeStart.boxX, y = resizeStart.boxY, w = resizeStart.boxW, h = resizeStart.boxH;
        switch (resizeHandle) {
          case 'tl':
            x = Math.max(0, Math.min(mx, resizeStart.boxX + resizeStart.boxW - 0.01));
            y = Math.max(0, Math.min(my, resizeStart.boxY + resizeStart.boxH - 0.01));
            w = resizeStart.boxW + (resizeStart.boxX - x);
            h = resizeStart.boxH + (resizeStart.boxY - y);
            break;
          case 'tr':
            y = Math.max(0, Math.min(my, resizeStart.boxY + resizeStart.boxH - 0.01));
            w = Math.max(0.01, mx - resizeStart.boxX);
            h = resizeStart.boxH + (resizeStart.boxY - y);
            break;
          case 'bl':
            x = Math.max(0, Math.min(mx, resizeStart.boxX + resizeStart.boxW - 0.01));
            w = resizeStart.boxW + (resizeStart.boxX - x);
            h = Math.max(0.01, my - resizeStart.boxY);
            break;
          case 'br':
            w = Math.max(0.01, mx - resizeStart.boxX);
            h = Math.max(0.01, my - resizeStart.boxY);
            break;
        }
        w = Math.min(w, 1 - x);
        h = Math.min(h, 1 - y);
        next[resizeIndex] = { ...next[resizeIndex], x, y, w, h };
        return next;
      });
    };
    const handleMouseUp = () => {
      setResizeIndex(null);
      setResizeHandle(null);
      setTimeout(() => { resizeMovedRef.current = false; }, 0);
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [resizeIndex, resizeHandle, resizeStart]);

  const handleImageMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    const rect = imgRef.current!.getBoundingClientRect();
    setStart({ x: (e.clientX - rect.left) / rect.width, y: (e.clientY - rect.top) / rect.height });
    setDrawing(true);
  };

  const handleImageMouseUp = (e: React.MouseEvent) => {
    if (!drawing) return;
    e.preventDefault();
    const rect = imgRef.current!.getBoundingClientRect();
    const end = { x: (e.clientX - rect.left) / rect.width, y: (e.clientY - rect.top) / rect.height };
    const box: BBox = {
      x: Math.min(start.x, end.x),
      y: Math.min(start.y, end.y),
      w: Math.abs(end.x - start.x),
      h: Math.abs(end.y - start.y),
      category: activeCategory,
    };
    if (box.w > 0.005 && box.h > 0.005) {
      setBoxes((prev) => [...prev, box]);
    }
    setDrawing(false);
  };

  const handleBoxMouseDown = (e: React.MouseEvent, idx: number) => {
    e.stopPropagation();
    e.preventDefault();
    const rect = imgRef.current!.getBoundingClientRect();
    setDragOffset({
      x: (e.clientX - rect.left) / rect.width - boxes[idx].x,
      y: (e.clientY - rect.top) / rect.height - boxes[idx].y,
    });
    setDragIndex(idx);
  };

  const handleBoxClick = (e: React.MouseEvent, idx: number) => {
    e.stopPropagation();
    if (dragMoved || resizeMovedRef.current) return;
    setBoxes((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleResizeStart = (e: React.MouseEvent, idx: number, handle: Handle) => {
    e.stopPropagation();
    e.preventDefault();
    resizeMovedRef.current = true;
    const box = boxes[idx];
    setResizeIndex(idx);
    setResizeHandle(handle);
    setResizeStart({ x: e.clientX, y: e.clientY, boxX: box.x, boxY: box.y, boxW: box.w, boxH: box.h });
  };

  const HANDLE_SIZE = 8;

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        {categories.map((cat) => {
          const c = getColor(cat, colors);
          return (
            <button key={cat} onClick={() => setActiveCategory(cat)}
                    style={{
                      marginRight: 4, padding: '4px 10px',
                      fontWeight: activeCategory === cat ? 'bold' : 'normal',
                      border: activeCategory === cat ? `2px solid ${c}` : '1px solid #ccc',
                      borderRadius: 4, display: 'inline-flex', alignItems: 'center', gap: 6,
                    }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: c, display: 'inline-block' }} />
              {cat}
            </button>
          );
        })}
        <button onClick={() => setShowLabels((v) => !v)}
                style={{ marginLeft: 8, padding: '4px 10px', borderRadius: 4, border: '1px solid #ccc', cursor: 'pointer' }}>
          {showLabels ? 'Hide labels' : 'Show labels'}
        </button>
      </div>
      <div ref={containerRef} style={{ position: 'relative', display: 'inline-block', userSelect: 'none' }}>
        <img ref={imgRef} src={imageUrl} alt="annotate" draggable={false}
             onMouseDown={handleImageMouseDown} onMouseUp={handleImageMouseUp}
             style={{ maxWidth: '100%', cursor: 'crosshair' }} />
        {boxes.map((box, i) => {
          const c = getColor(box.category, colors);
          return (
            <div key={i}
                 onMouseDown={(e) => handleBoxMouseDown(e, i)}
                 onClick={(e) => handleBoxClick(e, i)}
                 style={{
                   position: 'absolute',
                   left: `${box.x * 100}%`, top: `${box.y * 100}%`,
                   width: `${box.w * 100}%`, height: `${box.h * 100}%`,
                   border: `2px solid ${c}`, background: `${c}22`,
                   cursor: dragIndex === i ? 'grabbing' : 'grab',
                   boxSizing: 'border-box',
                 }}>
              {showLabels && (
                <span style={{ background: c, color: '#fff', fontSize: 10, padding: '1px 4px', display: 'inline-block' }}>
                  {box.category}
                </span>
              )}
              {/* Resize handles */}
              {['tl', 'tr', 'bl', 'br'].map((h) => (
                <div key={h}
                     onMouseDown={(e) => handleResizeStart(e, i, h as Handle)}
                     style={{
                       position: 'absolute',
                       width: HANDLE_SIZE, height: HANDLE_SIZE,
                       background: '#fff', border: `2px solid ${c}`, borderRadius: 2,
                       boxSizing: 'border-box',
                       ...(h === 'tl' ? { top: -HANDLE_SIZE / 2, left: -HANDLE_SIZE / 2, cursor: 'nwse-resize' } :
                          h === 'tr' ? { top: -HANDLE_SIZE / 2, right: -HANDLE_SIZE / 2, cursor: 'nesw-resize' } :
                          h === 'bl' ? { bottom: -HANDLE_SIZE / 2, left: -HANDLE_SIZE / 2, cursor: 'nesw-resize' } :
                                       { bottom: -HANDLE_SIZE / 2, right: -HANDLE_SIZE / 2, cursor: 'nwse-resize' }),
                     }} />
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
