import { AuthProvider, useAuth } from './context/AuthContext';
import useHashLocation from './hooks/useHashLocation';
import LoginView from './views/LoginView';
import ProjectListView from './views/ProjectListView';
import SetupView from './views/SetupView';
import LabelView from './views/LabelView';
import BrowseView from './views/BrowseView';

function NotFound() {
  return <div style={{ padding: 20 }}><h2>404 Not Found</h2></div>;
}

function matchRoute(parts: string[]): { component: JSX.Element; id?: string } {
  if (parts.length === 0 || (parts.length === 1 && parts[0] === 'projects')) {
    return { component: <ProjectListView /> };
  }
  if (parts.length === 2 && parts[0] === 'projects' && parts[1] === 'new') {
    return { component: <SetupView /> };
  }
  if (parts.length === 3 && parts[0] === 'projects') {
    const id = parts[1];
    if (parts[2] === 'label') return { component: <LabelView projectId={id} />, id };
    if (parts[2] === 'browse') return { component: <BrowseView projectId={id} />, id };
  }
  return { component: <NotFound /> };
}

function AppContent() {
  const { user } = useAuth();
  const { parts } = useHashLocation();

  if (!user) return <LoginView />;

  const { component } = matchRoute(parts);
  return component;
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
