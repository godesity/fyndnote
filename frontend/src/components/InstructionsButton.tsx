import { useState } from 'react';
import InstructionsEditor from './InstructionsEditor';

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export default function InstructionsButton({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="px-3 py-1.5 rounded-lg border border-[var(--color-border)] bg-white text-sm text-[var(--color-text)] hover:bg-gray-50 transition-all flex items-center gap-1.5"
      >
        <span>📋</span>
        Guidelines
      </button>

      {open && (
        <>
          <div className="fixed inset-0 bg-black/20 z-40" onClick={() => setOpen(false)} />
          <div className="fixed inset-y-0 right-0 w-[32rem] max-w-full bg-white shadow-xl border-l border-[var(--color-border)] z-50 flex flex-col animate-slide-in">
            <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]">
              <h3 className="font-semibold text-[var(--color-text-heading)]">Annotation Guidelines</h3>
              <button onClick={() => setOpen(false)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] text-lg leading-none">&times;</button>
            </div>
            <div className="flex-1 overflow-y-auto p-5">
              <InstructionsEditor value={value} onChange={onChange} />
            </div>
          </div>
        </>
      )}
    </>
  );
}
