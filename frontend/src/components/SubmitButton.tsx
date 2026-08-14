import { useState } from 'react';
import { useAnnotationContext } from '../context/AnnotationContext';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';

interface Props {
  projectId: string;
  rowIndex: number;
  onSubmitted: () => void;
}

export default function SubmitButton({ projectId, rowIndex, onSubmitted }: Props) {
  const { getAnnotations } = useAnnotationContext();
  const { user } = useAuth();
  const [saving, setSaving] = useState(false);

  const handleSubmit = async () => {
    if (!user) return;
    setSaving(true);
    const data = getAnnotations();
    await api.submitAnnotation(projectId, rowIndex, user.user_id, data);
    setSaving(false);
    onSubmitted();
  };

  return (
    <button onClick={handleSubmit} disabled={saving}
            style={{ marginTop: 16, padding: '10px 24px', fontSize: 16 }}>
      {saving ? 'Saving...' : 'Submit & Next'}
    </button>
  );
}
