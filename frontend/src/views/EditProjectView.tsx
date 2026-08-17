import { useEffect, useState, useCallback } from "react";
import { LiveProvider, LiveEditor, LivePreview, LiveError } from "react-live";
import { api } from "../api/client";
import * as widgets from "../widgets";
import { AnnotationProvider } from "../context/AnnotationContext";
import LoadTemplateDialog from "../components/LoadTemplateDialog";

const scope = { ...widgets, useState, useCallback };

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
  const [projectColor, setProjectColor] = useState("#1976d2");
  const [projectTags, setProjectTags] = useState("");
  const [sampleRow, setSampleRow] = useState<any>(null);
  const [datasetLoaded, setDatasetLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showTemplateDialog, setShowTemplateDialog] = useState(false);

  useEffect(() => {
    const load = async () => {
      const user = JSON.parse(sessionStorage.getItem("auth_user") || "{}");
      const project = await api.getProject(projectId, user.user_id);
      setProjectName(project.name);
      setProjectColor(project.color || "#1976d2");
      setProjectTags(project.tags || "");
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
      await api.updateProject(projectId, projectName, projectColor, projectTags);
      await api.updateTemplate(templateId, templateSource);
      window.location.hash = "#/projects";
    }
    setSaving(false);
  };

  const handleSelectTemplate = (tpl: { source: string }) => {
    setTemplateSource(tpl.source);
  };

  return (
    <div style={{ padding: 20 }}>
      <div style={{ height: 3, background: projectColor, marginBottom: 8, borderRadius: 2 }} />
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h2>Settings: {projectName}</h2>
        <button onClick={() => (window.location.hash = "#/projects")}>
          Back
        </button>
      </div>

      <div style={{ marginBottom: 20 }}>
        <h3>Project Name</h3>
        <input
          value={projectName}
          onChange={(e) => setProjectName(e.target.value)}
          style={{ padding: 8, width: 300 }}
        />
      </div>

      <div style={{ marginBottom: 20, display: 'flex', gap: 24 }}>
        <div>
          <h3>Color</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="color" value={projectColor}
                   onChange={(e) => setProjectColor(e.target.value)}
                   style={{ width: 40, height: 32, padding: 0, border: 'none', cursor: 'pointer' }} />
            <span style={{ fontSize: 13, color: '#666' }}>{projectColor}</span>
          </div>
        </div>
        <div style={{ flex: 1 }}>
          <h3>Tags</h3>
          <input value={projectTags} placeholder="e.g. image, nlp, production"
                 onChange={(e) => setProjectTags(e.target.value)}
                 style={{ padding: 8, width: '100%', boxSizing: 'border-box' }} />
          <p style={{ fontSize: 11, color: '#999', margin: '2px 0 0' }}>Comma-separated</p>
        </div>
      </div>

      <div style={{ marginBottom: 20 }}>
        <h3>Template</h3>
        <p style={{ fontSize: 13, color: "#666", marginBottom: 8 }}>
          Available variables: <code>data</code> (current row),{" "}
          <code>annotations</code> (saved values).
        </p>
        <div style={{ display: "flex", gap: 16 }}>
          <div style={{ flex: 1 }}>
            <AnnotationProvider>
              <LiveProvider
                code={templateSource}
                scope={{ ...scope, data: sampleRow || {}, annotations: {} }}
              >
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
              <p>Loading sample row...</p>
            )}
          </div>
        </div>
        <button
          onClick={handleSave}
          disabled={saving || !datasetLoaded}
          style={{ marginTop: 8 }}
        >
          {saving ? "Saving..." : "Save"}
        </button>
        <button onClick={() => setShowTemplateDialog(true)} style={{ marginTop: 8, marginLeft: 8 }}>
          Load Template
        </button>
        {showTemplateDialog && (
          <LoadTemplateDialog onSelect={handleSelectTemplate} onClose={() => setShowTemplateDialog(false)} />
        )}
      </div>
    </div>
  );
}
