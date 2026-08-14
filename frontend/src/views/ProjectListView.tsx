import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import SetupView from './SetupView';
import LabelView from './LabelView';
import BrowseView from './BrowseView';

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
  const [view, setView] = useState<'list' | 'setup' | 'label' | 'browse'>('list');
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [templateSource, setTemplateSource] = useState('');
  const [numRows, setNumRows] = useState(0);

  useEffect(() => {
    if (user) {
      api.listProjects(user.user_id).then((res) => setProjects(res.projects));
    }
  }, [user, view]);

  if (!user) return null;

  const isAdmin = user.global_role === 'system_admin' || activeProject?.role === 'project_admin';

  const startLabeling = async (p: Project) => {
    setActiveProject(p);
    const [t, projectDetail] = await Promise.all([
      api.getTemplate(p.template_id),
      api.getProject(p.id, user!.user_id),
    ]);
    setTemplateSource(t.source);
    setNumRows(projectDetail.num_rows || 0);
    setView('label');
  };

  const startBrowsing = (p: Project) => {
    setActiveProject(p);
    setView('browse');
  };

  const goToList = () => {
    setActiveProject(null);
    setView('list');
  };

  if (view === 'setup') return <SetupView onDone={goToList} />;
  if (view === 'label' && activeProject) return <LabelView projectId={activeProject.id} templateSource={templateSource} numRows={numRows} onBack={goToList} />;
  if (view === 'browse' && activeProject) return <BrowseView projectId={activeProject.id} onBack={goToList} />;

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

      {projects.length === 0 && <p>No projects available.</p>}
      {projects.map((p) => (
        <div key={p.id} style={{ border: '1px solid #ccc', padding: 12, marginBottom: 8, borderRadius: 4 }}>
          <strong>{p.name}</strong>
          {p.role && <span style={{ marginLeft: 12, color: '#666' }}>({p.role})</span>}
          <div style={{ marginTop: 8 }}>
            <button onClick={() => startLabeling(p)} style={{ marginRight: 8 }}>Label</button>
            <button onClick={() => startBrowsing(p)}>Browse</button>
          </div>
        </div>
      ))}
    </div>
  );
}

