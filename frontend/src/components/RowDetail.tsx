interface Props {
  index: number;
  row: Record<string, any>;
  annotations?: any[];
  onClose: () => void;
}

export default function RowDetail({ index, row, annotations, onClose }: Props) {
  return (
    <div style={{ position: 'fixed', top: 0, right: 0, width: 500, height: '100vh',
                  background: 'white', borderLeft: '1px solid #ccc', padding: 20, overflowY: 'auto', zIndex: 100 }}>
      <button onClick={onClose} style={{ float: 'right' }}>Close</button>
      <h3>Row {index}</h3>
      <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 4, overflow: 'auto' }}>
        {JSON.stringify(row, null, 2)}
      </pre>
      {annotations && annotations.length > 0 && (
        <>
          <h4>Annotations</h4>
          {annotations.map((a, i) => (
            <div key={i} style={{ border: '1px solid #eee', padding: 8, marginBottom: 8, borderRadius: 4 }}>
              <strong>{a.author_id}</strong>
              <pre style={{ fontSize: 12 }}>{JSON.stringify(a.data, null, 2)}</pre>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
