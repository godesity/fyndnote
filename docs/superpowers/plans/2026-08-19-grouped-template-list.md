# Grouped Template List Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Load Template dialog to group predefined templates by modality (text/image/audio), add filter pills, and show a live preview when a template is selected.

**Architecture:** Frontend-only change. Extend `PredefinedTemplate` interface with `group`, `data`, and `annotations` fields. Rewrite `LoadTemplateDialog` with a three-zone layout: filter pills, grouped list, and LiveProvider-based preview panel. Static media files served from `frontend/public/labeling_template/`.

**Tech Stack:** React, TypeScript, react-live (LiveProvider/LivePreview)

---

### Task 1: Update PredefinedTemplate interface and data

**Files:**
- Modify: `frontend/src/predefinedTemplates.ts`

- [ ] **Step 1: Rewrite predefinedTemplates.ts with new fields**

Replace the entire file content:

```typescript
export interface PredefinedTemplate {
  name: string;
  description: string;
  group: "text" | "image" | "audio";
  source: string;
  data: Record<string, any>;
  annotations: Record<string, any>;
}

const TEXT_CLASSIFICATION = `<div style={{ padding: 20 }}>
  <h3>Classify the sentiment</h3>
  <p style={{ fontSize: 18 }}>{data.text}</p>
  <SelectField
    name="sentiment"
    labels={["positive", "negative", "neutral"]}
    defaultValue={annotations?.sentiment}
  />
</div>`;

const IMAGE_BBOX = `<div>
  <h3>Annotate objects in the image</h3>
  {data.image_url && (
    <BBoxField
      name="objects"
      imageUrl={data.image_url}
      categories={["cat", "dog", "car", "person"]}
      defaultValue={annotations?.objects}
    />
  )}
  {!data.image_url && <p>No image_url field found in this dataset.</p>}
</div>`;

const NER = `<div>
  <h3>Tag named entities</h3>
  {data.text && (
    <NERField
      name="entities"
      text={data.text}
      entityTypes={["PERSON", "ORG", "LOC", "DATE"]}
      defaultValue={annotations?.entities}
    />
  )}
</div>`;

const FREE_TEXT = `<div style={{ padding: 20 }}>
  <h3>Provide a description</h3>
  <p><strong>Input:</strong> {data.text || data.input || JSON.stringify(data)}</p>
  <TextField
    name="response"
    placeholder="Enter your annotation..."
    multiline
    defaultValue={annotations?.response}
  />
</div>`;

const RATING_CHECKBOX = `<div style={{ padding: 20 }}>
  <h3>Rate and tag</h3>
  <p style={{ fontSize: 18 }}>{data.text}</p>
  <p>Rating:</p>
  <RatingField name="rating" max={5} defaultValue={annotations?.rating} />
  <p style={{ marginTop: 12 }}>Categories:</p>
  <CheckboxGroup
    name="tags"
    labels={["spam", "offensive", "informative", "question"]}
    defaultValue={annotations?.tags}
  />
</div>`;

const AUDIO_SEGMENTS = `<div style={{ padding: 20 }}>
  <h3>Label audio segments</h3>
  {data.audio_url ? (
    <AudioSegmentField
      name="segments"
      url={data.audio_url}
      labels={["speech", "music", "noise", "silence"]}
      defaultValue={annotations?.segments}
    />
  ) : (
    <p>No audio_url field found in this dataset.</p>
  )}
</div>`;

const AUDIO_PLAYBACK = `<div style={{ padding: 20 }}>
  <h3>Listen and classify</h3>
  {data.audio_url ? (
    <>
      <AudioPlayer url={data.audio_url} />
      <p style={{ marginTop: 12 }}>Overall classification:</p>
      <SelectField
        name="classification"
        labels={["clean", "noisy", "music", "speech"]}
        defaultValue={annotations?.classification}
      />
    </>
  ) : (
    <p>No audio_url field found in this dataset.</p>
  )}
