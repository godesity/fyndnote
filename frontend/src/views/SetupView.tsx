import { useEffect, useState } from 'react';
import { LiveProvider, LiveEditor, LivePreview, LiveError } from 'react-live';
import { api } from '../api/client';
import * as widgets from '../widgets';

const scope = { ...widgets, useState, useCallback };

const DEFAULT_TEMPLATE = `function TextClassification({ row, annotations }) {
  return (
    <div style={{ padding: 20 }}>
      <h3>Classify the sentiment</h3>
      <p style={{ fontSize: 18 }}>{row.text}</p>
      <SelectField
        name="sentiment"
        labels={["positive", "negative", "neutral"]}
        defaultValue={annotations?.sentiment}
      />
    </div>
  );
}`;

export default function SetupView({ onDone }: { onDone: () => void }) {
  const [datasets, setDatasets] = useState<any[]>([]);
  const [selectedDataset, setSelectedDataset] = useState('');
  const [templateSource, setTemplateSource] = useState(DEFAULT_TEMPLATE);
  const [templateId, setTemplateId] = useState<string | null>(null);
  const [projectName, setProjectName] = useState('');
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
      const t = await api.createTemplate('custom', templateSource);
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
        <select value={selectedDataset} onChange={(e) => loadSample(e.target.value)} style={{ width: '100%', padding: 8 }}>
          <option value="">-- Select --</option>
          {datasets.map((d) => (
            <option key={d.id} value={d.id}>{d.name} ({d.num_rows} rows)</option>
          ))}
        </select>
        <button onClick={() => {/* open load dialog */}} style={{ marginLeft: 8 }}>Load New</button>
      </div>

      <div style={{ marginBottom: 20 }}>
        <h3>2. Edit Template</h3>
        <div style={{ display: 'flex', gap: 16 }}>
          <div style={{ flex: 1 }}>
            <LiveProvider code={templateSource} scope={scope}>
              <LiveEditor onChange={setTemplateSource} />
              <LiveError />
            </LiveProvider>
          </div>
          <div style={{ flex: 1, border: '1px solid #ccc', padding: 8, minHeight: 200 }}>
            <h4>Preview</h4>
            {sampleRow ? (
              <LiveProvider code={templateSource} scope={scope} noInline={false}
                {...{ row: sampleRow, annotations: {} } as any}>
                <LivePreview />
              </LiveProvider>
            ) : <p>Select a dataset to preview</p>}
          </div>
        </div>
        <button onClick={saveTemplate} style={{ marginTop: 8 }}>
          {templateId ? 'Update Template' : 'Save Template'}
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
        <button onClick={createProject} disabled={!projectName || !selectedDataset || !templateId}
                style={{ marginLeft: 8, padding: '8px 16px' }}>
          Create Project
        </button>
      </div>
    </div>
  );
}
