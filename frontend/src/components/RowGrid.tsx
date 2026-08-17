import { useState } from 'react';
import AnnotationStatusBadge from './AnnotationStatusBadge';
import GradientBorderCard from './GradientBorderCard';

interface RowEntry {
  index: number;
  preview: Record<string, any>;
  annotation_status: { by_me: boolean; by_any: boolean; annotators: string[] };
}

interface Props {
  rows: RowEntry[];
  onSelect: (index: number) => void;
  page: number;
  total: number;
  onPageChange: (page: number) => void;
  color?: string;
}

type ViewMode = 'grid' | 'list';

function truncate(val: any, maxLen = 60): string {
  const s = typeof val === 'string' ? val : JSON.stringify(val);
  if (s.length <= maxLen) return s;
  return s.slice(0, maxLen) + '…';
}

function RowPreview({ preview }: { preview: Record<string, any> }) {
  const entries = Object.entries(preview).slice(0, 5);
  return (
    <div className="space-y-1.5">
      {entries.map(([key, val]) => (
        <div key={key} className="text-xs">
          <span className="font-medium text-[var(--color-text-muted)]">{key}: </span>
          <span className="text-[var(--color-text)]">{truncate(val)}</span>
        </div>
      ))}
      {Object.keys(preview).length > 5 && (
        <div className="text-xs text-[var(--color-text-muted)] italic">
          +{Object.keys(preview).length - 5} more fields
        </div>
      )}
    </div>
  );
}

export default function RowGrid({ rows, onSelect, page, total, onPageChange, color }: Props) {
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const perPage = 50;
  const totalPages = Math.ceil(total / perPage);

  return (
    <div>
      {/* View toggle */}
      <div className="flex items-center gap-1 mb-4 bg-white border border-[var(--color-border)] rounded-lg p-0.5 w-fit shadow-sm">
        <button
          onClick={() => setViewMode('grid')}
          className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${viewMode === 'grid' ? 'bg-gradient-to-r from-sunset-500 to-coral-500 text-white shadow-sm' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'}`}
        >
          ▦ Grid
        </button>
        <button
          onClick={() => setViewMode('list')}
          className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${viewMode === 'list' ? 'bg-gradient-to-r from-sunset-500 to-coral-500 text-white shadow-sm' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'}`}
        >
          ☰ List
        </button>
      </div>

      {viewMode === 'grid' ? (
        /* ---- Grid view ---- */
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
          {rows.map((r) => (
            <GradientBorderCard key={r.index}>
              <div className="p-4 cursor-pointer" onClick={() => onSelect(r.index)}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-[var(--color-text-muted)]">Row {r.index}</span>
                  <AnnotationStatusBadge byMe={r.annotation_status.by_me} byAny={r.annotation_status.by_any} annotators={r.annotation_status.annotators} />
                </div>
                <RowPreview preview={r.preview} />
              </div>
            </GradientBorderCard>
          ))}
        </div>
      ) : (
        /* ---- List view ---- */
        <div className="divide-y divide-[var(--color-border)]">
          {rows.map((r) => (
            <div
              key={r.index}
              className="px-4 py-3 cursor-pointer hover:bg-gray-50/50 transition-colors"
              onClick={() => onSelect(r.index)}
            >
              <div className="flex items-center gap-4">
                <span className="text-xs font-semibold text-[var(--color-text-muted)] w-16 flex-shrink-0">Row {r.index}</span>
                <div className="flex-1 min-w-0 flex items-center gap-4 overflow-hidden">
                  {Object.entries(r.preview).slice(0, 4).map(([key, val]) => (
                    <span key={key} className="text-xs text-[var(--color-text)] truncate min-w-0 flex-shrink">
                      <span className="font-medium text-[var(--color-text-muted)]">{key}:</span> {truncate(val, 40)}
                    </span>
                  ))}
                  {Object.keys(r.preview).length > 4 && (
                    <span className="text-xs text-[var(--color-text-muted)] italic flex-shrink-0">
                      +{Object.keys(r.preview).length - 4}
                    </span>
                  )}
                </div>
                <AnnotationStatusBadge byMe={r.annotation_status.by_me} byAny={r.annotation_status.by_any} annotators={r.annotation_status.annotators} />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1 mt-6">
          {/* Prev */}
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            className="px-3 py-1.5 rounded-lg text-sm font-medium bg-white border border-[var(--color-border)] text-[var(--color-text)] hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed transition-all flex items-center gap-1"
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M10.3 12.7L5.6 8l4.7-4.7L9.3 2.3 3.6 8l5.7 5.7 1-1z"/></svg>
            Prev
          </button>

          {/* Page numbers */}
          {Array.from({ length: totalPages }, (_, i) => {
            const p = i + 1;
            const show =
              p === 1 ||
              p === totalPages ||
              Math.abs(p - page) <= 2;

            if (!show) {
              const prevShown = i === 0 || Math.abs(p - 1 - page) <= 2;
              return prevShown ? <span key={p} className="px-2 text-[var(--color-text-muted)] select-none">…</span> : null;
            }

            return (
              <button
                key={p}
                onClick={() => onPageChange(p)}
                className={`w-9 h-9 rounded-lg text-sm font-medium transition-all ${
                  page === p
                    ? 'bg-gradient-to-r from-sunset-500 to-coral-500 text-white shadow-sm'
                    : 'bg-white border border-[var(--color-border)] text-[var(--color-text)] hover:bg-gray-50'
                }`}
              >
                {p}
              </button>
            );
          })}

          {/* Next */}
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
            className="px-3 py-1.5 rounded-lg text-sm font-medium bg-white border border-[var(--color-border)] text-[var(--color-text)] hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed transition-all flex items-center gap-1"
          >
            Next
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M5.7 3.3L10.4 8l-4.7 4.7 1.4 1.4L12.8 8 7.1 2.3 5.7 3.3z"/></svg>
          </button>
        </div>
      )}
    </div>
  );
}
