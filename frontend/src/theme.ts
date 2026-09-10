import { useEffect, useState } from 'react';

export type ThemeMode = 'dark' | 'light';
const KEY = 'fyndnote_theme';
const EVENT = 'fyndnote-theme-change';

export function getTheme(): ThemeMode {
  const stored = localStorage.getItem(KEY);
  if (stored === 'dark' || stored === 'light') return stored;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function applyTheme(mode: ThemeMode, persist = true): void {
  if (persist) localStorage.setItem(KEY, mode);
  document.documentElement.classList.toggle('dark', mode === 'dark');
  window.dispatchEvent(new Event(EVENT));
}

export function initTheme(): void {
  applyTheme(getTheme(), false);
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!localStorage.getItem(KEY)) applyTheme(e.matches ? 'dark' : 'light', false);
  });
}

/** Resolved value of a CSS custom property — canvas/SVG need computed colors, not var(). */
export function cssVar(name: string, fallback = ''): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

export function subscribeTheme(cb: () => void): () => void {
  window.addEventListener(EVENT, cb);
  return () => window.removeEventListener(EVENT, cb);
}

/** Re-render trigger: bumps whenever the theme changes. */
export function useThemeVersion(): number {
  const [v, setV] = useState(0);
  useEffect(() => subscribeTheme(() => setV((n) => n + 1)), []);
  return v;
}
