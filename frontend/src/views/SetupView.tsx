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

export default function SetupView({ onDone }: { onDone: () => void }) {
  const [datasets, setDatasets] = useState<any[]>([]);
  const [selectedDataset, setSelectedDataset] = useState("");
  const [templateSource, setTemplateSource] = useState(DEFAULT_TEMPLATE);
  const [templateId, setTemplateId] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("");
  const [sampleRow, setSampleRow] = useState<any>(null);
  const [validated, setValidated] = useState(false);

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
    onDone();
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
        <button
          onClick={() => {
            /* open load dialog */
          }}
          style={{ marginLeft: 8 }}
        >
          Load New
        </button>
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
