import { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginView from './views/LoginView';
import ProjectListView from './views/ProjectListView';

function AppContent() {
  const { user } = useAuth();
  if (!user) return <LoginView />;
  return <ProjectListView />;
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
