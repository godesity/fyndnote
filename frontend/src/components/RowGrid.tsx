import AnnotationStatusBadge from './AnnotationStatusBadge';

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
}

export default function RowGrid({ rows, onSelect, page, total, onPageChange }: Props) {
  const perPage = 50;
  const totalPages = Math.ceil(total / perPage);

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 8 }}>
        {rows.map((r) => (
          <div key={r.index} onClick={() => onSelect(r.index)}
               style={{ border: '1px solid #ddd', padding: 8, borderRadius: 4, cursor: 'pointer' }}>
            <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>Row {r.index}</div>
            <div style={{ fontSize: 13, marginBottom: 8, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {JSON.stringify(r.preview).slice(0, 100)}
            </div>
            <AnnotationStatusBadge {...r.annotation_status} />
          </div>
        ))}
      </div>
      {totalPages > 1 && (
        <div style={{ marginTop: 16, display: 'flex', gap: 4 }}>
          {Array.from({ length: totalPages }, (_, i) => (
            <button key={i} onClick={() => onPageChange(i + 1)}
                    style={{ fontWeight: page === i + 1 ? 'bold' : 'normal', padding: '4px 8px' }}>
              {i + 1}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
