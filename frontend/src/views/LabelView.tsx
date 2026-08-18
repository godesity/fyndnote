import { useEffect, useState, useCallback, useRef } from 'react';
import { LiveProvider, LivePreview } from 'react-live';
import { themes } from 'prism-react-renderer';
import { useAuth } from '../context/AuthContext';
import { AnnotationProvider } from '../context/AnnotationContext';
import { api } from '../api/client';
import BreadcrumbNav from '../components/BreadcrumbNav';
import { RenderInstructions } from '../components/InstructionsEditor';
import { SkeletonLabelView } from '../components/SkeletonLoader';
import SubmitButton from '../components/SubmitButton';
import * as widgets from '../widgets';

const scope = { ...widgets, useState, useCallback };
const editorTheme = themes.oneLight;

interface Props {
  projectId: string;
}

export default function LabelView({ projectId }: Props) {
  const { user } = useAuth();
  const previewRef = useRef<HTMLDivElement>(null);
  const currentRowRef = useRef<{ index: number; row: Record<string, any> } | null>(null);
  const numRowsRef = useRef(0);
  const navigateToRef = useRef<(rowIndex: number) => void>(() => {});
  const [templateSource, setTemplateSource] = useState('');
  const [numRows, setNumRows] = useState(0);
  const [projectColor, setProjectColor] = useState('#F97316');
  const [projectName, setProjectName] = useState('');
  const [projectInstructions, setProjectInstructions] = useState('');
  const [progressAnnotated, setProgressAnnotated] = useState(0);
  const [loadingMeta, setLoadingMeta] = useState(true);
  const [currentRow, setCurrentRow] = useState<{ index: number; row: Record<string, any> } | null>(null);
  const [annotations, setAnnotations] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [showGuide, setShowGuide] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [isAnnotated, setIsAnnotated] = useState(false);
  const isAnnotatedRef = useRef(false);
  const [mlPrefilling, setMlPrefilling] = useState(false);
  const [mlAnnotator, setMlAnnotator] = useState<string | null>(null);
  const mlSettingsRef = useRef<{ enabled: boolean; mode: string }>({ enabled: false, mode: 'on_navigate' });
  const prefilledRowsRef = useRef<Set<number>>(new Set());

  useEffect(() => {
    if (!user) return;
    api.getProject(projectId, user.user_id).then((projectDetail) => {
      setNumRows(projectDetail.num_rows || 0);
      setTemplateSource(projectDetail.template_source || '');
      setProjectColor(projectDetail.color || '#F97316');
      setProjectName(projectDetail.name || '');
      setProjectInstructions(projectDetail.instructions || '');
      setProgressAnnotated(projectDetail.progress?.annotated_rows || 0);
      mlSettingsRef.current = {
        enabled: !!projectDetail.ml_enabled,
        mode: projectDetail.ml_mode || 'on_navigate',
      };
      setLoadingMeta(false);
    });
  }, [projectId, user]);

  const loadFirstRow = async () => {
    if (!user) return;
    setLoading(true);
    const next = await api.nextRow(projectId, user.user_id);
    if (next.index !== null && next.row !== null) {
      setCurrentRow(next as { index: number; row: Record<string, any> });
      currentRowRef.current = next as { index: number; row: Record<string, any> };
      try {
        const ann = await api.getAnnotation(projectId, next.index, user.user_id);
        setAnnotations(ann.data);
        setIsAnnotated(true);
        isAnnotatedRef.current = true;
      } catch {
        setAnnotations({});
        setIsAnnotated(false);
        isAnnotatedRef.current = false;
      }
      if (!isAnnotatedRef.current) {
        tryMlPrefill(next.index);
      }
    } else {
      setCurrentRow(null);
      currentRowRef.current = null;
    }
    setLoading(false);
  };

  const tryMlPrefill = async (rowIndex: number) => {
    const ml = mlSettingsRef.current;
    if (!ml.enabled || (ml.mode !== 'on_navigate' && ml.mode !== 'both')) return;
    if (prefilledRowsRef.current.has(rowIndex)) return;
    prefilledRowsRef.current.add(rowIndex);
    setMlPrefilling(true);
    try {
      const result = await api.mlPrefill(projectId, rowIndex);
      if (result.annotation) {
        setAnnotations(result.annotation);
        setMlAnnotator(result.annotator);
      }
    } catch {
      // silent fail
    }
    setMlPrefilling(false);
  };

  const fillFromHumanAnnotation = async () => {
    if (!user || !currentRow) return;
    try {
      const ann = await api.getAnnotation(projectId, currentRow.index, user.user_id);
      setAnnotations(ann.data);
    } catch { /* silent */ }
  };

  const fillFromMLAnnotation = async () => {
    if (!currentRow) return;
    try {
      const ann = await api.getMLAnnotation(projectId, currentRow.index);
      setAnnotations(ann.data);
    } catch { /* silent */ }
  };

  const navigateTo = async (rowIndex: number) => {
    if (!user) return;
    setLoading(true);
    try {
      const result = await api.getProjectRow(projectId, rowIndex, user.user_id);
      const row = { index: result.index, row: result.row };
      setCurrentRow(row);
      currentRowRef.current = row;
      setIsAnnotated(result.annotation_status.by_me);
      isAnnotatedRef.current = result.annotation_status.by_me;
      if (result.annotation_status.by_me) {
        const ann = await api.getAnnotation(projectId, result.index, user.user_id);
        setAnnotations(ann.data);
      } else {
        setAnnotations({});
        if (!result.annotation_status.by_me) {
          tryMlPrefill(result.index);
        }
      }
    } catch {
      setCurrentRow(null);
      currentRowRef.current = null;
    }
    setLoading(false);
  };

  const navigateShuffle = async (direction: 1 | -1) => {
    if (!user) return;
    const row = currentRowRef.current;
    if (!row) return;
    setLoading(true);
    try {
      const result = await api.navigateRow(projectId, row.index, user.user_id, direction);
      const newRow = { index: result.index, row: result.row };
      setCurrentRow(newRow);
      currentRowRef.current = newRow;
      setIsAnnotated(result.annotation_status.by_me);
      isAnnotatedRef.current = result.annotation_status.by_me;
      if (result.annotation_status.by_me) {
        const ann = await api.getAnnotation(projectId, result.index, user.user_id);
        setAnnotations(ann.data);
      } else {
        setAnnotations({});
        if (!result.annotation_status.by_me) {
          tryMlPrefill(result.index);
        }
      }
    } catch {
      setLoading(false);
    }
    setLoading(false);
  };

  useEffect(() => {
    navigateToRef.current = navigateTo;
  }, [navigateTo]);

  const navigateShuffleRef = useRef(navigateShuffle);
  useEffect(() => {
    navigateShuffleRef.current = navigateShuffle;
  }, [navigateShuffle]);

  const handleSubmitted = () => {
    setIsAnnotated(true);
    navigateShuffleRef.current(1);
  };

  useEffect(() => {
    numRowsRef.current = numRows;
  }, [numRows]);

  useEffect(() => {
    loadFirstRow();
  }, [projectId]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        const row = currentRowRef.current;
        if (!row) return;
        const tag = e.target as HTMLElement;
        if (tag instanceof HTMLTextAreaElement) return;
        if (tag instanceof HTMLInputElement) {
          const textInputs = ['text', 'email', 'url', 'search', 'tel', 'number', 'password', 'date', 'datetime-local', 'month', 'week', 'time'];
          if (textInputs.includes(tag.type)) return;
        }
        e.preventDefault();
        navigateShuffleRef.current(e.key === 'ArrowLeft' ? -1 : 1);
        return;
      }

      if (e.key === 'Escape') {
        window.location.hash = '#/projects';
        return;
      }

      if (e.key === 'Enter') {
        const tag = e.target as HTMLElement;
        if (tag instanceof HTMLTextAreaElement) return;
        if (tag instanceof HTMLInputElement) {
          const textInputs = ['text', 'email', 'url', 'search', 'tel', 'number', 'password', 'date', 'datetime-local', 'month', 'week', 'time'];
          if (textInputs.includes(tag.type)) return;
        }
        const btn = document.querySelector('[data-submit-btn]') as HTMLButtonElement | null;
        if (btn && !btn.disabled) btn.click();
        return;
      }

      if (e.key === 'g' || e.key === 'G') {
        setShowGuide((prev) => !prev);
        return;
      }

      const idx = (() => {
        if (e.key >= '1' && e.key <= '9') return parseInt(e.key) - 1;
        if (e.key === '0') return 9;
        return -1;
      })();
      if (idx < 0) return;
      if (!previewRef.current) return;

      const tag = e.target as HTMLElement;
      if (tag instanceof HTMLTextAreaElement) return;
      if (tag instanceof HTMLInputElement) {
        const textInputs = ['text', 'email', 'url', 'search', 'tel', 'number', 'password', 'date', 'datetime-local', 'month', 'week', 'time'];
        if (textInputs.includes(tag.type)) return;
      }

      e.preventDefault();
      const sel = previewRef.current.querySelector<HTMLSelectElement>('select');
      if (sel && idx < sel.options.length) {
        sel.selectedIndex = idx;
        sel.dispatchEvent(new Event('change', { bubbles: true }));
        return;
      }
      const els = previewRef.current.querySelectorAll<HTMLElement>(
        'input:not([type="hidden"]), textarea, button, [tabindex]:not([tabindex="-1"])'
      );
      const el = els[idx];
      if (!el) return;

      if (el instanceof HTMLInputElement && (el.type === 'checkbox' || el.type === 'radio')) {
        el.checked = !el.checked;
        el.dispatchEvent(new Event('change', { bubbles: true }));
      } else if (el instanceof HTMLButtonElement) {
        el.click();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  if (loadingMeta) return <SkeletonLabelView />;
  if (loading) return <SkeletonLabelView />;
  if (!currentRow) return (
    <div className="min-h-screen bg-[var(--color-surface-secondary)]">
      <BreadcrumbNav crumbs={[
        { label: 'Projects', href: '#/projects' },
        { label: projectName },
      ]} />
      <div className="max-w-xl mx-auto px-6 py-20 text-center animate-fade-in">
        <div className="w-16 h-16 rounded-full bg-gradient-to-br from-sunset-100 to-coral-100 flex items-center justify-center mx-auto mb-4">
          <span className="text-2xl">🎉</span>
        </div>
        <h2 className="text-xl font-bold text-[var(--color-text-heading)] mb-2">All rows annotated!</h2>
        <p className="text-sm text-[var(--color-text-muted)] mb-6">Great work — no more rows to label.</p>
        <button
          onClick={() => window.location.hash = '#/projects'}
          className="px-5 py-2.5 rounded-lg bg-gradient-to-r from-sunset-500 to-coral-500 text-white font-medium text-sm hover:from-sunset-600 hover:to-coral-600 transition-all shadow-sm"
        >
          Back to Projects
        </button>
      </div>
    </div>
  );

  const pct = numRows > 0 ? Math.round((progressAnnotated / numRows) * 100) : 0;

  return (
    <AnnotationProvider>
      <div className="min-h-screen bg-[var(--color-surface-secondary)]">
        <BreadcrumbNav crumbs={[
          { label: 'Projects', href: '#/projects' },
          { label: projectName },
        ]} />

        {/* Color indicator */}
        <div className="h-1" style={{ background: projectColor }} />

        <div className="max-w-4xl mx-auto px-6 py-4 animate-fade-in">
          {/* Progress bar */}
          <div className="mb-4">
            <div className="flex justify-between text-sm text-[var(--color-text-muted)] mb-1.5">
              <span>Progress: {progressAnnotated} / {numRows} rows</span>
              <span>{pct}%</span>
            </div>
            <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500 ease-out"
                style={{ width: `${pct}%`, background: projectColor }}
              />
            </div>
          </div>

          <div className="flex gap-0">
            {/* Content area */}
            <div className="flex-1 min-w-0">
              {/* Labeling card */}
              <div className="bg-white border border-[var(--color-border)] rounded-s-xl shadow-sm">
                <div ref={previewRef} className="p-5 min-h-[300px]">
                  <LiveProvider
                    code={templateSource}
                    scope={{ ...scope, data: currentRow.row, annotations }}
                    theme={editorTheme}
                  >
                    <LivePreview />
                  </LiveProvider>
                </div>

                {/* Bottom bar: submit + tip */}
                <div className="flex items-center gap-3 px-5 py-3 border-t border-[var(--color-border)]">
                  <div className="flex items-center gap-2">
                    <SubmitButton projectId={projectId} rowIndex={currentRow.index} onSubmitted={handleSubmitted} />
                    <button onClick={fillFromHumanAnnotation}
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium cursor-pointer transition-colors ${
                      isAnnotated
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100'
                        : 'bg-gray-100 text-gray-500 border border-gray-200'
                    }`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${isAnnotated ? 'bg-emerald-500' : 'bg-gray-400'}`} />
                      {isAnnotated ? 'Annotated' : 'Not annotated'}
                    </button>
                    {mlPrefilling && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-violet-50 text-violet-700 border border-violet-200">
                        <span className="w-1.5 h-1.5 rounded-full bg-violet-500 animate-pulse" />
                        AI prefilling...
                      </span>
                    )}
                    {mlAnnotator && !mlPrefilling && (
                      <button onClick={fillFromMLAnnotation}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 cursor-pointer transition-colors">
                        AI: {mlAnnotator}
                      </button>
                    )}
                  </div>

                  <div className="flex items-center gap-2 px-3 py-1.5 bg-sunset-50 border border-sunset-200 rounded-lg text-sm text-sunset-700 flex-1 min-w-0">
                    <span className="text-xs truncate">
                      <kbd className="px-1 py-0.5 rounded bg-white border border-sunset-200 text-xs font-mono">1-9</kbd> select,
                      <kbd className="px-1 py-0.5 rounded bg-white border border-sunset-200 text-xs font-mono ml-1">Enter</kbd> submit,
                      <kbd className="px-1 py-0.5 rounded bg-white border border-sunset-200 text-xs font-mono ml-1">←</kbd>
                      <kbd className="px-1 py-0.5 rounded bg-white border border-sunset-200 text-xs font-mono">→</kbd> nav
                    </span>
                    <button
                      onClick={() => setShowShortcuts(true)}
                      className="text-sunset-600 font-semibold hover:text-sunset-700 transition-colors text-xs whitespace-nowrap flex-shrink-0"
                    >
                      More shortcuts →
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Guidelines vertical tab */}
            <button
              onClick={() => setShowGuide(!showGuide)}
              className="w-8 rounded-r-xl rounded-l-none bg-gradient-to-b from-sunset-500 to-coral-500 flex items-center justify-center cursor-pointer hover:from-sunset-600 hover:to-coral-600 transition-all flex-shrink-0 shadow-sm border border-l-0 border-[var(--color-border)]"
              title="Annotation guidelines"
            >
              <span className="text-white text-xs whitespace-nowrap [writing-mode:vertical-rl] tracking-widest">
                📋 Guidelines
              </span>
            </button>
          </div>
        </div>

        {/* Guidelines drawer */}
        {showGuide && (
          <div className="fixed inset-y-0 right-0 w-80 bg-white shadow-xl border-l border-[var(--color-border)] z-50 animate-slide-in">
            <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]">
              <h3 className="font-semibold text-[var(--color-text-heading)] text-sm">Annotation Guidelines</h3>
              <button onClick={() => setShowGuide(false)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] text-lg leading-none">&times;</button>
            </div>
            <div className="p-5 text-sm text-[var(--color-text)] overflow-y-auto max-h-[calc(100vh-60px)]">
              {projectInstructions ? (
                <RenderInstructions html={projectInstructions} />
              ) : (
                <p className="text-[var(--color-text-muted)] italic">No guidelines set for this project. Edit the project to add instructions.</p>
              )}
            </div>
          </div>
        )}

        {/* Shortcuts modal */}
        {showShortcuts && (
          <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 animate-fade-in" onClick={() => setShowShortcuts(false)}>
            <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4 animate-fade-in" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-[var(--color-text-heading)]">Keyboard Shortcuts</h3>
                <button onClick={() => setShowShortcuts(false)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] text-lg leading-none">&times;</button>
              </div>
              <div className="space-y-2.5 text-sm">
                <div className="flex justify-between"><span>Select option 1-9</span> <kbd className="px-2 py-0.5 rounded bg-gray-100 border border-gray-200 text-xs font-mono">1-9</kbd></div>
                <div className="flex justify-between"><span>Submit annotation</span> <kbd className="px-2 py-0.5 rounded bg-gray-100 border border-gray-200 text-xs font-mono">Enter</kbd></div>
                <div className="flex justify-between"><span>Previous row</span> <kbd className="px-2 py-0.5 rounded bg-gray-100 border border-gray-200 text-xs font-mono">←</kbd></div>
                <div className="flex justify-between"><span>Next row</span> <kbd className="px-2 py-0.5 rounded bg-gray-100 border border-gray-200 text-xs font-mono">→</kbd></div>
                <div className="flex justify-between"><span>Toggle guidelines</span> <kbd className="px-2 py-0.5 rounded bg-gray-100 border border-gray-200 text-xs font-mono">G</kbd></div>
                <div className="flex justify-between"><span>Back to projects</span> <kbd className="px-2 py-0.5 rounded bg-gray-100 border border-gray-200 text-xs font-mono">Esc</kbd></div>
              </div>
            </div>
          </div>
        )}
      </div>
    </AnnotationProvider>
  );
}