</div>`;

export const PREDEFINED_TEMPLATES: PredefinedTemplate[] = [
  {
    name: "Text Classification",
    description: "Single-label text classification with a dropdown",
    group: "text",
    data: { text: "This product is amazing! I love the new design." },
    annotations: { sentiment: "positive" },
    source: TEXT_CLASSIFICATION,
  },
  {
    name: "Image BBox",
    description: "Bounding box annotation for object detection",
    group: "image",
    data: { image_url: "./labeling_template/image-sample.png" },
    annotations: { objects: [] },
    source: IMAGE_BBOX,
  },
  {
    name: "NER",
    description: "Named entity recognition with token-level tags",
    group: "text",
    data: { text: "Apple Inc. is based in Cupertino, California." },
    annotations: {
      entities: [
        { start: 0, end: 9, type: "ORG" },
        { start: 23, end: 33, type: "LOC" },
        { start: 36, end: 46, type: "LOC" },
      ],
    },
    source: NER,
  },
  {
    name: "Free Text",
    description: "Open-ended text response field",
    group: "text",
    data: { text: "A cat sitting on a windowsill watching the rain." },
    annotations: { response: "The image depicts a domestic cat perched on a windowsill, gazing outward at the rainfall." },
    source: FREE_TEXT,
  },
  {
    name: "Rating + Checkbox",
    description: "Star rating with multi-select category checkboxes",
    group: "text",
    data: { text: "This article was very helpful for understanding the topic." },
    annotations: { rating: 4, tags: ["informative"] },
    source: RATING_CHECKBOX,
  },
  {
    name: "Audio Segments",
    description: "Timeline-based audio segment labeling with labels",
    group: "audio",
    data: { audio_url: "./labeling_template/audio-sample.mp3" },
    annotations: { segments: [] },
    source: AUDIO_SEGMENTS,
  },
  {
    name: "Audio Playback",
    description: "Play audio with an overall classification dropdown",
    group: "audio",
    data: { audio_url: "./labeling_template/audio-sample.mp3" },
    annotations: { classification: "speech" },
    source: AUDIO_PLAYBACK,
  },
];
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/predefinedTemplates.ts
git commit -m "feat: add group, data, annotations to PredefinedTemplate interface"
```

---

### Task 2: Create example media files

**Files:**
- Create: `frontend/public/labeling_template/image-sample.png`
- Create: `frontend/public/labeling_template/audio-sample.mp3`

- [ ] **Step 1: Create directory**

```bash
mkdir -p frontend/public/labeling_template
```

- [ ] **Step 2: Generate image-sample.png using Pillow**

Run: `cd frontend/public/labeling_template && python3 -c "
from PIL import Image, ImageDraw
img = Image.new('RGB', (640, 480), 'white')
draw = ImageDraw.Draw(img)
# Draw a simple scene: ground, house, sun, tree
draw.rectangle([(0, 360), (640, 480)], fill='#4ade80')  # grass
draw.rectangle([(200, 200), (450, 360)], fill='#fbbf24')  # house body
draw.polygon([(180, 200), (325, 100), (470, 200)], fill='#ef4444')  # roof
draw.rectangle([(280, 260), (330, 360)], fill='#92400e')  # door
draw.rectangle([(360, 240), (420, 290)], fill='#93c5fd')  # window
draw.ellipse([(500, 40), (560, 100)], fill='#facc15')  # sun
# tree
draw.rectangle([(80, 280), (110, 360)], fill='#78350f')
draw.ellipse([(50, 200), (140, 290)], fill='#22c55e')
# person (small figure)
draw.ellipse([(520, 340), (540, 360)], fill='#fca5a5')  # head
draw.rectangle([(525, 360), (535, 390)], fill='#3b82f6')  # body
# car
draw.rectangle([(50, 380), (180, 420)], fill='#ef4444')  # car body
draw.rectangle([(70, 370), (160, 380)], fill='#93c5fd')  # windshield
draw.ellipse([(65, 412), (90, 432)], fill='#1f2937')  # wheel
draw.ellipse([(140, 412), (165, 432)], fill='#1f2937')  # wheel
# dog
draw.ellipse([(350, 395), (380, 420)], fill='#a16207')  # dog body
draw.ellipse([(340, 385), (360, 405)], fill='#a16207')  # dog head
img.save('image-sample.png')
print('Created image-sample.png')
"
```

Expected output: `Created image-sample.png`

- [ ] **Step 3: Generate audio-sample.mp3 using ffmpeg**

Run: `ffmpeg -f lavfi -i "sine=frequency=440:duration=5" -f lavfi -i "sine=frequency=330:duration=5" -filter_complex "[0:a][1:a]amix=inputs=2:duration=first" -b:a 128k frontend/public/labeling_template/audio-sample.mp3 -y 2>&1 | tail -3`

Expected: A 5-second audio file with a pleasant tone mix at `frontend/public/labeling_template/audio-sample.mp3`

- [ ] **Step 4: Commit**

```bash
git add frontend/public/labeling_template/
git commit -m "feat: add example media files for template previews"
```

---

### Task 3: Rewrite LoadTemplateDialog with groups and preview

**Files:**
- Create: `frontend/src/components/LoadTemplateDialog.tsx` (full rewrite)

- [ ] **Step 1: Write the new LoadTemplateDialog component**

Replace `frontend/src/components/LoadTemplateDialog.tsx` with:

```typescript
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
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`

Expected: No type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/LoadTemplateDialog.tsx
git commit -m "feat: group templates by modality with live preview in LoadTemplateDialog"
```

---

### Task 4: Verify the build

- [ ] **Step 1: Run the frontend build**

Run: `cd frontend && npm run build 2>&1 | tail -10`

Expected: Build succeeds with no errors.

- [ ] **Step 2: Commit if clean**

```bash
git add -A
git commit -m "chore: verify build passes"
```
