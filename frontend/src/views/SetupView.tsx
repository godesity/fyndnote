import { useEffect, useState, useCallback } from "react";
import { LiveProvider, LiveEditor, LivePreview, LiveError } from "react-live";
import { api } from "../api/client";
import * as widgets from "../widgets";
import { AnnotationProvider } from "../context/AnnotationContext";

const scope = { ...widgets, useState, useCallback };

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
  const [sampleRow, setSampleRow] = useState<any>(null);
  const [validated, setValidated] = useState(false);
  const [loadInput, setLoadInput] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showLoadDialog, setShowLoadDialog] = useState(false);

  useEffect(() => {
    api.listDatasets().then((res) => setDatasets(res.datasets));
  }, []);

  const loadSample = async (dsId: string) => {
    setSelectedDataset(dsId);
    const row = await api.getRow(dsId, 0);
    setSampleRow(row.row);
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
    await api.createProject(projectName, selectedDataset, templateId);
    window.location.hash = '#/projects';
  };

  const handleLoad = async () => {
    if (!loadInput.trim()) return;
    setLoading(true);
    setLoadError(null);
    try {
      await api.loadDataset(loadInput.trim());
      setLoadInput("");
      setShowLoadDialog(false);
      const res = await api.listDatasets();
      setDatasets(res.datasets);
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
      await api.uploadDataset(file);
      const res = await api.listDatasets();
      setDatasets(res.datasets);
    } catch (err: any) {
      setLoadError(err.message || "Failed to upload dataset");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 20 }}>
      <h2>Setup Project</h2>

      <div style={{ marginBottom: 20 }}>
        <h3>1. Select Dataset</h3>
        <select
          value={selectedDataset}
          onChange={(e) => loadSample(e.target.value)}
          style={{ width: "100%", padding: 8 }}
        >
          <option value="">-- Select --</option>
          {datasets.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name || d.source} ({d.num_rows} rows)
            </option>
          ))}
        </select>
        <button onClick={() => setShowLoadDialog(!showLoadDialog)} style={{ marginLeft: 8 }}>
          Load New
        </button>

        {showLoadDialog && (
          <div style={{ marginTop: 8, padding: 12, border: '1px solid #ccc', borderRadius: 4 }}>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <input
                value={loadInput}
                onChange={(e) => setLoadInput(e.target.value)}
                placeholder="HF dataset ID, HTTP URL, or file:// path"
                style={{ flex: 1, padding: 8 }}
              />
              <button onClick={handleLoad} disabled={loading || !loadInput.trim()}>
                {loading ? "Loading..." : "Load"}
              </button>
            </div>
            <div>
              <input type="file" accept=".csv,.json,.jsonl,.parquet" onChange={handleFileUpload} />
            </div>
            {loadError && <p style={{ color: 'red', fontSize: 13, marginTop: 4 }}>{loadError}</p>}
          </div>
        )}
      </div>

      <div style={{ marginBottom: 20 }}>
        <h3>2. Edit Template</h3>
        <p style={{ fontSize: 13, color: "#666", marginBottom: 8 }}>
          Available variables: <code>data</code> (current row), <code>annotations</code> (saved values).
          Use any widget component: <code>SelectField</code>, <code>TextField</code>, <code>CheckboxGroup</code>, <code>RatingField</code>, <code>NERField</code>, <code>BBoxField</code>.
        </p>
        <div style={{ display: "flex", gap: 16 }}>
          <div style={{ flex: 1 }}>
            <AnnotationProvider>
              <LiveProvider code={templateSource} scope={{ ...scope, data: sampleRow || {}, annotations: {} }}>
                <LiveEditor onChange={setTemplateSource} />
                <LiveError />
              </LiveProvider>
            </AnnotationProvider>
          </div>
          <div
            style={{
              flex: 1,
              border: "1px solid #ccc",
              padding: 8,
              minHeight: 200,
            }}
          >
            <h4>Preview</h4>
            {sampleRow ? (
              <AnnotationProvider>
                <LiveProvider
                  code={templateSource}
                  scope={{ ...scope, data: sampleRow, annotations: {} }}
                >
                  <LivePreview />
                </LiveProvider>
              </AnnotationProvider>
            ) : (
              <p>Select a dataset to preview</p>
            )}
          </div>
        </div>
        <button onClick={saveTemplate} style={{ marginTop: 8 }}>
          {templateId ? "Update Template" : "Save Template"}
        </button>
      </div>

      <div>
        <h3>3. Create Project</h3>
        <input
          value={projectName}
          onChange={(e) => setProjectName(e.target.value)}
          placeholder="Project name"
          style={{ padding: 8, width: 300 }}
        />
        <button
          onClick={createProject}
          disabled={!projectName || !selectedDataset || !templateId}
          style={{ marginLeft: 8, padding: "8px 16px" }}
        >
          Create Project
        </button>
      </div>
    </div>
  );
}
