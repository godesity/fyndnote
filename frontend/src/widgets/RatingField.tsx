import { useEffect, useState } from 'react';
import { useAnnotationContext } from '../context/AnnotationContext';

interface Props {
  name: string;
  max: number;
  icon?: string;
  defaultValue?: number;
}

export default function RatingField({ name, max, defaultValue }: Props) {
  const [value, setValue] = useState(defaultValue || 0);
  const { registerField, unregisterField } = useAnnotationContext();

  useEffect(() => {
    registerField({ name, getValue: () => value });
    return () => unregisterField(name);
  }, [name, value]);

  return (
    <div style={{ display: 'flex', gap: 4 }}>
      {Array.from({ length: max }, (_, i) => (
        <button key={i} onClick={() => setValue(i + 1)}
                style={{
                  width: 32, height: 32,
                  background: i < value ? '#ffc107' : '#eee',
                  border: '1px solid #ccc', borderRadius: 4, cursor: 'pointer'
                }}>
          {i + 1}
        </button>
      ))}
    </div>
  );
}
