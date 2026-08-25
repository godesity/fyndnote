import { useState } from "react";
import Dialog from "./Dialog";
import { api, ApiError } from "../api/client";

interface Props {
  projectName: string;
  projectId: string;
  onClose: () => void;
}

export default function DeleteProjectDialog({ projectName, projectId, onClose }: Props) {
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const confirmed = confirmText.trim() === "delete";

  const handleDelete = async () => {
    if (!confirmed || deleting) return;
    setDeleting(true);
    setError(null);
    try {
      await api.deleteProject(projectId);
      window.location.hash = "#/projects";
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      setConfirmText("");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Dialog title="Delete project" onClose={onClose} minWidth="460px" closeOnBackdrop={false}>
      <p className="text-sm text-[var(--color-text)] mb-4">
        You are about to delete <strong>{projectName}</strong>. This will permanently remove
        the project and all annotations made on it. This action cannot be undone.
      </p>
      <label className="text-xs font-medium text-[var(--color-text-muted)] block mb-1">
        Type "delete" to confirm
      </label>
      <input
        value={confirmText}
        onChange={(e) => setConfirmText(e.target.value)}
        className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-red-400 mb-4"
      />
      {error && (
        <p className="text-sm text-red-600 mb-4">{error}</p>
      )}
      <div className="flex justify-end gap-2">
        <button
          onClick={onClose}
          disabled={deleting}
          className="px-4 py-2 rounded-lg border border-[var(--color-border)] bg-white text-sm text-[var(--color-text)] hover:bg-gray-50 transition-all disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          onClick={handleDelete}
          disabled={!confirmed || deleting}
          className="px-4 py-2 rounded-lg bg-red-500 text-white font-medium text-sm hover:bg-red-600 transition-all shadow-sm disabled:opacity-50"
        >
          {deleting ? "Deleting..." : "Delete"}
        </button>
      </div>
    </Dialog>
  );
}
