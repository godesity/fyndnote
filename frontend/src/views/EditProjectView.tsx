import { useEffect, useState, useCallback } from "react";
import { LiveProvider, LiveEditor, LivePreview, LiveError } from "react-live";
import { themes } from "prism-react-renderer";
import { api } from "../api/client";
import type { DspyConfig, DspyField, DspyTestResult, DspyTrainResult } from "../api/client";
import * as widgets from "../widgets";
import { AnnotationProvider } from "../context/AnnotationContext";
import BreadcrumbNav from "../components/BreadcrumbNav";
import LoadTemplateDialog from "../components/LoadTemplateDialog";
import DeleteProjectDialog from "../components/DeleteProjectDialog";
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
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [mlEnabled, setMlEnabled] = useState(false);
  const [mlUrl, setMlUrl] = useState("");
  const [mlAnnotator, setMlAnnotator] = useState("");
  const [mlMode, setMlMode] = useState("on_navigate");
  const [mlType, setMlType] = useState("external");
  const [dspyModel, setDspyModel] = useState("");
  const [dspyLoading, setDspyLoading] = useState(false);
  const [dspyApiBase, setDspyApiBase] = useState("");
  const [dspyCfg, setDspyCfg] = useState<DspyConfig | null>(null);
  const [dspyInstruction, setDspyInstruction] = useState("");
  const [testResult, setTestResult] = useState<DspyTestResult | null>(null);
  const [trainResult, setTrainResult] = useState<DspyTrainResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [training, setTraining] = useState(false);
  const [optimizer, setOptimizer] = useState("bootstrap");
  const [maxExamples, setMaxExamples] = useState(50);
  const [dspyError, setDspyError] = useState<string | null>(null);
  const [importText, setImportText] = useState("");
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);

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
      setMlType(project.ml_type || "external");
      setDspyModel(project.dspy_model || "");
      setDspyApiBase(project.dspy_api_base || "");
      setTemplateSource(project.template_source || "");
      setOriginalSource(project.template_source || "");
      setTemplateId(project.template_id);
      const row = await api.getRow(project.dataset_id, 0);
      setSampleRow(row.row);
      setDatasetLoaded(true);
      if ((project.ml_type || "external") === "dspy") loadDspyConfig();
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
        mlEnabled, mlUrl, mlAnnotator, mlMode, mlType, dspyModel, dspyApiBase);
      await api.updateTemplate(templateId, templateSource);
      window.location.hash = "#/projects";
    }
    setSaving(false);
  };

  const loadDspyConfig = async () => {
    setDspyLoading(true);
    setDspyError(null);
    try {
      const cfg = await api.dspyConfig(projectId);
      setDspyCfg(cfg);
      setDspyInstruction(cfg.instruction);
    } catch (e) {
      setDspyError(e instanceof Error ? e.message : "Failed to load DSPy config");
    } finally {
      setDspyLoading(false);
    }
  };

  const handleMlTypeChange = (t: string) => {
    setMlType(t);
    if (t === "dspy" && !dspyCfg) loadDspyConfig();
  };

  const patchField = (key: "input_fields" | "output_fields", idx: number, patch: Partial<DspyField>) => {
    setDspyCfg((prev) => {
      if (!prev) return prev;
      const list = prev[key].map((f, i) => (i === idx ? { ...f, ...patch } : f));
      return { ...prev, [key]: list } as DspyConfig;
    });
  };

  const handleSavePrompt = async () => {
    if (!dspyCfg) return;
    setDspyLoading(true);
    setDspyError(null);
    try {
      const cfg = await api.dspyUpdate(projectId, {
        instruction: dspyInstruction,
        input_fields: dspyCfg.input_fields,
        output_fields: dspyCfg.output_fields,
        model: dspyModel,
        api_base: dspyApiBase,
      });
      setDspyCfg(cfg);
      setDspyInstruction(cfg.instruction);
    } catch (e) {
      setDspyError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setDspyLoading(false);
    }
  };

  const handleDerive = async () => {
    if (!window.confirm("Re-derive the field schema from the current template?\nThis discards your field-level edits and tuning state.")) return;
    setDspyLoading(true);
    setDspyError(null);
    try {
      const cfg = await api.dspyDerive(projectId);
      setDspyCfg(cfg);
      setDspyInstruction(cfg.instruction);
      setTestResult(null);
      setTrainResult(null);
    } catch (e) {
      setDspyError(e instanceof Error ? e.message : "Re-derive failed");
    } finally {
      setDspyLoading(false);
    }
  };

  const handleTestRow = async () => {
    setTesting(true);
    setDspyError(null);
    setTestResult(null);
    try {
      setTestResult(await api.dspyTest(projectId, 0));
    } catch (e) {
      setDspyError(e instanceof Error ? e.message : "Test failed");
    } finally {
      setTesting(false);
    }
  };

  const handleTrain = async () => {
    setTraining(true);
    setDspyError(null);
    setTrainResult(null);
    try {
      const result = await api.dspyTrain(projectId, optimizer, maxExamples);
      setTrainResult(result);
      const cfg = await api.dspyConfig(projectId);
      setDspyCfg(cfg);
      setDspyInstruction(cfg.instruction);
    } catch (e) {
      setDspyError(e instanceof Error ? e.message : "Tuning failed");
    } finally {
      setTraining(false);
    }
  };

  const handleResetTuning = async () => {
    setDspyLoading(true);
    setDspyError(null);
    try {
      const cfg = await api.dspyReset(projectId);
      setDspyCfg(cfg);
      setDspyInstruction(cfg.instruction);
      setTrainResult(null);
    } catch (e) {
      setDspyError(e instanceof Error ? e.message : "Reset failed");
    } finally {
      setDspyLoading(false);
    }
  };

  const handleClearPredictions = async () => {
    setDspyError(null);
    try {
      await api.deleteAllMLAnnotations(projectId);
    } catch (e) {
      setDspyError(e instanceof Error ? e.message : "Clear failed");
    }
  };

  const handleSelectTemplate = (tpl: { source: string }) => {
    setTemplateSource(tpl.source);
  };

  const handleImportRows = async () => {
    setImportError(null);
    setImportResult(null);
    if (!importText.trim()) return;
    let rows: any[];
    try {
      rows = JSON.parse(importText);
    } catch {
      setImportError("Invalid JSON array");
      return;
    }
    if (!Array.isArray(rows)) {
      setImportError("Expected a JSON array of row objects");
      return;
    }
    if (!rows.every((r) => r && typeof r === "object" && !Array.isArray(r))) {
      setImportError("Each row must be a JSON object");
      return;
    }
    setImporting(true);
    try {
      await api.importRows(projectId, rows);
      setImportResult(`Imported ${rows.length} rows`);
      setImportText("");
    } catch (e: any) {
      setImportError(e.message || "Import failed");
    } finally {
      setImporting(false);
    }
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
          <div className="bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] p-5 shadow-sm flex items-center gap-4">
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
          <div className="bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] p-5 shadow-sm">
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
          <div className="bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] p-5 shadow-sm">
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
              <div className="flex-1 min-w-0 border border-[var(--color-border)] rounded-lg p-3 bg-[var(--color-surface)]">
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
                className="px-4 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm text-[var(--color-text)] hover:bg-[var(--color-surface-sunken)] transition-all"
              >
                Load Template
              </button>
            </div>
            {showTemplateDialog && (
              <LoadTemplateDialog onSelect={handleSelectTemplate} onClose={() => setShowTemplateDialog(false)} />
            )}
          </div>
        </section>

        {/* Import Rows */}
        <section className="mb-6">
          <div className="bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-[var(--color-text-heading)] mb-2">Import Rows</h3>
            <p className="text-sm text-[var(--color-text-muted)] mb-3">
              Paste a JSON array of row objects to bulk-add rows to this project's dataset.
            </p>
            <textarea
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              placeholder={`[{ "text": "hello" }, ... ]`}
              className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400 font-mono"
              rows={5}
            />
            <div className="flex items-center gap-3 mt-3">
              <button
                onClick={handleImportRows}
                disabled={importing || !importText.trim()}
                className="px-5 py-2.5 rounded-lg bg-gradient-to-r from-sunset-500 to-coral-500 text-white font-medium text-sm hover:from-sunset-600 hover:to-coral-600 disabled:opacity-50 transition-all shadow-sm"
              >
                {importing ? "Importing..." : "Import"}
              </button>
              {importResult && (
                <span className="text-sm text-green-600">{importResult}</span>
              )}
              {importError && (
                <span className="text-sm text-red-500">{importError}</span>
              )}
            </div>
          </div>
        </section>

        {/* ML Backend */}
        <section className="mb-6">
          <div className="bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-[var(--color-text-heading)] mb-2">ML Backend</h3>
            <div className="flex items-center gap-3 mb-4">
              <label className="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" checked={mlEnabled} onChange={(e) => setMlEnabled(e.target.checked)} className="sr-only peer" />
                <div className="w-9 h-5 bg-[var(--color-surface-sunken)] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:bg-sunset-500 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all" />
              </label>
              <span className="text-sm text-[var(--color-text)]">Enable ML auto-prefill</span>
            </div>
            <div className="mb-4">
              <label className="text-xs font-medium text-[var(--color-text-muted)] block mb-1">Backend Type</label>
              <div className="flex gap-4">
                {[
                  { value: "external", label: "External API" },
                  { value: "dspy", label: "DSPy LLM" },
                ].map((opt) => (
                  <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" name="ml-type" value={opt.value}
                           checked={mlType === opt.value}
                           onChange={() => handleMlTypeChange(opt.value)}
                           className="text-sunset-500 focus:ring-sunset-400" />
                    <span className="text-sm text-[var(--color-text)]">{opt.label}</span>
                  </label>
                ))}
              </div>
            </div>
            {mlType === "external" ? (
              mlEnabled && (
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
                  <MlModePicker value={mlMode} onChange={setMlMode} />
                </div>
              )
            ) : (
              <div className="space-y-3">
                <div>
                  <label className="text-xs font-medium text-[var(--color-text-muted)] block mb-1">Model</label>
                  <input value={dspyModel} onChange={(e) => setDspyModel(e.target.value)}
                         placeholder="openai/gpt-4o-mini"
                         className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400" />
                </div>
                <div>
                  <label className="text-xs font-medium text-[var(--color-text-muted)] block mb-1">API Base (OpenAI-compatible)</label>
                  <input value={dspyApiBase} onChange={(e) => setDspyApiBase(e.target.value)}
                         placeholder="http://localhost:8082/v1"
                         className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400" />
                </div>
                {mlEnabled && (
                  <>
                    <div>
                      <label className="text-xs font-medium text-[var(--color-text-muted)] block mb-1">Annotator Name</label>
                      <input value={mlAnnotator} onChange={(e) => setMlAnnotator(e.target.value)}
                             placeholder="e.g. dspy-mock, my-model-v1"
                             className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400" />
                    </div>
                    <MlModePicker value={mlMode} onChange={setMlMode} />
                  </>
                )}
              </div>
            )}

            {/* Prompt Studio */}
            {mlType === "dspy" && (
              <div className="mt-5 pt-5 border-t border-[var(--color-border)]">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-semibold text-[var(--color-text-heading)]">Prompt Studio</h4>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${dspyCfg?.tuned_at ? "bg-green-100 text-green-700" : "bg-[var(--color-surface-sunken)] text-[var(--color-text-muted)]"}`}>
                    {dspyCfg?.tuned_at ? `Tuned ${dspyCfg.tuned_at.slice(0, 19).replace("T", " ")}` : "not tuned"}
                  </span>
                </div>
                {dspyLoading && !dspyCfg && (
                  <p className="text-sm text-[var(--color-text-muted)]">Loading prompt config...</p>
                )}
                {dspyCfg && (
                  <div className="space-y-4">
                    <div>
                      <label className="text-xs font-medium text-[var(--color-text-muted)] block mb-1">Instruction (fully transparent — this is what runs)</label>
                      <textarea value={dspyInstruction} onChange={(e) => setDspyInstruction(e.target.value)}
                                rows={3}
                                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400 font-mono" />
                    </div>
                    <div>
                      <p className="text-xs font-medium text-[var(--color-text-muted)] mb-2">Input fields</p>
                      {dspyCfg.input_fields.length === 0 && (
                        <p className="text-xs text-[var(--color-text-muted)]">No input columns referenced by the template.</p>
                      )}
                      {dspyCfg.input_fields.map((f, i) => (
                        <div key={f.source} className="flex items-center gap-2 mb-2">
                          <span className="text-xs font-mono w-32 shrink-0 text-[var(--color-text)]">{f.name}</span>
                          <input value={f.desc} placeholder="field description"
                                 onChange={(e) => patchField("input_fields", i, { desc: e.target.value })}
                                 className="flex-1 px-3 py-1.5 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400" />
                        </div>
                      ))}
                    </div>
                    <div>
                      <p className="text-xs font-medium text-[var(--color-text-muted)] mb-2">Output fields (annotation schema)</p>
                      {dspyCfg.output_fields.map((f, i) => (
                        <div key={f.source} className="flex items-center gap-2 mb-2">
                          <span className="text-xs font-mono w-28 shrink-0 text-[var(--color-text)]">{f.name}</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-surface-sunken)] text-[var(--color-text-muted)] shrink-0">
                            {f.kind}{f.options && f.options.length > 0 ? `: ${f.options.join("/")}` : ""}{f.max ? ` (1-${f.max})` : ""}
                          </span>
                          {f.kind === "unsupported" ? (
                            <span className="text-xs text-[var(--color-text-muted)] flex-1">(unsupported — spatial widgets cannot be predicted)</span>
                          ) : (
                            <input value={f.desc} placeholder="field description"
                                   onChange={(e) => patchField("output_fields", i, { desc: e.target.value })}
                                   className="flex-1 px-3 py-1.5 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400" />
                          )}
                          <label className="flex items-center gap-1 shrink-0">
                            <input type="checkbox" checked={!!f.enabled} disabled={f.kind === "unsupported"}
                                   onChange={(e) => patchField("output_fields", i, { enabled: e.target.checked })} />
                            <span className="text-xs text-[var(--color-text-muted)]">on</span>
                          </label>
                        </div>
                      ))}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <button onClick={handleSavePrompt} disabled={dspyLoading}
                              className="px-4 py-2 rounded-lg bg-gradient-to-r from-sunset-500 to-coral-500 text-white font-medium text-sm hover:from-sunset-600 hover:to-coral-600 disabled:opacity-50 transition-all shadow-sm">
                        Save Prompt
                      </button>
                      <button onClick={handleDerive} disabled={dspyLoading}
                              className="px-4 py-2 rounded-lg border border-[var(--color-border)] text-sm text-[var(--color-text)] hover:bg-[var(--color-surface-sunken)] disabled:opacity-50 transition-all">
                        Re-derive from template
                      </button>
                      <button onClick={handleTestRow} disabled={testing || dspyLoading}
                              className="px-4 py-2 rounded-lg border border-[var(--color-border)] text-sm text-[var(--color-text)] hover:bg-[var(--color-surface-sunken)] disabled:opacity-50 transition-all">
                        {testing ? "Testing..." : "Test row 0"}
                      </button>
                      <select value={optimizer} onChange={(e) => setOptimizer(e.target.value)}
                              className="px-2 py-2 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400">
                        <option value="bootstrap">bootstrap</option>
                        <option value="mipro">mipro</option>
                      </select>
                      <input type="number" min={3} value={maxExamples}
                             onChange={(e) => setMaxExamples(parseInt(e.target.value || "50", 10))}
                             className="w-20 px-2 py-2 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400" />
                      <button onClick={handleTrain} disabled={training || dspyLoading}
                              className="px-4 py-2 rounded-lg bg-sky-600 text-white font-medium text-sm hover:bg-sky-700 disabled:opacity-50 transition-all shadow-sm">
                        {training ? "Tuning..." : "Tune"}
                      </button>
                      <button onClick={handleResetTuning} disabled={dspyLoading}
                              className="px-4 py-2 rounded-lg border border-[var(--color-border)] text-sm text-[var(--color-text)] hover:bg-[var(--color-surface-sunken)] disabled:opacity-50 transition-all">
                        Reset tuning
                      </button>
                      <button onClick={handleClearPredictions}
                              className="px-4 py-2 rounded-lg border border-red-300 text-sm text-red-600 hover:bg-red-50 transition-all">
                        Clear predictions
                      </button>
                    </div>
                    {trainResult && (
                      <div className="text-xs text-[var(--color-text)] bg-[var(--color-surface-sunken)] rounded-lg p-3">
                        score <b>{trainResult.score.toFixed(3)}</b> · demos <b>{trainResult.n_demos}</b> ·
                        train/val <b>{trainResult.train_size}/{trainResult.val_size}</b> · {trainResult.optimizer}
                      </div>
                    )}
                    {testResult && (
                      <div className="text-xs text-[var(--color-text)] bg-[var(--color-surface-sunken)] rounded-lg p-3 space-y-1">
                        <p className="font-semibold">Test prediction (row 0)</p>
                        {testResult.fields.map((f) => (
                          <p key={f.name}>
                            <span className="font-mono">{f.name}</span> ={" "}
                            <span className="font-mono">{typeof f.value === "string" ? f.value : JSON.stringify(f.value)}</span>
                          </p>
                        ))}
                        <p className="font-mono text-[var(--color-text-muted)] break-all">{JSON.stringify(testResult.annotation)}</p>
                      </div>
                    )}
                    {dspyError && <p className="text-sm text-red-500">{dspyError}</p>}
                    {dspyCfg && !dspyCfg.llm_key_set && (
                      <p className="text-xs text-amber-600">
                        FYNDNOTE_LLM_API_KEY is not set on the server — Test/Tune will fail until it is configured.
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </section>

        {datasetLoaded && (
          <section className="mb-6">
            {/* Danger Zone */}
            <div className="bg-[var(--color-surface)] rounded-xl border-2 border-red-300 p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-red-600 mb-1">Danger Zone</h3>
              <p className="text-sm text-[var(--color-text-muted)] mb-4">
                Deletes the project and all its annotations permanently. The dataset and
                templates stay available for other or new projects.
              </p>
              <button
                onClick={() => setShowDeleteDialog(true)}
                className="px-5 py-2.5 rounded-lg bg-red-500 text-white font-medium text-sm hover:bg-red-600 transition-all shadow-sm"
              >
                Delete Project
              </button>
            </div>
          </section>
        )}

        {showDeleteDialog && (
          <DeleteProjectDialog
            projectName={projectName}
            projectId={projectId}
            onClose={() => setShowDeleteDialog(false)}
          />
        )}
      </div>
    </div>
  );
}

function MlModePicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
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
                   checked={value === opt.value}
                   onChange={() => onChange(opt.value)}
                   className="text-sunset-500 focus:ring-sunset-400" />
            <span className="text-sm text-[var(--color-text)]">{opt.label}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
