import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';

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

export default function ProjectListView() {
  const { user, logout } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);

  useEffect(() => {
    if (user) {
      api.listProjects(user.user_id).then((res) => setProjects(res.projects));
    }
  }, [user]);

  if (!user) return null;

  const isAdmin = user.global_role === 'system_admin';

  return (
    <div style={{ padding: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <h1>Projects</h1>
        <div>
          <span style={{ marginRight: 12 }}>{user.name} ({user.global_role})</span>
          {isAdmin && <button onClick={() => window.location.hash = '#/projects/new'}>New Project</button>}
          <button onClick={logout} style={{ marginLeft: 8 }}>Logout</button>
        </div>
      </div>

      {projects.length === 0 && <p>No projects available.</p>}
      {projects.map((p) => (
        <div key={p.id} style={{ border: '1px solid #ccc', padding: 12, marginBottom: 8, borderRadius: 4 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 14, height: 14, borderRadius: '50%', background: p.color || '#1976d2', display: 'inline-block', flexShrink: 0 }} />
            <strong>{p.name}</strong>
            {p.role && <span style={{ color: '#666' }}>({p.role})</span>}
          </div>
          {p.tags && (
            <div style={{ marginTop: 4, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {p.tags.split(',').map((t, i) => (
                <span key={i} style={{ fontSize: 11, background: '#e0e0e0', padding: '1px 6px', borderRadius: 3 }}>{t.trim()}</span>
              ))}
            </div>
          )}
          <div style={{ marginTop: 8 }}>
            <button onClick={() => window.location.hash = `#/projects/${p.id}/label`} style={{ marginRight: 8 }}>Label</button>
            <button onClick={() => window.location.hash = `#/projects/${p.id}/browse`} style={{ marginRight: 8 }}>Browse</button>
            {isAdmin && <button onClick={() => window.location.hash = `#/projects/${p.id}/edit`}>Settings</button>}
          </div>
        </div>
      ))}
    </div>
  );
}
