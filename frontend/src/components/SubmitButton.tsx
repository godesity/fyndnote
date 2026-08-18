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
    <button onClick={handleSubmit} disabled={saving} data-submit-btn
            className="px-5 py-2.5 rounded-lg bg-gradient-to-r from-sunset-500 to-coral-500 text-white font-medium text-sm hover:from-sunset-600 hover:to-coral-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm">
      {saving ? 'Saving...' : 'Submit & Next'}
    </button>
  );
}
