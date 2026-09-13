import { useEffect, useState } from "react";
import {
  api,
  ApiError,
  type ProjectMember,
  type ProjectMemberCandidate,
  type ProjectRole,
} from "../api/client";

interface Props {
  projectId: string;
  /** The signed-in user; used as the actor for every membership mutation. */
  userId: string;
}

const ROLES: { value: ProjectRole; label: string }[] = [
  { value: "project_admin", label: "Project admin" },
  { value: "annotator", label: "Annotator" },
];

/**
 * Membership editor for a project's settings page. Only rendered for callers the
 * backend reports as `can_manage` (project admins / global admins); the routes
 * themselves enforce the same rule, so this is presentation, not the check.
 */
export default function ProjectMembers({ projectId, userId }: Props) {
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [candidates, setCandidates] = useState<ProjectMemberCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [newRole, setNewRole] = useState<ProjectRole>("annotator");

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .listProjectMembers(projectId, userId)
      .then(setMembers)
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [projectId, userId]);

  // Debounced search over users who are not members yet.
  useEffect(() => {
    const handle = setTimeout(() => {
      api
        .listMemberCandidates(projectId, userId, query)
        .then(setCandidates)
        .catch(() => setCandidates([]));
    }, 200);
    return () => clearTimeout(handle);
  }, [projectId, userId, query]);

  // Shared mutation path: run the call, reload the roster, surface the outcome.
  const mutate = async (action: () => Promise<unknown>, success: string) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      setMembers(await api.listProjectMembers(projectId, userId));
      setNotice(success);
      setQuery("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] p-5 shadow-sm">
      <h3 className="text-sm font-semibold text-[var(--color-text-heading)] mb-2">Members</h3>
      <p className="text-sm text-[var(--color-text-muted)] mb-4">
        Project admins can configure the project and manage its members; annotators can only label
        rows. Global admins always have access to every project.
      </p>

      {loading ? (
        <p className="text-sm text-[var(--color-text-muted)]">Loading members...</p>
      ) : members.length === 0 ? (
        <p className="text-sm text-[var(--color-text-muted)] mb-4">
          Nobody has access to this project yet.
        </p>
      ) : (
        <div className="divide-y divide-[var(--color-border)] mb-4">
          {members.map((m) => (
            <div key={m.user_id} className="flex items-center gap-3 py-2">
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium text-[var(--color-text-heading)]">
                  {m.name || m.user_id}
                </span>
                {m.user_id !== m.name && (
                  <span className="ml-2 text-xs text-[var(--color-text-muted)]">{m.user_id}</span>
                )}
                <span className="ml-2 text-xs text-[var(--color-text-muted)]">
                  global: {m.global_role}
                </span>
                {m.user_id === userId && <span className="ml-2 text-xs text-sunset-600">(you)</span>}
              </div>
              <select
                value={m.role}
                disabled={busy}
                onChange={(e) =>
                  mutate(
                    () =>
                      api.setProjectMember(
                        projectId,
                        m.user_id,
                        e.target.value as ProjectRole,
                        userId
                      ),
                    `Updated ${m.user_id} to ${e.target.value}`
                  )
                }
                className="px-2 py-1 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] focus:outline-none focus:border-sunset-400 disabled:opacity-50"
              >
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
              <button
                onClick={() =>
                  mutate(
                    () => api.removeProjectMember(projectId, m.user_id, userId),
                    `Removed ${m.user_id}`
                  )
                }
                disabled={busy}
                className="px-3 py-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm text-red-600 hover:bg-red-50 transition-all disabled:opacity-50"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search users by id or name"
          className="flex-1 min-w-[180px] px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400"
        />
        <select
          value={newRole}
          onChange={(e) => setNewRole(e.target.value as ProjectRole)}
          className="px-2 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] focus:outline-none focus:border-sunset-400"
        >
          {ROLES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      </div>

      {candidates.length > 0 ? (
        <div className="mt-3 divide-y divide-[var(--color-border)] border border-[var(--color-border)] rounded-lg overflow-hidden">
          {candidates.map((c) => (
            <div key={c.user_id} className="flex items-center gap-3 px-3 py-2">
              <div className="flex-1 min-w-0">
                <span className="text-sm text-[var(--color-text-heading)]">{c.name}</span>
                <span className="ml-2 text-xs text-[var(--color-text-muted)]">
                  {c.user_id} · global: {c.global_role}
                </span>
              </div>
              <button
                onClick={() =>
                  mutate(
                    () => api.setProjectMember(projectId, c.user_id, newRole, userId),
                    `Added ${c.user_id} as ${newRole}`
                  )
                }
                disabled={busy}
                className="px-3 py-1 rounded-lg bg-gradient-to-r from-sunset-500 to-coral-500 text-white text-sm hover:from-sunset-600 hover:to-coral-600 transition-all shadow-sm disabled:opacity-50"
              >
                Add
              </button>
            </div>
          ))}
        </div>
      ) : (
        query.trim() !== "" && (
          <p className="text-xs text-[var(--color-text-muted)] mt-2">
            No non-member users match that search.
          </p>
        )
      )}

      {notice && <p className="text-sm text-green-600 mt-3">{notice}</p>}
      {error && <p className="text-sm text-red-500 mt-3">{error}</p>}
    </div>
  );
}
