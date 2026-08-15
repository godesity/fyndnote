import { useEffect, useState, useCallback } from 'react';
import { LiveProvider, LivePreview } from 'react-live';
import { useAuth } from '../context/AuthContext';
import { AnnotationProvider } from '../context/AnnotationContext';
import { api } from '../api/client';
import RowNavigator from '../components/RowNavigator';
import SubmitButton from '../components/SubmitButton';
import * as widgets from '../widgets';

const scope = { ...widgets, useState, useCallback };

interface Props {
  projectId: string;
  templateSource: string;
  numRows: number;
  onBack: () => void;
}

export default function LabelView({ projectId, templateSource, numRows, onBack }: Props) {
  const { user } = useAuth();
  const [currentRow, setCurrentRow] = useState<{ index: number; row: Record<string, any> } | null>(null);
  const [annotations, setAnnotations] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);

  const fetchNext = async () => {
    if (!user) return;
    setLoading(true);
    const next = await api.nextRow(projectId, user.user_id);
    if (next.index !== null) {
      setCurrentRow(next);
      try {
        const ann = await api.getAnnotation(projectId, next.index, user.user_id);
        setAnnotations(ann.data);
      } catch {
        setAnnotations({});
      }
    } else {
      setCurrentRow(null);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchNext();
  }, [projectId]);

  if (loading) return <div>Loading...</div>;
  if (!currentRow) return (
    <div>
      <p>All rows annotated!</p>
      <button onClick={onBack}>Back to Projects</button>
    </div>
  );

  return (
    <AnnotationProvider>
      <div style={{ padding: 20 }}>
        <button onClick={onBack} style={{ marginBottom: 16 }}>&larr; Back</button>
        <RowNavigator currentIndex={currentRow.index} numRows={numRows} />
        <div style={{ border: '1px solid #ccc', padding: 16, borderRadius: 4, marginTop: 16, minHeight: 300 }}>
          <LiveProvider code={templateSource}
                        scope={{ ...scope, data: currentRow.row, annotations }}>
            <LivePreview />
          </LiveProvider>
        </div>
        <SubmitButton projectId={projectId} rowIndex={currentRow.index}
                      onSubmitted={fetchNext} />
      </div>
    </AnnotationProvider>
  );
}
