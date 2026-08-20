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
            className="my-2 px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-white cursor-pointer">
      {labels.map((l) => (
        <option key={l} value={l}>{l}</option>
      ))}
    </select>
  );
}
