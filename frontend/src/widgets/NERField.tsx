import { useEffect, useState, useRef, useCallback } from 'react';
import { useAnnotationContext } from '../context/AnnotationContext';

interface Entity {
  start: number;
  end: number;
  entity: string;
}

interface Props {
  name: string;
  text: string;
  entityTypes: string[];
  defaultValue?: Entity[];
}

export default function NERField({ name, text, entityTypes, defaultValue }: Props) {
  const [entities, setEntities] = useState<Entity[]>(defaultValue || []);
  const [activeEntity, setActiveEntity] = useState(entityTypes[0]);
  const { registerField, unregisterField } = useAnnotationContext();

  useEffect(() => {
    registerField({ name, getValue: () => entities });
    return () => unregisterField(name);
  }, [name, entities]);

  const handleSelect = useCallback(() => {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return;
    const range = sel.getRangeAt(0);
    const start = range.startOffset;
    const end = range.endOffset;
    setEntities((prev) => [...prev, { start, end, entity: activeEntity }]);
    sel.removeAllRanges();
  }, [activeEntity]);

  const sorted = [...entities].sort((a, b) => a.start - b.start);
  const parts: JSX.Element[] = [];
  let pos = 0;
  for (const e of sorted) {
    if (e.start > pos) {
      parts.push(<span key={`t-${pos}`}>{text.slice(pos, e.start)}</span>);
    }
    parts.push(
      <mark key={`e-${e.start}`} style={{ background: '#ffd700', cursor: 'pointer' }}
            onClick={() => setEntities((prev) => prev.filter((x) => x.start !== e.start))}>
        {text.slice(e.start, e.end)}
        <small style={{ marginLeft: 4, color: '#666' }}>({e.entity})</small>
      </mark>
    );
    pos = e.end;
  }
  if (pos < text.length) {
    parts.push(<span key={`t-end`}>{text.slice(pos)}</span>);
  }

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        {entityTypes.map((et) => (
          <button key={et} onClick={() => setActiveEntity(et)}
                  style={{ marginRight: 4, padding: '4px 8px', fontWeight: activeEntity === et ? 'bold' : 'normal' }}>
            {et}
          </button>
        ))}
      </div>
      <div onMouseUp={handleSelect}
           style={{ padding: 12, border: '1px solid #ccc', borderRadius: 4, lineHeight: 1.8, userSelect: 'text' }}>
        {parts}
      </div>
      <p style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
        Select text to tag as &quot;{activeEntity}&quot;. Click a tag to remove it.
      </p>
    </div>
  );
}
