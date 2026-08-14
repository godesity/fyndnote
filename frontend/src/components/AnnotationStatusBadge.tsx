interface Props {
  byMe: boolean;
  byAny: boolean;
  annotators: string[];
}

export default function AnnotationStatusBadge({ byMe, byAny, annotators }: Props) {
  if (byMe) return <span style={{ background: '#4caf50', color: 'white', padding: '2px 8px', borderRadius: 4, fontSize: 12 }}>Annotated by me</span>;
  if (byAny) return <span style={{ background: '#ff9800', color: 'white', padding: '2px 8px', borderRadius: 4, fontSize: 12 }}>Annotated by {annotators.join(', ')}</span>;
  return <span style={{ background: '#eee', padding: '2px 8px', borderRadius: 4, fontSize: 12 }}>Unannotated</span>;
}
