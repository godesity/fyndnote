import { type JSX, useEffect, useState, useRef, useCallback } from 'react';
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
  colors?: string[];
}

const DEFAULT_COLORS = [
  '#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6',
  '#1abc9c', '#e67e22', '#34495e', '#16a085', '#c0392b',
];

function getColor(entityType: string, colors: string[]): string {
  let hash = 0;
  for (let i = 0; i < entityType.length; i++) {
    hash = entityType.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

function absoluteOffset(container: HTMLElement, targetNode: Node, nodeOffset: number): number {
  let found = false;
  let pos = 0;

  function walk(node: Node): void {
    if (found) return;
    if (node.nodeType === Node.TEXT_NODE) {
      if (node === targetNode) {
        pos += nodeOffset;
        found = true;
        return;
      }
      pos += (node.textContent || '').length;
      return;
    }
    if ((node as Element).tagName === 'SMALL') return;
    for (let i = 0; i < node.childNodes.length; i++) {
      walk(node.childNodes[i]);
    }
  }

  walk(container);
  return pos;
}

export default function NERField({ name, text, entityTypes, defaultValue, colors: colorOverride }: Props) {
  const colors = colorOverride || DEFAULT_COLORS;
  const [entities, setEntities] = useState<Entity[]>(defaultValue || []);
  const [activeEntity, setActiveEntity] = useState(entityTypes[0]);
  const containerRef = useRef<HTMLDivElement>(null);
  const { registerField, unregisterField } = useAnnotationContext();

  useEffect(() => {
    registerField({ name, getValue: () => entities });
    return () => unregisterField(name);
  }, [name, entities]);

  const handleSelect = useCallback(() => {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed || !containerRef.current) return;
    const range = sel.getRangeAt(0);
    const start = absoluteOffset(containerRef.current, range.startContainer, range.startOffset);
    const end = absoluteOffset(containerRef.current, range.endContainer, range.endOffset);
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
    const bg = getColor(e.entity, colors);
    parts.push(
      <mark key={`e-${e.start}`}
            style={{ background: bg, color: '#fff', cursor: 'pointer', padding: '2px 4px', borderRadius: 3 }}
            onClick={() => setEntities((prev) => prev.filter((x) => x.start !== e.start))}>
        {text.slice(e.start, e.end)}
        <small style={{ marginLeft: 4, opacity: 0.8 }}>({e.entity})</small>
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
        {entityTypes.map((et) => {
          const c = getColor(et, colors);
          return (
            <button key={et} onClick={() => setActiveEntity(et)}
                    style={{
                      marginRight: 4, padding: '4px 10px',
                      fontWeight: activeEntity === et ? 'bold' : 'normal',
                      border: activeEntity === et ? `2px solid ${c}` : '1px solid #ccc',
                      borderRadius: 4, display: 'inline-flex', alignItems: 'center', gap: 6,
                    }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: c, display: 'inline-block' }} />
              {et}
            </button>
          );
        })}
      </div>
      <div ref={containerRef} onMouseUp={handleSelect}
           style={{ padding: 12, border: '1px solid #ccc', borderRadius: 4, lineHeight: 2.2, userSelect: 'text' }}>
        {parts}
      </div>
      <p style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
        Select text to tag as &quot;{activeEntity}&quot;. Click a tag to remove it.
      </p>
    </div>
  );
}
