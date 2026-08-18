import { useEffect, useState } from 'react';
import { useAnnotationContext } from '../context/AnnotationContext';

interface Props {
  name: string;
  labels: string[];
  defaultValue?: string;
}

export default function SelectField({ name, labels, defaultValue }: Props) {
  const [value, setValue] = useState(defaultValue || labels[0] || '');
  const { registerField, unregisterField } = useAnnotationContext();

  useEffect(() => {
    if (defaultValue !== undefined) setValue(defaultValue);
  }, [defaultValue]);

  useEffect(() => {
    registerField({ name, getValue: () => value });
    return () => unregisterField(name);
  }, [name, value]);

  return (
    <select value={value} onChange={(e) => setValue(e.target.value)}
            style={{ padding: 8, fontSize: 14 }}>
      {labels.map((l) => (
        <option key={l} value={l}>{l}</option>
      ))}
    </select>
  );
}
