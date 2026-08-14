import { useEffect, useState, useRef } from 'react';
import { useAnnotationContext } from '../context/AnnotationContext';

interface BBox {
  x: number; y: number; w: number; h: number; category: string;
}

interface Props {
  name: string;
  imageUrl: string;
  categories: string[];
  defaultValue?: BBox[];
}

export default function BBoxField({ name, imageUrl, categories, defaultValue }: Props) {
  const [boxes, setBoxes] = useState<BBox[]>(defaultValue || []);
  const [activeCategory, setActiveCategory] = useState(categories[0]);
  const [drawing, setDrawing] = useState(false);
  const [start, setStart] = useState({ x: 0, y: 0 });
  const imgRef = useRef<HTMLImageElement>(null);
  const { registerField, unregisterField } = useAnnotationContext();

  useEffect(() => {
    registerField({ name, getValue: () => boxes });
    return () => unregisterField(name);
  }, [name, boxes]);

  const handleMouseDown = (e: React.MouseEvent) => {
    const rect = imgRef.current!.getBoundingClientRect();
    setStart({ x: (e.clientX - rect.left) / rect.width, y: (e.clientY - rect.top) / rect.height });
    setDrawing(true);
  };

  const handleMouseUp = (e: React.MouseEvent) => {
    if (!drawing) return;
    const rect = imgRef.current!.getBoundingClientRect();
    const end = { x: (e.clientX - rect.left) / rect.width, y: (e.clientY - rect.top) / rect.height };
    const box: BBox = {
      x: Math.min(start.x, end.x),
      y: Math.min(start.y, end.y),
      w: Math.abs(end.x - start.x),
      h: Math.abs(end.y - start.y),
      category: activeCategory,
    };
    setBoxes((prev) => [...prev, box]);
    setDrawing(false);
  };

  const removeBox = (idx: number) => {
    setBoxes((prev) => prev.filter((_, i) => i !== idx));
  };

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        {categories.map((c) => (
          <button key={c} onClick={() => setActiveCategory(c)}
                  style={{ marginRight: 4, padding: '4px 8px', fontWeight: activeCategory === c ? 'bold' : 'normal' }}>
            {c}
          </button>
        ))}
      </div>
      <div style={{ position: 'relative', display: 'inline-block' }}>
        <img ref={imgRef} src={imageUrl} alt="annotate"
             onMouseDown={handleMouseDown} onMouseUp={handleMouseUp}
             style={{ maxWidth: '100%', cursor: 'crosshair' }} />
        {boxes.map((box, i) => (
          <div key={i} onClick={() => removeBox(i)}
               style={{
                 position: 'absolute',
                 left: `${box.x * 100}%`, top: `${box.y * 100}%`,
                 width: `${box.w * 100}%`, height: `${box.h * 100}%`,
                 border: '2px solid red', background: 'rgba(255,0,0,0.1)',
                 cursor: 'pointer', boxSizing: 'border-box',
               }}>
            <span style={{ background: 'red', color: 'white', fontSize: 10, padding: '1px 4px' }}>
              {box.category}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
