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

const DEFAULT_TEMPLATE = `<div style={{ padding: 20 }}>
  <h3>Classify the sentiment</h3>
  <p style={{ fontSize: 18 }}>{data.text}</p>
  <SelectField
    name="sentiment"
    labels={["positive", "negative", "neutral"]}
    defaultValue={annotations?.sentiment}
  />
</div>`;

export default function SetupView() {
  const [datasets, setDatasets] = useState<any[]>([]);
  const [selectedDataset, setSelectedDataset] = useState("");
  const [templateSource, setTemplateSource] = useState(DEFAULT_TEMPLATE);
  const [templateId, setTemplateId] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("");
  const [projectColor, setProjectColor] = useState("#F97316");
  const [projectTags, setProjectTags] = useState("");
  const [projectInstructions, setProjectInstructions] = useState("");
  const [mlEnabled, setMlEnabled] = useState(false);
  const [mlUrl, setMlUrl] = useState("");
  const [mlAnnotator, setMlAnnotator] = useState("");
  const [mlMode, setMlMode] = useState("on_navigate");
  const [sampleRow, setSampleRow] = useState<any>(null);
  const [validated] = useState(false);
  const [loadInput, setLoadInput] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showLoadDialog, setShowLoadDialog] = useState(false);
  const [showTemplateDialog, setShowTemplateDialog] = useState(false);
  const [datasetSearch, setDatasetSearch] = useState("");
  const [sampleError, setSampleError] = useState<string | null>(null);

  useEffect(() => {
    api.listDatasets().then((res) => setDatasets(res.datasets));
  }, []);

  const loadSample = async (dsId: string) => {
    setSelectedDataset(dsId);
    setSampleError(null);
    try {
      const row = await api.getRow(dsId, 0);
      setSampleRow(row.row);
    } catch {
      setSampleRow(null);
      setSampleError("Failed to load sample row — dataset source may no longer be available");
    }
  };

  const saveTemplate = async () => {
    if (templateId) {
      await api.updateTemplate(templateId, templateSource, validated);
    } else {
      const t = await api.createTemplate("custom", templateSource);
      setTemplateId(t.id);
    }
  };

  const createProject = async () => {
    if (!projectName || !selectedDataset || !templateId) return;
    await api.createProject(projectName, selectedDataset, templateId, projectColor, projectTags, projectInstructions,
      mlEnabled, mlUrl, mlAnnotator, mlMode);
    window.location.hash = '#/projects';
  };

  const handleLoad = async () => {
    if (!loadInput.trim()) return;
    setLoading(true);
    setLoadError(null);
    try {
      const meta = await api.loadDataset(loadInput.trim());
      setLoadInput("");
      setShowLoadDialog(false);
      const res = await api.listDatasets();
      setDatasets(res.datasets);
      await loadSample(meta.id);
    } catch (err: any) {
      setLoadError(err.message || "Failed to load dataset");
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setLoadError(null);
    try {
      const meta = await api.uploadDataset(file);
      const res = await api.listDatasets();
      setDatasets(res.datasets);
      await loadSample(meta.id);
    } catch (err: any) {
      setLoadError(err.message || "Failed to upload dataset");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectTemplate = (tpl: { source: string }) => {
    setTemplateSource(tpl.source);
  };

  return (
    <div className="min-h-screen bg-[var(--color-surface-secondary)]">
      <BreadcrumbNav crumbs={[
        { label: 'Projects', href: '#/projects' },
        { label: 'New Project' },
      ]} />

      <div className="max-w-5xl mx-auto px-6 py-6 animate-fade-in">
        <h2 className="text-xl font-bold text-[var(--color-text-heading)] mb-6">Setup Project</h2>

        {/* Step 1: Select Dataset */}
        <section className="mb-6">
          <h3 className="text-base font-semibold text-[var(--color-text-heading)] mb-3">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-gradient-to-br from-sunset-500 to-coral-500 text-white text-xs font-bold mr-2">1</span>
            Select Dataset
          </h3>
          <div className="bg-white rounded-xl border border-[var(--color-border)] p-5 shadow-sm">
            <input
              value={datasetSearch}
              onChange={(e) => setDatasetSearch(e.target.value)}
              placeholder="Filter datasets..."
              className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm mb-3 focus:outline-none focus:border-sunset-400 focus:ring-3 focus:ring-sunset-100"
            />
            <div className="flex gap-2">
              <select
                value={selectedDataset}
                onChange={(e) => loadSample(e.target.value)}
                className="flex-1 px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-white focus:outline-none focus:border-sunset-400"
              >
                <option value="">-- Select --</option>
                {datasets
                  .filter((d) => {
                    const q = datasetSearch.toLowerCase();
                    return !q || (d.name && d.name.toLowerCase().includes(q)) || d.source.toLowerCase().includes(q);
                  })
                  .map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name || d.source} ({d.num_rows} rows)
                  </option>
                ))}
              </select>
              <button
                onClick={() => setShowLoadDialog(!showLoadDialog)}
                className="px-4 py-2 rounded-lg border border-[var(--color-border)] bg-white text-sm text-[var(--color-text)] hover:bg-gray-50 transition-all whitespace-nowrap"
              >
                Load New
              </button>
            </div>

            {showLoadDialog && (
              <div className="mt-4 p-4 border border-[var(--color-border)] rounded-lg bg-[var(--color-surface-secondary)] animate-fade-in">
                <div className="flex gap-2 mb-3">
                  <input
                    value={loadInput}
                    onChange={(e) => setLoadInput(e.target.value)}
                    placeholder="HF dataset ID, HTTP URL, or file:// path"
                    className="flex-1 px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400"
                  />
                  <button
                    onClick={handleLoad}
                    disabled={loading || !loadInput.trim()}
                    className="px-4 py-2 rounded-lg bg-gradient-to-r from-sunset-500 to-coral-500 text-white text-sm font-medium hover:from-sunset-600 hover:to-coral-600 disabled:opacity-50 transition-all"
                  >
                    {loading ? "Loading..." : "Load"}
                  </button>
                </div>
                <div>
                  <label className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-[var(--color-border)] bg-white text-sm text-[var(--color-text)] cursor-pointer hover:bg-gray-50 transition-all">
                    <span>Upload file</span>
                    <input type="file" accept=".csv,.json,.jsonl,.parquet" onChange={handleFileUpload} className="hidden" />
                  </label>
                </div>
                {loadError && <p className="text-red-500 text-sm mt-2">{loadError}</p>}
              </div>
            )}
          </div>
        </section>

        {/* Step 2: Edit Template */}
        <section className="mb-6">
          <h3 className="text-base font-semibold text-[var(--color-text-heading)] mb-3">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-gradient-to-br from-sunset-500 to-coral-500 text-white text-xs font-bold mr-2">2</span>
            Edit Template
          </h3>
          <div className="bg-white rounded-xl border border-[var(--color-border)] p-5 shadow-sm">
            <p className="text-sm text-[var(--color-text-muted)] mb-4">
              Available variables: <code className="px-1.5 py-0.5 rounded bg-sunset-50 text-sunset-600 text-xs">data</code> (current row), <code className="px-1.5 py-0.5 rounded bg-sunset-50 text-sunset-600 text-xs">annotations</code> (saved values).
              Use any widget: <code className="px-1.5 py-0.5 rounded bg-gray-100 text-xs">SelectField</code>, <code className="px-1.5 py-0.5 rounded bg-gray-100 text-xs">TextField</code>, <code className="px-1.5 py-0.5 rounded bg-gray-100 text-xs">CheckboxGroup</code>, etc.
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
                  ) : sampleError ? (
                    <p className="text-sm text-red-500">{sampleError}</p>
                  ) : (
                    <p className="text-sm text-[var(--color-text-muted)]">Select a dataset to preview</p>
                  )}
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              <button
                onClick={saveTemplate}
                className="px-4 py-2 rounded-lg bg-gradient-to-r from-sunset-500 to-coral-500 text-white text-sm font-medium hover:from-sunset-600 hover:to-coral-600 transition-all shadow-sm"
              >
                {templateId ? "Update Template" : "Save Template"}
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

        {/* Step 3: Create Project */}
        <section className="mb-6">
          <h3 className="text-base font-semibold text-[var(--color-text-heading)] mb-3">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-gradient-to-br from-sunset-500 to-coral-500 text-white text-xs font-bold mr-2">3</span>
            Create Project
          </h3>
          <div className="bg-white rounded-xl border border-[var(--color-border)] p-5 shadow-sm">
            <div className="flex gap-4 items-start flex-wrap">
              <div className="flex-1 min-w-[200px]">
                <label className="text-xs font-medium text-[var(--color-text-muted)] block mb-1">Project name</label>
                <div className="flex items-center gap-2">
                  <input value={projectName} onChange={(e) => setProjectName(e.target.value)}
                         placeholder="My project" className="flex-1 px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400" />
                  <InstructionsButton value={projectInstructions} onChange={setProjectInstructions} />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-[var(--color-text-muted)] block mb-1">Color</label>
                <div className="flex items-center gap-2">
                  <input type="color" value={projectColor}
                         onChange={(e) => setProjectColor(e.target.value)}
                         className="w-9 h-9 p-0.5 border border-[var(--color-border)] rounded-lg cursor-pointer" />
                  <span className="text-xs text-[var(--color-text-muted)]">{projectColor}</span>
                </div>
              </div>
              <div className="flex-1 min-w-[180px]">
                <label className="text-xs font-medium text-[var(--color-text-muted)] block mb-1">Tags</label>
                <input value={projectTags} onChange={(e) => setProjectTags(e.target.value)}
                       placeholder="e.g. nlp, image, production"
                       className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400" />
              </div>
            </div>

            <hr className="my-4 border-[var(--color-border)]" />

            <div className="flex items-center gap-3">
              <label className="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" checked={mlEnabled} onChange={(e) => setMlEnabled(e.target.checked)} className="sr-only peer" />
                <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:bg-sunset-500 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all" />
              </label>
              <span className="text-sm text-[var(--color-text)]">Enable ML auto-prefill</span>
            </div>

            <button
              onClick={createProject}
              disabled={!projectName || !selectedDataset || !templateId}
              className="mt-4 px-5 py-2.5 rounded-lg bg-gradient-to-r from-sunset-500 to-coral-500 text-white font-medium text-sm hover:from-sunset-600 hover:to-coral-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm"
            >
              Create Project
            </button>
          </div>
        </section>

        {/* Step 4: ML Backend details (optional) */}
        {mlEnabled && (
        <section className="mb-6">
          <h3 className="text-base font-semibold text-[var(--color-text-heading)] mb-3">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-gradient-to-br from-sunset-500 to-coral-500 text-white text-xs font-bold mr-2">4</span>
            ML Backend <span className="text-xs text-[var(--color-text-muted)] font-normal">(optional)</span>
          </h3>
          <div className="bg-white rounded-xl border border-[var(--color-border)] p-5 shadow-sm">
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
          </div>
        </section>
        )}
      </div>
    </div>
  );
}
