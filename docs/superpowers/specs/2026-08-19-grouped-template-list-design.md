# Grouped Template Selection with Preview

## Problem

The Load Template dialog shows all 7 predefined templates in a flat, unsorted list with no
grouping or preview. Users cannot filter by modality (text / image / audio) and cannot see what
a template looks like with real data before selecting it.

## Design

### Data model — PredefinedTemplate

New fields added to the existing interface in `frontend/src/predefinedTemplates.ts`:

```typescript
export interface PredefinedTemplate {
  name: string;
  description: string;
  group: "text" | "image" | "audio";
  source: string;
  data: Record<string, any>;        // example row data for live preview
  annotations: Record<string, any>; // default annotation values for preview
}
```

### Template assignments

| Template | group | data | annotations |
|---|---|---|---|
| Text Classification | text | `{ text: "This product is amazing! I love the new design." }` | `{ sentiment: "positive" }` |
| NER | text | `{ text: "Apple Inc. is based in Cupertino, California." }` | `{ entities: [{ start: 0, end: 9, type: "ORG" }, { start: 23, end: 33, type: "LOC" }, { start: 36, end: 46, type: "LOC" }] }` |
| Free Text | text | `{ text: "A cat sitting on a windowsill watching the rain." }` | `{ response: "The image depicts a domestic cat..." }` |
| Rating + Checkbox | text | `{ text: "This article was very helpful for understanding the topic." }` | `{ rating: 4, tags: ["informative"] }` |
| Image BBox | image | `{ image_url: "./labeling_template/image-sample.png" }` | `{ objects: [] }` |
| Audio Segments | audio | `{ audio_url: "./labeling_template/audio-sample.mp3" }` | `{ segments: [] }` |
| Audio Playback | audio | `{ audio_url: "./labeling_template/audio-sample.mp3" }` | `{ classification: "speech" }` |

### Example media files — `frontend/public/labeling_template/`

| File | Purpose |
|---|---|
| `image-sample.png` | Static example image for Image BBox preview (photo with visible objects) |
| `audio-sample.mp3` | Short 5-10s audio clip for Audio Segments / Audio Playback preview |

Text groups use inline `data` objects — no external files needed.

### UI — LoadTemplateDialog (_refactored_)

The dialog is redesigned from a flat list into three zones:

1. **Filter pills (top):** A row of pill buttons — `All | Text | Image | Audio`.
   - "All" is the default, showing all templates grouped by section.
   - Clicking a group pill filters to only templates in that group.

2. **Template list (left):**
   - When "All" is active: templates render under group section headers (`Text`, `Image`, `Audio`), each as a clickable card showing name + description.
   - When a specific group is active: the section header is hidden and only matching templates are shown.
   - Clicking a template card highlights it (orange border + background) and populates the preview panel.

3. **Preview panel (right):**
   - Shown when a template is selected.
   - Uses `LiveProvider` to render the template's `source` with `data` as the row and `annotations` as the saved annotation values.
   - A "Use Template" button at the bottom confirms the selection.

### Component changes

- **`frontend/src/predefinedTemplates.ts`** — Add `group`, `data`, `annotations` fields to each entry.
- **`frontend/src/components/LoadTemplateDialog.tsx`** — Full rewrite: filter pills, grouped list, preview panel.
- **`frontend/src/views/SetupView.tsx`** — Minor: `handleSelectTemplate` now receives the full `PredefinedTemplate` (unchanged signature), template dialog passes static data + annotations for preview.
- **`frontend/public/labeling_template/`** — New directory with `image-sample.png` and `audio-sample.mp3`.

### No backend changes

Templates are still frontend-only predefined templates. The backend `TemplateService` and API routes are unchanged.

### Files to modify / create

| Action | File |
|---|---|
| Modify | `frontend/src/predefinedTemplates.ts` |
| Rewrite | `frontend/src/components/LoadTemplateDialog.tsx` |
| Create | `frontend/public/labeling_template/image-sample.png` |
| Create | `frontend/public/labeling_template/audio-sample.mp3` |
| View only | `frontend/src/views/SetupView.tsx` (minimal or no changes) |
