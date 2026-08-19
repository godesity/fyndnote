import { useState } from "react";
import { LiveProvider, LivePreview, LiveError } from "react-live";
import { themes } from "prism-react-renderer";
import { PREDEFINED_TEMPLATES } from "../predefinedTemplates";
import type { PredefinedTemplate } from "../predefinedTemplates";
import * as widgets from "../widgets";
import { AnnotationProvider } from "../context/AnnotationContext";

const ALL_GROUPS = ["All", "text", "image", "audio"] as const;
type GroupFilter = (typeof ALL_GROUPS)[number];

const scope = { ...widgets, useState };

interface Props {
  onSelect: (tpl: PredefinedTemplate) => void;
  onClose: () => void;
}

export default function LoadTemplateDialog({ onSelect, onClose }: Props) {
  const [groupFilter, setGroupFilter] = useState<GroupFilter>("All");
  const [selected, setSelected] = useState<PredefinedTemplate | null>(null);

  const filtered = groupFilter === "All"
    ? PREDEFINED_TEMPLATES
    : PREDEFINED_TEMPLATES.filter((t) => t.group === groupFilter);

  const grouped = groupFilter === "All"
    ? (["text", "image", "audio"] as const).map((g) => ({
        group: g,
        templates: PREDEFINED_TEMPLATES.filter((t) => t.group === g),
      }))
    : [];

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "#fff", borderRadius: 8, padding: 24,
          minWidth: 700, maxWidth: 900, width: "85vw",
          maxHeight: "85vh", display: "flex", flexDirection: "column",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 style={{ margin: "0 0 16px" }}>Load Template</h3>

        {/* Filter pills */}
        <div style={{ display: "flex", gap: 6, marginBottom: 16 }}>
          {ALL_GROUPS.map((g) => (
            <button
              key={g}
              onClick={() => { setGroupFilter(g); setSelected(null); }}
              style={{
                padding: "4px 14px",
                borderRadius: 20,
                border: "none",
                fontSize: 13,
                fontWeight: groupFilter === g ? 600 : 400,
                background: groupFilter === g ? "#F97316" : "#f3f4f6",
                color: groupFilter === g ? "#fff" : "#374151",
                cursor: "pointer",
              }}
            >
              {g === "All" ? "All" : g.charAt(0).toUpperCase() + g.slice(1)}
            </button>
          ))}
        </div>

        {/* Two-column layout: list | preview */}
        <div style={{ display: "flex", gap: 16, flex: 1, minHeight: 0 }}>
          {/* Left: template list */}
          <div style={{ flex: "0 0 280px", overflowY: "auto" }}>
            {groupFilter === "All"
              ? grouped.map(({ group, templates }) =>
                  templates.length > 0 ? (
                    <div key={group} style={{ marginBottom: 12 }}>
                      <div style={{
                        fontSize: 11, fontWeight: 600, color: "#9ca3af",
                        textTransform: "uppercase", letterSpacing: 1,
                        marginBottom: 6, paddingLeft: 4,
                      }}>
                        {group.charAt(0).toUpperCase() + group.slice(1)}
                      </div>
                      {templates.map((tpl) => (
                        <TemplateCard
                          key={tpl.name}
                          template={tpl}
                          isSelected={selected?.name === tpl.name}
                          onClick={() => setSelected(tpl)}
                        />
                      ))}
                    </div>
                  ) : null
                )
              : filtered.map((tpl) => (
                  <TemplateCard
                    key={tpl.name}
                    template={tpl}
                    isSelected={selected?.name === tpl.name}
                    onClick={() => setSelected(tpl)}
                  />
                ))}
          </div>

          {/* Right: preview panel */}
          <div style={{
            flex: 1, borderLeft: "1px solid #eee", paddingLeft: 16,
            display: "flex", flexDirection: "column",
          }}>
            <div style={{
              fontSize: 11, fontWeight: 600, color: "#9ca3af",
              textTransform: "uppercase", letterSpacing: 1, marginBottom: 8,
            }}>
              Preview
            </div>
            {selected ? (
              <>
                <div style={{
                  flex: 1, borderRadius: 8, border: "1px solid #e5e7eb",
                  overflow: "auto", padding: 12, background: "#f9fafb",
                }}>
                  <AnnotationProvider>
                    <LiveProvider
                      code={selected.source}
                      scope={{ ...scope, data: selected.data, annotations: selected.annotations }}
                      theme={themes.oneLight}
                    >
                      <LivePreview />
                      <LiveError />
                    </LiveProvider>
                  </AnnotationProvider>
                </div>
                <button
                  onClick={() => { onSelect(selected); onClose(); }}
                  style={{
                    marginTop: 12,
                    padding: "8px 20px",
                    borderRadius: 8,
                    border: "none",
                    background: "linear-gradient(to right, #F97316, #ef4444)",
                    color: "#fff",
                    fontWeight: 600,
                    fontSize: 14,
                    cursor: "pointer",
                  }}
                >
                  Use Template
                </button>
              </>
            ) : (
              <div style={{
                flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
                color: "#9ca3af", fontSize: 14,
              }}>
                Select a template to preview
              </div>
            )}
          </div>
        </div>

        {/* Cancel button */}
        <div style={{ marginTop: 12, textAlign: "right" }}>
          <button onClick={onClose} style={{
            padding: "6px 16px", borderRadius: 6, border: "1px solid #ddd",
            background: "#fff", cursor: "pointer", fontSize: 13,
          }}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

function TemplateCard({
  template,
  isSelected,
  onClick,
}: {
  template: PredefinedTemplate;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <div
      onClick={onClick}
      style={{
        padding: "8px 12px",
        marginBottom: 4,
        border: isSelected ? "2px solid #F97316" : "1px solid #ddd",
        borderRadius: 6,
        cursor: "pointer",
        background: isSelected ? "#fff7ed" : "#fff",
      }}
      onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.borderColor = "#888"; }}
      onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.borderColor = "#ddd"; }}
    >
      <div style={{ fontWeight: 600, fontSize: 13 }}>{template.name}</div>
      <div style={{ fontSize: 12, color: "#666", marginTop: 2 }}>
        {template.description}
      </div>
    </div>
  );
}
