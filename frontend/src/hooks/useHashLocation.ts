import { useState, useEffect, useCallback } from 'react';

function parseHash(): string[] {
  const hash = window.location.hash.replace(/^#\/?/, '');
  if (!hash) return [];
  return hash.split('/').filter(Boolean);
}

export default function useHashLocation() {
  const [parts, setParts] = useState<string[]>(parseHash);

  useEffect(() => {
    const onHashChange = () => setParts(parseHash());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const navigate = useCallback((path: string) => {
    window.location.hash = path;
  }, []);

  return { parts, navigate };
}
