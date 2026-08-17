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
}

export default function LabelView({ projectId }: Props) {
  const { user } = useAuth();
  const [templateSource, setTemplateSource] = useState('');
  const [numRows, setNumRows] = useState(0);
  const [projectColor, setProjectColor] = useState('#1976d2');
  const [projectName, setProjectName] = useState('');
  const [loadingMeta, setLoadingMeta] = useState(true);
  const [currentRow, setCurrentRow] = useState<{ index: number; row: Record<string, any> } | null>(null);
  const [annotations, setAnnotations] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    api.getProject(projectId, user.user_id).then((projectDetail) => {
      setNumRows(projectDetail.num_rows || 0);
      setTemplateSource(projectDetail.template_source || '');
      setProjectColor(projectDetail.color || '#1976d2');
      setProjectName(projectDetail.name || '');
      setLoadingMeta(false);
    });
  }, [projectId, user]);

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

  if (loadingMeta) return <div>Loading...</div>;
  if (loading) return <div>Loading next row...</div>;
  if (!currentRow) return (
    <div>
      <p>All rows annotated!</p>
      <button onClick={() => window.location.hash = '#/projects'}>Back to Projects</button>
    </div>
  );

  return (
    <AnnotationProvider>
      <div style={{ padding: 20 }}>
        <div style={{ height: 3, background: projectColor, marginBottom: 8, borderRadius: 2 }} />
        <button onClick={() => window.location.hash = '#/projects'} style={{ marginBottom: 16 }}>&larr; Back</button>
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
