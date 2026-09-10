import { useEffect, useState } from 'react';
import { api } from '../api/client';

interface Props {
  index: number;
  row: Record<string, any>;
  annotations?: any[];
  projectId: string;
  userId: string;
  onClose: () => void;
  onRefresh: () => void;
}

export default function RowDetail({ index, row, annotations, projectId, userId, onClose, onRefresh }: Props) {
  const [byMe, setByMe] = useState(false);
  const [mlAnnotation, setMlAnnotation] = useState<{ annotator: string; data: Record<string, any>; created_at: string } | null>(null);
  const [pending, setPending] = useState<'annotation' | 'prediction' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    api.getProjectRow(projectId, index, userId)
      .then((r) => setByMe(r.annotation_status.by_me))
      .catch(() => {});
    api.getMLAnnotation(projectId, index)
      .then(setMlAnnotation)
      .catch(() => setMlAnnotation(null));
    onRefresh();
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, projectId, userId]);

  const clearAnnotation = async () => {
    setPending('annotation');
    setError(null);
    try {
      await api.deleteAnnotation(projectId, index, userId);
      refresh();
    } catch (e: any) {
      setError(e.message || 'Failed to clear annotation');
    }
    setPending(null);
  };

  const clearPrediction = async () => {
    setPending('prediction');
    setError(null);
    try {
      await api.deleteMLAnnotation(projectId, index);
      refresh();
    } catch (e: any) {
      setError(e.message || 'Failed to clear prediction');
    }
    setPending(null);
  };

  return (
    <div className="fixed top-0 right-0 w-[500px] max-w-full h-screen bg-[var(--color-surface)] border-l border-[var(--color-border)] shadow-xl z-50 flex flex-col animate-slide-in">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]">
        <h3 className="font-semibold text-[var(--color-text-heading)]">Row {index}</h3>
        <button
          onClick={onClose}
          className="w-8 h-8 rounded-lg flex items-center justify-center bg-[var(--color-surface-secondary)] hover:bg-[var(--color-surface-sunken)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-all text-lg leading-none"
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

        {/* My annotation */}
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)] mb-2">My Annotation</h4>
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm text-[var(--color-text)]">
              {byMe ? 'Annotated by you' : 'Not annotated by you'}
            </span>
            {byMe && (
              <button
                onClick={clearAnnotation}
                disabled={pending === 'annotation'}
                className="px-2.5 py-1 rounded-md bg-[var(--color-surface-secondary)] hover:bg-[var(--color-surface-sunken)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] text-xs font-medium transition-all disabled:opacity-50"
              >
                {pending === 'annotation' ? 'Clearing...' : 'Clear annotation'}
              </button>
            )}
          </div>
        </div>

        {/* ML prediction */}
        {mlAnnotation && (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)] mb-2">ML Prediction</h4>
            <div className="border border-[var(--color-border)] rounded-lg p-4">
              <div className="flex items-center justify-between mb-2 gap-3">
                <span className="text-sm font-medium text-[var(--color-text-heading)]">{mlAnnotation.annotator}</span>
                <button
                  onClick={clearPrediction}
                  disabled={pending === 'prediction'}
                  className="px-2.5 py-1 rounded-md bg-[var(--color-surface-secondary)] hover:bg-[var(--color-surface-sunken)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] text-xs font-medium transition-all disabled:opacity-50"
                >
                  {pending === 'prediction' ? 'Clearing...' : 'Clear prediction'}
                </button>
              </div>
              <pre className="bg-[var(--color-surface-secondary)] rounded p-3 text-xs font-mono text-[var(--color-text)] overflow-auto max-h-60 whitespace-pre">
                {JSON.stringify(mlAnnotation.data, null, 2)}
              </pre>
            </div>
          </div>
        )}

        {/* All annotations */}
        {annotations && annotations.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)] mb-2">Annotations ({annotations.length})</h4>
            <div className="space-y-3">
              {annotations.map((a, i) => (
                <div key={i} className="border border-[var(--color-border)] rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-sunset-400" />
                      <span className="text-sm font-medium text-[var(--color-text-heading)]">{a.author_id}</span>
                    </div>
                    <span className="text-xs text-[var(--color-text-muted)]">
                      {new Date(a.created_at).toLocaleString()}
                    </span>
                  </div>
                  <pre className="bg-[var(--color-surface-secondary)] rounded p-3 text-xs font-mono text-[var(--color-text)] overflow-auto max-h-60 whitespace-pre">
                    {JSON.stringify(a.data, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="px-4 py-3 rounded-lg text-sm bg-red-50 text-red-700 border border-red-200">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
