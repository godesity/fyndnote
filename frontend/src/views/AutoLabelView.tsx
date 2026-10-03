import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { DspyConfig, DspyField, DspyTestResult, DspyTrainResult, DspyVersion } from "../api/client";
import BreadcrumbNav from "../components/BreadcrumbNav";

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

export default function AutoLabelView({ projectId }: { projectId: string }) {
  const [projectName, setProjectName] = useState("");
  const [projectColor, setProjectColor] = useState("#F97316");
  const [mlEnabled, setMlEnabled] = useState(false);
  const [mlUrl, setMlUrl] = useState("");
  const [mlAnnotator, setMlAnnotator] = useState("");
  const [mlMode, setMlMode] = useState("on_navigate");
  const [mlType, setMlType] = useState("external");
  const [dspyModel, setDspyModel] = useState("");
  const [dspyApiBase, setDspyApiBase] = useState("");
  const [dspyLoading, setDspyLoading] = useState(false);
  const [dspyCfg, setDspyCfg] = useState<DspyConfig | null>(null);
  const [dspyInstruction, setDspyInstruction] = useState("");
  const [testResult, setTestResult] = useState<DspyTestResult | null>(null);
  const [trainResult, setTrainResult] = useState<DspyTrainResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [training, setTraining] = useState(false);
  const [optimizer, setOptimizer] = useState("bootstrap");
  const [maxExamples, setMaxExamples] = useState(50);
  const [dspyError, setDspyError] = useState<string | null>(null);
  const [dspyVersions, setDspyVersions] = useState<DspyVersion[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);

  useEffect(() => {
    const load = async () => {
      const user = JSON.parse(sessionStorage.getItem("auth_user") || "{}");
      const project = await api.getProject(projectId, user.user_id);
      setProjectName(project.name);
      setProjectColor(project.color || "#F97316");
      setMlEnabled(!!project.ml_enabled);
      setMlUrl(project.ml_url || "");
      setMlAnnotator(project.ml_annotator || "");
      setMlMode(project.ml_mode || "on_navigate");
      setMlType(project.ml_type || "external");
      setDspyModel(project.dspy_model || "");
      setDspyApiBase(project.dspy_api_base || "");
      if ((project.ml_type || "external") === "dspy") loadDspyConfig();
    };
    load();
  }, [projectId]);

  const loadDspyConfig = async () => {
    setDspyLoading(true);
    setDspyError(null);
    try {
      const cfg = await api.dspyConfig(projectId);
      setDspyCfg(cfg);
      setDspyInstruction(cfg.instruction);
      const hist = await api.dspyVersions(projectId).catch(() => null);
      if (hist) setDspyVersions(hist.versions);
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

  const handleSave = async () => {
    setSaving(true);
    setDspyError(null);
    try {
      // Name-only update: leave color/tags/instructions untouched so this page
      // never clobbers fields owned by the Settings view.
      await api.updateProject(projectId, projectName,
        undefined, undefined, undefined,
        mlEnabled, mlUrl, mlAnnotator, mlMode, mlType, dspyModel, dspyApiBase);
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2000);
    } catch (e) {
      setDspyError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
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
      api.dspyVersions(projectId).then((h) => setDspyVersions(h.versions)).catch(() => {});
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
      setTrainResult(null);
      api.dspyVersions(projectId).then((h) => setDspyVersions(h.versions)).catch(() => {});
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
      api.dspyVersions(projectId).then((h) => setDspyVersions(h.versions)).catch(() => {});
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
      const [cfg, hist] = await Promise.all([
        api.dspyReset(projectId),
        api.dspyVersions(projectId),
      ]);
      setDspyCfg(cfg);
      setDspyInstruction(cfg.instruction);
      setDspyVersions(hist.versions);
      setTrainResult(null);
    } catch (e) {
      setDspyError(e instanceof Error ? e.message : "Reset failed");
    } finally {
      setDspyLoading(false);
    }
  };

  const handleAcceptPending = async () => {
    setDspyLoading(true);
    setDspyError(null);
    try {
      const cfg = await api.dspyAccept(projectId);
      setDspyCfg(cfg);
      setDspyInstruction(cfg.instruction);
      setTrainResult(null);
      // read versions AFTER the promotion commits, or the list is stale
      const hist = await api.dspyVersions(projectId);
      setDspyVersions(hist.versions);
    } catch (e) {
      setDspyError(e instanceof Error ? e.message : "Accept failed");
    } finally {
      setDspyLoading(false);
    }
  };

  const handleRejectPending = async () => {
    setDspyLoading(true);
    setDspyError(null);
    try {
      const [cfg, hist] = await Promise.all([
        api.dspyReject(projectId),
        api.dspyVersions(projectId),
      ]);
      setDspyCfg(cfg);
      setDspyInstruction(cfg.instruction);
      setDspyVersions(hist.versions);
      setTrainResult(null);
    } catch (e) {
      setDspyError(e instanceof Error ? e.message : "Reject failed");
    } finally {
      setDspyLoading(false);
    }
  };

  const handleRevert = async (version: number) => {
    if (!window.confirm(`Switch predictions back to prompt v${version}?\nThe current active prompt stays in history.`)) return;
    setDspyLoading(true);
    setDspyError(null);
    try {
      const [cfg, hist] = await Promise.all([
        api.dspyRevert(projectId, version),
        api.dspyVersions(projectId),
      ]);
      setDspyCfg(cfg);
      setDspyInstruction(cfg.instruction);
      setDspyVersions(hist.versions);
    } catch (e) {
      setDspyError(e instanceof Error ? e.message : "Revert failed");
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

  return (
    <div className="min-h-screen bg-[var(--color-surface-secondary)]">
      <BreadcrumbNav crumbs={[
        { label: 'Projects', href: '#/projects' },
        { label: projectName || 'Settings', href: `#/projects/${projectId}/edit` },
        { label: 'Auto-Label' },
      ]} />

      <div className="h-1" style={{ background: projectColor }} />

      <div className="max-w-5xl mx-auto px-6 py-6 animate-fade-in">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-[var(--color-text-heading)]">Auto-Label: {projectName}</h2>
          <a href={`#/projects/${projectId}/edit`}
             className="px-4 py-2 rounded-lg border border-[var(--color-border)] text-sm text-[var(--color-text)] hover:bg-[var(--color-surface-sunken)] transition-all">
            Template Settings
          </a>
        </div>

        <section className="mb-6">
          <div className="bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] p-5 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-[var(--color-text-heading)]">ML Backend</h3>
              {savedFlash && <span className="text-sm text-green-600">Saved</span>}
            </div>
            <div className="flex items-center gap-3 mb-4">
              <label className="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" checked={mlEnabled} onChange={(e) => setMlEnabled(e.target.checked)} className="sr-only peer" />
                <div className="w-9 h-5 bg-[var(--color-surface-sunken)] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:bg-sunset-500 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all" />
              </label>
              <span className="text-sm text-[var(--color-text)]">Enable ML auto-prefill</span>
              <button
                onClick={handleSave}
                disabled={saving}
                className="ml-auto px-5 py-2.5 rounded-lg bg-gradient-to-r from-sunset-500 to-coral-500 text-white font-medium text-sm hover:from-sunset-600 hover:to-coral-600 disabled:opacity-50 transition-all shadow-sm">
                {saving ? "Saving..." : "Save"}
              </button>
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
          </div>
        </section>

        {mlType === "dspy" && (
          <section className="mb-6">
            <div className="bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] p-5 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-[var(--color-text-heading)]">Prompt Studio</h3>
                <div className="flex items-center gap-2">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--color-surface-sunken)] text-[var(--color-text-muted)]">
                    v{dspyCfg?.active_version ?? "-"} · {dspyCfg?.kind ?? "derived"}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${dspyCfg?.pending ? "bg-amber-100 text-amber-700" : dspyCfg?.tuned_at ? "bg-green-100 text-green-700" : "bg-[var(--color-surface-sunken)] text-[var(--color-text-muted)]"}`}>
                    {dspyCfg?.pending ? "tune awaiting review" : dspyCfg?.tuned_at ? `Tuned ${dspyCfg.tuned_at.slice(0, 19).replace("T", " ")}` : "not tuned"}
                  </span>
                </div>
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
                  {dspyCfg.pending && (
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-2">
                      <p className="text-xs text-amber-800">
                        A tuned candidate is ready ({dspyCfg.pending.optimizer}, score{" "}
                        <b>{dspyCfg.pending.score == null ? "?" : dspyCfg.pending.score.toFixed(3)}</b>,{" "}
                        {dspyCfg.pending.n_demos} demos) and is <b>not</b> used by predictions yet.
                      </p>
                      <p className="text-xs font-mono text-amber-900 break-words line-clamp-3">{dspyCfg.pending.instruction}</p>
                      <div className="flex gap-2">
                        <button onClick={handleAcceptPending} disabled={dspyLoading}
                                className="px-3 py-1.5 rounded-lg bg-green-600 text-white text-xs font-medium hover:bg-green-700 disabled:opacity-50 transition-all">
                          Accept &amp; make live
                        </button>
                        <button onClick={handleRejectPending} disabled={dspyLoading}
                                className="px-3 py-1.5 rounded-lg border border-amber-300 text-amber-800 text-xs hover:bg-amber-100 disabled:opacity-50 transition-all">
                          Discard
                        </button>
                      </div>
                    </div>
                  )}
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
                      {training ? "Tuning..." : "Tune (candidate)"}
                    </button>
                    <button onClick={() => setShowHistory((v) => !v)} disabled={dspyLoading}
                            className="px-4 py-2 rounded-lg border border-[var(--color-border)] text-sm text-[var(--color-text)] hover:bg-[var(--color-surface-sunken)] disabled:opacity-50 transition-all">
                      {showHistory ? "Hide history" : `History (${dspyVersions.length})`}
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
                  {showHistory && (
                    <div className="border border-[var(--color-border)] rounded-lg divide-y divide-[var(--color-border)]">
                      {dspyVersions.length === 0 && (
                        <p className="text-xs text-[var(--color-text-muted)] p-3">No versions recorded yet.</p>
                      )}
                      {dspyVersions.map((v) => (
                        <div key={v.version} className="flex items-start gap-2 p-3">
                          <span className="text-xs font-mono w-10 shrink-0">v{v.version}</span>
                          <div className="flex-1 min-w-0">
                            <p className="text-xs text-[var(--color-text-muted)]">
                              {v.kind}
                              {v.optimizer ? ` · ${v.optimizer}` : ""}
                              {v.score != null ? ` · score ${v.score.toFixed(3)}` : ""}
                              {v.n_demos ? ` · ${v.n_demos} demos` : ""}
                              {v.source_version ? ` · from v${v.source_version}` : ""}
                              {" · "}{v.created_at?.slice(0, 16).replace("T", " ")}
                              {v.label ? ` · ${v.label}` : ""}
                            </p>
                            <p className="text-xs font-mono text-[var(--color-text)] break-words line-clamp-2">{v.instruction}</p>
                          </div>
                          {v.version !== dspyCfg.active_version && (
                            <button onClick={() => handleRevert(v.version)} disabled={dspyLoading}
                                    className="px-3 py-1.5 rounded-lg border border-[var(--color-border)] text-xs text-[var(--color-text)] hover:bg-[var(--color-surface-sunken)] shrink-0 transition-all">
                              Use this
                            </button>
                          )}
                          {v.version === dspyCfg.active_version && (
                            <span className="text-[10px] px-2 py-1 rounded-full bg-green-100 text-green-700 shrink-0">live</span>
                          )}
                        </div>
                      ))}
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
                  {trainResult && (
                    <div className="text-xs text-[var(--color-text)] bg-[var(--color-surface-sunken)] rounded-lg p-3">
                      Tuned candidate created ({trainResult.optimizer}) — review it above, then Accept to make it live. Nothing changed yet.
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
          </section>
        )}
      </div>
    </div>
  );
}
