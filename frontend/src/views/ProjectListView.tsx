import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import BreadcrumbNav from '../components/BreadcrumbNav';
import GradientBorderCard from '../components/GradientBorderCard';
import { SkeletonCard } from '../components/SkeletonLoader';

interface Project {
  id: string;
  name: string;
  dataset_id: string;
  template_id: string;
  color: string;
  tags: string;
  created_at: string;
  role?: string;
}

type ViewMode = 'grid' | 'list';

export default function ProjectListView() {
  const { user, logout } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [nameFilter, setNameFilter] = useState('');
  const [tagsFilter, setTagsFilter] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (user) {
      setLoading(true);
      api.listProjects(user.user_id).then((res) => {
        setProjects(res.projects);
        setLoading(false);
      });
    }
  }, [user]);

  if (!user) return null;

  const isAdmin = user.global_role === 'system_admin';

  const filtered = projects.filter((p) => {
    if (nameFilter && !p.name.toLowerCase().includes(nameFilter.toLowerCase())) return false;
    if (tagsFilter && !p.tags.toLowerCase().includes(tagsFilter.toLowerCase())) return false;
    return true;
  });

  const toggleExpand = (id: string) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="min-h-screen bg-[var(--color-surface-secondary)]">
      <BreadcrumbNav crumbs={[{ label: 'Projects' }]} />

      <div className="max-w-5xl mx-auto px-6 py-6 animate-fade-in">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-[var(--color-text-heading)]">Projects</h1>
          <div className="flex items-center gap-3">
            <span className="text-sm text-[var(--color-text-muted)]">
              {user.name}
              <span className="ml-1 text-xs opacity-60">({user.global_role})</span>
            </span>
            {isAdmin && (
              <button
                onClick={() => window.location.hash = '#/projects/new'}
                className="px-4 py-2 rounded-lg bg-gradient-to-r from-sunset-500 to-coral-500 text-white text-sm font-medium hover:from-sunset-600 hover:to-coral-600 transition-all shadow-sm"
              >
                + New Project
              </button>
            )}
            <button
              onClick={logout}
              className="px-3 py-2 rounded-lg border border-[var(--color-border)] bg-white text-sm text-[var(--color-text)] hover:bg-gray-50 transition-all"
            >
              Logout
            </button>
          </div>
        </div>

        <div className="flex gap-3 mb-4">
          <input
            value={nameFilter}
            onChange={(e) => setNameFilter(e.target.value)}
            placeholder="Filter by name..."
            className="flex-1 px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-white focus:outline-none focus:border-sunset-400 focus:ring-3 focus:ring-sunset-100 transition-all"
          />
          <input
            value={tagsFilter}
            onChange={(e) => setTagsFilter(e.target.value)}
            placeholder="Filter by tag..."
            className="flex-1 px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-white focus:outline-none focus:border-sunset-400 focus:ring-3 focus:ring-sunset-100 transition-all"
          />
        </div>

        {/* View toggle */}
        <div className="flex items-center gap-1 mb-5 bg-white border border-[var(--color-border)] rounded-lg p-0.5 w-fit shadow-sm">
          <button
            onClick={() => setViewMode('grid')}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${viewMode === 'grid' ? 'bg-gradient-to-r from-sunset-500 to-coral-500 text-white shadow-sm' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'}`}
          >
            ▦ Grid
          </button>
          <button
            onClick={() => setViewMode('list')}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${viewMode === 'list' ? 'bg-gradient-to-r from-sunset-500 to-coral-500 text-white shadow-sm' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'}`}
          >
            ☰ List
          </button>
        </div>

        {loading ? (
          viewMode === 'grid' ? (
            <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
              {[1, 2, 3].map((i) => <SkeletonCard key={i} />)}
            </div>
          ) : (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-14 rounded-lg bg-gray-100 animate-pulse" />
              ))}
            </div>
          )
        ) : filtered.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-[var(--color-text-muted)]">No projects available.</p>
          </div>
        ) : viewMode === 'grid' ? (
          /* ---- Grid view ---- */
          <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
            {filtered.map((p) => (
              <GradientBorderCard key={p.id} color={p.color || undefined} gradient={undefined}>
                <div className="p-5">
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className="w-3 h-3 rounded-full flex-shrink-0"
                      style={{ background: p.color || '#F97316' }}
                    />
                    <strong
                      className="text-[var(--color-text-heading)] cursor-pointer hover:text-sunset-600 transition-colors"
                      onClick={() => window.location.hash = `#/projects/${p.id}/label`}
                    >
                      {p.name}
                    </strong>
                    {p.role && (
                      <span className="text-xs text-[var(--color-text-muted)]">({p.role})</span>
                    )}
                  </div>
                  {p.tags && (
                    <div className="flex gap-1.5 flex-wrap mt-2">
                      {p.tags.split(',').map((t, i) => (
                        <span
                          key={i}
                          className="text-xs px-2 py-0.5 rounded-full bg-sunset-50 text-sunset-600 border border-sunset-200"
                        >
                          {t.trim()}
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="flex gap-2 mt-4">
                    <button
                      onClick={() => window.location.hash = `#/projects/${p.id}/label`}
                      className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-sunset-500 to-coral-500 text-white text-sm hover:from-sunset-600 hover:to-coral-600 transition-all shadow-sm"
                    >
                      Label
                    </button>
                    <button
                      onClick={() => window.location.hash = `#/projects/${p.id}/browse`}
                      className="px-3 py-1.5 rounded-lg border border-[var(--color-border)] bg-white text-sm text-[var(--color-text)] hover:bg-gray-50 transition-all"
                    >
                      Browse
                    </button>
                    {isAdmin && (
                      <button
                        onClick={() => window.location.hash = `#/projects/${p.id}/edit`}
                        className="px-3 py-1.5 rounded-lg border border-[var(--color-border)] bg-white text-sm text-[var(--color-text)] hover:bg-gray-50 transition-all"
                      >
                        Settings
                      </button>
                    )}
                  </div>
                </div>
              </GradientBorderCard>
            ))}
          </div>
        ) : (
          /* ---- List view ---- */
          <div className="bg-white rounded-lg border border-[var(--color-border)] overflow-hidden shadow-sm">
            <div className="divide-y divide-[var(--color-border)]">
            {filtered.map((p) => {
              const isOpen = expanded[p.id] || false;
              return (
                <div key={p.id}>
                  <div className="flex items-center gap-3 px-4 py-3">
                    <span
                      className="w-3 h-3 rounded-full flex-shrink-0"
                      style={{ background: p.color || '#F97316' }}
                    />
                    <span
                      className="flex-1 font-medium text-[var(--color-text-heading)] text-sm cursor-pointer hover:text-sunset-600 transition-colors"
                      onClick={() => window.location.hash = `#/projects/${p.id}/label`}
                    >
                      {p.name}
                    </span>
                    {p.tags && (
                      <div className="flex gap-1">
                        {p.tags.split(',').map((t, i) => (
                          <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-sunset-50 text-sunset-600 border border-sunset-200">
                            {t.trim()}
                          </span>
                        ))}
                      </div>
                    )}
                    <button
                      onClick={() => toggleExpand(p.id)}
                      className="p-1 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-gray-100 transition-all"
                      title="Actions"
                    >
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                        <circle cx="8" cy="3" r="1.5" />
                        <circle cx="8" cy="8" r="1.5" />
                        <circle cx="8" cy="13" r="1.5" />
                      </svg>
                    </button>
                  </div>
                  {isOpen && (
                    <div className="flex gap-2 px-4 pb-3">
                      <div className="flex gap-2 pt-2">
                        <button
                          onClick={() => window.location.hash = `#/projects/${p.id}/label`}
                          className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-sunset-500 to-coral-500 text-white text-xs font-medium hover:from-sunset-600 hover:to-coral-600 transition-all shadow-sm"
                        >
                          Label
                        </button>
                        <button
                          onClick={() => window.location.hash = `#/projects/${p.id}/browse`}
                          className="px-3 py-1.5 rounded-lg border border-[var(--color-border)] bg-white text-xs text-[var(--color-text)] hover:bg-gray-50 transition-all"
                        >
                          Browse
                        </button>
                        {isAdmin && (
                          <button
                            onClick={() => window.location.hash = `#/projects/${p.id}/edit`}
                            className="px-3 py-1.5 rounded-lg border border-[var(--color-border)] bg-white text-xs text-[var(--color-text)] hover:bg-gray-50 transition-all"
                          >
                            Settings
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
