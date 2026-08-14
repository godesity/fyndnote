interface Props {
  currentIndex: number;
  numRows: number;
}

export default function RowNavigator({ currentIndex, numRows }: Props) {
  const pct = numRows > 0 ? Math.round(((currentIndex + 1) / numRows) * 100) : 0;
  return (
    <div style={{ marginBottom: 8 }}>
      <span>Row {currentIndex + 1} of {numRows}</span>
      <div style={{ width: '100%', height: 6, background: '#eee', borderRadius: 3, marginTop: 4 }}>
        <div style={{ width: `${pct}%`, height: '100%', background: '#4caf50', borderRadius: 3 }} />
      </div>
    </div>
  );
}
