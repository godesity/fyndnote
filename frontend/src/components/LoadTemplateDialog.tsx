import { PREDEFINED_TEMPLATES } from "../predefinedTemplates";
import type { PredefinedTemplate } from "../predefinedTemplates";

interface Props {
  onSelect: (tpl: PredefinedTemplate) => void;
  onClose: () => void;
}

export default function LoadTemplateDialog({ onSelect, onClose }: Props) {
  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        style={{ background: "#fff", borderRadius: 8, padding: 24, minWidth: 400, maxWidth: 500 }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 style={{ margin: "0 0 16px" }}>Load Template</h3>
        {PREDEFINED_TEMPLATES.map((tpl) => (
          <div
            key={tpl.name}
            onClick={() => { onSelect(tpl); onClose(); }}
            style={{
              padding: "12px 16px", marginBottom: 8, border: "1px solid #ddd",
              borderRadius: 6, cursor: "pointer",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.borderColor = "#888")}
            onMouseLeave={(e) => (e.currentTarget.style.borderColor = "#ddd")}
          >
            <div style={{ fontWeight: 600 }}>{tpl.name}</div>
            <div style={{ fontSize: 13, color: "#666", marginTop: 2 }}>
              {tpl.description}
            </div>
          </div>
        ))}
        <div style={{ marginTop: 12, textAlign: "right" }}>
          <button onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
