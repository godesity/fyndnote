import { useEffect, useState } from 'react';
import { useAnnotationContext } from '../context/AnnotationContext';

interface Props {
  name: string;
  labels: string[];
  defaultValue?: string[];
}

export default function CheckboxGroup({ name, labels, defaultValue }: Props) {
  const [checked, setChecked] = useState<Set<string>>(new Set(defaultValue || []));
  const { registerField, unregisterField } = useAnnotationContext();

  useEffect(() => {
    registerField({ name, getValue: () => Array.from(checked) });
    return () => unregisterField(name);
  }, [name, checked]);

  const toggle = (opt: string) => {
    const next = new Set(checked);
    if (next.has(opt)) next.delete(opt); else next.add(opt);
    setChecked(next);
  };

  return (
    <div>
      {labels.map((opt) => (
        <label key={opt} style={{ display: 'block', marginBottom: 4 }}>
          <input type="checkbox" checked={checked.has(opt)} onChange={() => toggle(opt)} />
          {' '}{opt}
        </label>
      ))}
    </div>
  );
}
