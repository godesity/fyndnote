interface Props {
  index: number;
  row: Record<string, any>;
  annotations?: any[];
  onClose: () => void;
}

export default function RowDetail({ index, row, annotations, onClose }: Props) {
  return (
    <div className="fixed top-0 right-0 w-[500px] max-w-full h-screen bg-white border-l border-[var(--color-border)] shadow-xl z-50 flex flex-col animate-slide-in">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]">
        <h3 className="font-semibold text-[var(--color-text-heading)]">Row {index}</h3>
        <button
          onClick={onClose}
          className="w-8 h-8 rounded-lg flex items-center justify-center bg-gray-100 hover:bg-gray-200 text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-all text-lg leading-none"
          title="Close"
        >
          ✕
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-5 space-y-6">
        {/* Row data */}
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)] mb-2">Row Data</h4>
          <pre className="bg-[var(--color-surface-secondary)] border border-[var(--color-border)] rounded-lg p-4 text-xs font-mono text-[var(--color-text)] overflow-auto max-h-[50vh] whitespace-pre">
            {JSON.stringify(row, null, 2)}
          </pre>
        </div>

        {/* Annotations */}
        {annotations && annotations.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)] mb-2">Annotations ({annotations.length})</h4>
            <div className="space-y-3">
              {annotations.map((a, i) => (
                <div key={i} className="border border-[var(--color-border)] rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="w-2 h-2 rounded-full bg-sunset-400" />
                    <span className="text-sm font-medium text-[var(--color-text-heading)]">{a.author_id}</span>
                  </div>
                  <pre className="bg-[var(--color-surface-secondary)] rounded p-3 text-xs font-mono text-[var(--color-text)] overflow-auto max-h-60 whitespace-pre">
                    {JSON.stringify(a.data, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
