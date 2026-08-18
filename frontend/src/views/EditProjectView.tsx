import { useEffect, useState, useCallback } from "react";
import { LiveProvider, LiveEditor, LivePreview, LiveError } from "react-live";
import { themes } from "prism-react-renderer";
import { api } from "../api/client";
import * as widgets from "../widgets";
import { AnnotationProvider } from "../context/AnnotationContext";
import BreadcrumbNav from "../components/BreadcrumbNav";
import LoadTemplateDialog from "../components/LoadTemplateDialog";
import WidgetDocs from "../components/WidgetDocs";
import InstructionsButton from "../components/InstructionsButton";

const scope = { ...widgets, useState, useCallback };
const editorTheme = themes.oneLight;

function extractColumns(source: string): Set<string> {
  const cols = new Set<string>();
  const re = /data\.([a-zA-Z_]\w*)/g;
  let m;
  while ((m = re.exec(source)) !== null) {
    cols.add(m[1]);
  }
  return cols;
}

export default function EditProjectView({ projectId }: { projectId: string }) {
  const [templateSource, setTemplateSource] = useState("");
  const [originalSource, setOriginalSource] = useState("");
  const [templateId, setTemplateId] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("");
  const [projectColor, setProjectColor] = useState("#F97316");
  const [projectTags, setProjectTags] = useState("");
  const [projectInstructions, setProjectInstructions] = useState("");
  const [sampleRow, setSampleRow] = useState<any>(null);
  const [datasetLoaded, setDatasetLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showTemplateDialog, setShowTemplateDialog] = useState(false);
  const [mlEnabled, setMlEnabled] = useState(false);
  const [mlUrl, setMlUrl] = useState("");
  const [mlAnnotator, setMlAnnotator] = useState("");
  const [mlMode, setMlMode] = useState("on_navigate");

  useEffect(() => {
    const load = async () => {
      const user = JSON.parse(sessionStorage.getItem("auth_user") || "{}");
      const project = await api.getProject(projectId, user.user_id);
      setProjectName(project.name);
      setProjectColor(project.color || "#F97316");
      setProjectTags(project.tags || "");
      setProjectInstructions(project.instructions || "");
      setMlEnabled(!!project.ml_enabled);
      setMlUrl(project.ml_url || "");
      setMlAnnotator(project.ml_annotator || "");
      setMlMode(project.ml_mode || "on_navigate");
      setTemplateSource(project.template_source || "");
      setOriginalSource(project.template_source || "");
      setTemplateId(project.template_id);
      const row = await api.getRow(project.dataset_id, 0);
      setSampleRow(row.row);
      setDatasetLoaded(true);
    };
    load();
  }, [projectId]);

  const handleSave = async () => {
    if (!templateId) return;
    setSaving(true);
    const oldCols = extractColumns(originalSource);
    const newCols = extractColumns(templateSource);
    const changed =
      oldCols.size !== newCols.size ||
      !Array.from(oldCols).every((c) => newCols.has(c));

    let proceed = true;
    if (changed) {
      const oldList = Array.from(oldCols).join(", ") || "(none)";
      const newList = Array.from(newCols).join(", ") || "(none)";
      proceed = window.confirm(
        `The template schema has changed.\n\nOld columns: ${oldList}\nNew columns: ${newList}\n\nExisting annotations may become incompatible. Continue?`
      );
    }

    if (proceed) {
      await api.updateProject(projectId, projectName, projectColor, projectTags, projectInstructions,
        mlEnabled, mlUrl, mlAnnotator, mlMode);
      await api.updateTemplate(templateId, templateSource);
      window.location.hash = "#/projects";
    }
    setSaving(false);
  };

  const handleSelectTemplate = (tpl: { source: string }) => {
    setTemplateSource(tpl.source);
  };

  return (
    <div className="min-h-screen bg-[var(--color-surface-secondary)]">
      <BreadcrumbNav crumbs={[
        { label: 'Projects', href: '#/projects' },
        { label: projectName || 'Settings' },
      ]} />

      <div className="h-1" style={{ background: projectColor }} />

      <div className="max-w-5xl mx-auto px-6 py-6 animate-fade-in">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-[var(--color-text-heading)]">Settings: {projectName}</h2>
        </div>

        {/* Project Name */}
        <section className="mb-6">
          <div className="bg-white rounded-xl border border-[var(--color-border)] p-5 shadow-sm flex items-center gap-4">
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-[var(--color-text-heading)] mb-2">Project Name</h3>
              <input
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                className="w-full max-w-xs px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400"
              />
            </div>
            <InstructionsButton value={projectInstructions} onChange={setProjectInstructions} />
          </div>
        </section>

        {/* Color & Tags */}
        <section className="mb-6">
          <div className="bg-white rounded-xl border border-[var(--color-border)] p-5 shadow-sm">
            <div className="flex gap-6">
              <div>
                <h3 className="text-sm font-semibold text-[var(--color-text-heading)] mb-2">Color</h3>
                <div className="flex items-center gap-2">
                  <input type="color" value={projectColor}
                         onChange={(e) => setProjectColor(e.target.value)}
                         className="w-9 h-9 p-0.5 border border-[var(--color-border)] rounded-lg cursor-pointer" />
                  <span className="text-xs text-[var(--color-text-muted)]">{projectColor}</span>
                </div>
              </div>
              <div className="flex-1">
                <h3 className="text-sm font-semibold text-[var(--color-text-heading)] mb-2">Tags</h3>
                <input value={projectTags} placeholder="e.g. image, nlp, production"
                       onChange={(e) => setProjectTags(e.target.value)}
                       className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400" />
                <p className="text-xs text-[var(--color-text-muted)] mt-1">Comma-separated</p>
              </div>
            </div>
          </div>
        </section>

        {/* Template */}
        <section className="mb-6">
          <div className="bg-white rounded-xl border border-[var(--color-border)] p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-[var(--color-text-heading)] mb-2">Template</h3>
            <p className="text-sm text-[var(--color-text-muted)] mb-4">
              Available variables: <code className="px-1.5 py-0.5 rounded bg-sunset-50 text-sunset-600 text-xs">data</code> (current row),{" "}
              <code className="px-1.5 py-0.5 rounded bg-sunset-50 text-sunset-600 text-xs">annotations</code> (saved values).
            </p>
            <div className="flex gap-4">
              <div className="flex-1 min-w-0">
                <AnnotationProvider>
                  <LiveProvider code={templateSource} scope={{ ...scope, data: sampleRow || {}, annotations: {} }} theme={editorTheme}>
                    <LiveEditor onChange={setTemplateSource} style={{ textAlign: 'left' }} />
                    <LiveError />
                  </LiveProvider>
                </AnnotationProvider>
                <details className="mt-3 group">
                  <summary className="text-sm font-medium text-[var(--color-text-muted)] cursor-pointer hover:text-[var(--color-text)] select-none">
                    Available widgets
                  </summary>
                  <div className="mt-3">
                    <WidgetDocs />
                  </div>
                </details>
              </div>
              <div className="flex-1 min-w-0 border border-[var(--color-border)] rounded-lg p-3 bg-white">
                <h4 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-2">Preview</h4>
                {sampleRow ? (
                  <AnnotationProvider>
                    <LiveProvider code={templateSource} scope={{ ...scope, data: sampleRow, annotations: {} }}>
                      <LivePreview />
                    </LiveProvider>
                  </AnnotationProvider>
                ) : (
                  <p className="text-sm text-[var(--color-text-muted)]">Loading sample row...</p>
                )}
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              <button
                onClick={handleSave}
                disabled={saving || !datasetLoaded}
                className="px-5 py-2.5 rounded-lg bg-gradient-to-r from-sunset-500 to-coral-500 text-white font-medium text-sm hover:from-sunset-600 hover:to-coral-600 disabled:opacity-50 transition-all shadow-sm"
              >
                {saving ? "Saving..." : "Save"}
              </button>
              <button
                onClick={() => setShowTemplateDialog(true)}
                className="px-4 py-2 rounded-lg border border-[var(--color-border)] bg-white text-sm text-[var(--color-text)] hover:bg-gray-50 transition-all"
              >
                Load Template
              </button>
            </div>
            {showTemplateDialog && (
              <LoadTemplateDialog onSelect={handleSelectTemplate} onClose={() => setShowTemplateDialog(false)} />
            )}
          </div>
        </section>

        {/* ML Backend */}
        <section className="mb-6">
          <div className="bg-white rounded-xl border border-[var(--color-border)] p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-[var(--color-text-heading)] mb-2">ML Backend</h3>
            <div className="flex items-center gap-3 mb-4">
              <label className="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" checked={mlEnabled} onChange={(e) => setMlEnabled(e.target.checked)} className="sr-only peer" />
                <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:bg-sunset-500 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all" />
              </label>
              <span className="text-sm text-[var(--color-text)]">Enable ML auto-prefill</span>
            </div>
            {mlEnabled && (
              <div className="space-y-3">
                <div>
                  <label className="text-xs font-medium text-[var(--color-text-muted)] block mb-1">ML Backend URL</label>
                  <input value={mlUrl} onChange={(e) => setMlUrl(e.target.value)}
                         placeholder="https://your-model.example.com/predict"
                         className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400" />
                </div>
                <div>
                  <label className="text-xs font-medium text-[var(--color-text-muted)] block mb-1">Annotator Name</label>
                  <input value={mlAnnotator} onChange={(e) => setMlAnnotator(e.target.value)}
                         placeholder="e.g. gpt-4o, my-model-v1"
                         className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400" />
                </div>
                <div>
                  <label className="text-xs font-medium text-[var(--color-text-muted)] block mb-1">Prefill Mode</label>
                  <div className="flex gap-4">
                    {[
                      { value: "on_navigate", label: "Auto-prefill on navigate" },
                      { value: "batch", label: "Batch only" },
                      { value: "both", label: "Both" },
                    ].map((opt) => (
                      <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
                        <input type="radio" name="ml-mode" value={opt.value}
                               checked={mlMode === opt.value}
                               onChange={(e) => setMlMode(e.target.value)}
                               className="text-sunset-500 focus:ring-sunset-400" />
                        <span className="text-sm text-[var(--color-text)]">{opt.label}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
