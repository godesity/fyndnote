import { useEffect, useState } from 'react';
import { useAnnotationContext } from '../context/AnnotationContext';

interface Props {
  name: string;
  placeholder?: string;
  multiline?: boolean;
  defaultValue?: string;
}

export default function TextField({ name, placeholder, multiline, defaultValue }: Props) {
  const [value, setValue] = useState(defaultValue || '');
  const { registerField, unregisterField } = useAnnotationContext();

  useEffect(() => {
    if (defaultValue !== undefined) setValue(defaultValue);
  }, [defaultValue]);

  useEffect(() => {
    registerField({ name, getValue: () => value });
    return () => unregisterField(name);
  }, [name, value]);

  if (multiline) {
    return <textarea value={value} onChange={(e) => setValue(e.target.value)}
                     placeholder={placeholder} rows={4}
                     style={{ width: '100%', padding: 8, border: '1px solid #e5e7eb', borderRadius: 8 }} />;
  }
  return <input value={value} onChange={(e) => setValue(e.target.value)}
                placeholder={placeholder}
                style={{ width: '100%', padding: 8, border: '1px solid #e5e7eb', borderRadius: 8 }} />;
}
