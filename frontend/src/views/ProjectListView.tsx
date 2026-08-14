import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import SetupView from './SetupView';

interface Project {
  id: string;
  name: string;
  dataset_id: string;
  template_id: string;
  created_at: string;
  role?: string;
}

export default function ProjectListView() {
  const { user, logout } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [view, setView] = useState<'list' | 'setup'>('list');

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
          {isAdmin && <button onClick={() => setView('setup')}>New Project</button>}
          <button onClick={logout} style={{ marginLeft: 8 }}>Logout</button>
        </div>
      </div>

      {view === 'setup' && isAdmin ? (
        <SetupView onDone={() => setView('list')} />
      ) : (
        <div>
          {projects.length === 0 && <p>No projects available.</p>}
          {projects.map((p) => (
            <div key={p.id} style={{ border: '1px solid #ccc', padding: 12, marginBottom: 8, borderRadius: 4 }}>
              <strong>{p.name}</strong>
              {p.role && <span style={{ marginLeft: 12, color: '#666' }}>({p.role})</span>}
              <div style={{ marginTop: 8 }}>
                <button style={{ marginRight: 8 }}>Label</button>
                <button>Browse</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

