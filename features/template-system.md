# Template System

**Date:** 2026-08-13
**Status:** Approved

## Concept

A template is a restricted React component stored as a string in the backend.
It transforms one dataset row into a labeling UI using predefined annotation
widgets. The template source code is edited in the Setup View and rendered in
the Label View — annotators never see the editor.

## Engine: react-live

`react-live` provides the following components:

| Component    | Used In       | Purpose                           |
| ------------ | ------------- | --------------------------------- |
| LiveEditor   | Setup View    | Write/edit template source code   |
| LivePreview  | Setup & Label | Render the template with row data |
| LiveProvider | Both          | Sandbox + inject globals          |
| LiveError    | Setup View    | Display compile/runtime errors    |

The setup view shows `LiveError` below the editor so the admin sees syntax errors
and runtime exceptions immediately. The `validated` flag on the template (see
Template Storage) is set by the frontend when `LiveError` shows no errors.

### Globals Available Inside Templates

```typescript
// Dataset row (injected)
row: Record<string, any>;

// Existing annotations for this row by this user (injected)
annotations: Record<string, any>;

// Predefined annotation widgets (see below)
SelectField, CheckboxGroup, BBoxField, NERField, TextField, RatingField;

// React hooks
useState, useCallback;

// Annotation context hook
useAnnotationContext: () => {
  registerField, getAnnotations;
};
```

## Annotation Widgets

All widgets auto-register with `AnnotationContext` via `useAnnotationContext`.
The parent app calls `getAnnotations()` on submit.

### SelectField

```jsx
<SelectField
  name="sentiment"
  labels={["positive", "negative", "neutral"]}
  defaultValue="neutral"
/>
```

**Props:** `name` (required), `labels` (required), `defaultValue` (optional, pre-fills from existing annotation)

**Produces:** `{ "sentiment": "positive" }`

### CheckboxGroup

```jsx
<CheckboxGroup
  name="topics"
  options={["technology", "science", "politics", "sports"]}
  defaultValue={annotations?.topics}
/>
```

**Props:** `name` (required), `options` (required), `defaultValue` (optional, pre-fills checked items)

**Produces:** `{ "topics": ["technology", "science"] }`

### BBoxField

```jsx
<BBoxField
  name="objects"
  imageUrl={row.image}
  categories={["car", "person", "bicycle"]}
  defaultValue={annotations?.objects}
/>
```

**Props:** `name` (required), `imageUrl` (required), `categories` (required), `defaultValue` (optional, pre-fills bboxes)

**Produces:** `{ "objects": [{ "x": 0.1, "y": 0.2, "w": 0.5, "h": 0.3, "category": "car" }] }`

Coordinates are normalized [0, 1] relative to image dimensions.

### NERField

```jsx
<NERField
  name="entities"
  text={row.text}
  entityTypes={["PERSON", "ORG", "LOC", "DATE"]}
  defaultValue={annotations?.entities}
/>
```

**Props:** `name` (required), `text` (required), `entityTypes` (required), `defaultValue` (optional, pre-fills entity spans)

**Produces:** `{ "entities": [{ "start": 12, "end": 25, "entity": "PERSON" }] }`

### TextField

```jsx
<TextField
  name="comment"
  placeholder="Optional notes..."
  multiline
  defaultValue={annotations?.comment}
/>
```

**Props:** `name` (required), `placeholder` (optional), `multiline` (optional), `defaultValue` (optional)

**Produces:** `{ "comment": "Free text response" }`

### RatingField

```jsx
<RatingField
  name="quality"
  max={5}
  icon="star"
  defaultValue={annotations?.quality}
/>
```

**Props:** `name` (required), `max` (required), `icon` (optional), `defaultValue` (optional)

## Example Templates

### 1. Text Classification

```jsx
function TextClassification({ row, annotations }) {
  return (
    <div style={{ padding: 20 }}>
      <h3>Classify the sentiment</h3>
      <p style={{ fontSize: 18, lineHeight: 1.5 }}>{row.text}</p>
      <SelectField
        name="sentiment"
        labels={["positive", "negative", "neutral"]}
        defaultValue={annotations?.sentiment}
      />
    </div>
  );
}
```

### 2. Image Bounding Boxes

```jsx
function ImageBBox({ row, annotations }) {
  return (
    <div style={{ padding: 20 }}>
      <h3>Draw bounding boxes around objects</h3>
      <BBoxField
        name="objects"
        imageUrl={row.image}
        categories={["car", "person", "bicycle", "traffic_light"]}
        defaultValue={annotations?.objects}
      />
    </div>
  );
}
```

### 3. Named Entity Recognition

```jsx
function NERLabeling({ row, annotations }) {
  return (
    <div style={{ padding: 20 }}>
      <h3>Tag named entities</h3>
      <NERField
        name="entities"
        text={row.text}
        entityTypes={["PERSON", "ORG", "LOC", "DATE", "PRODUCT"]}
        defaultValue={annotations?.entities}
      />
    </div>
  );
}
```

### 4. Content Moderation (nested output)

```jsx
function ContentModeration({ row, annotations }) {
  return (
    <div style={{ padding: 20 }}>
      <h3>Moderate this content</h3>
      <p style={{ fontSize: 18, lineHeight: 1.5 }}>{row.text}</p>

      <SelectField
        name="verdict"
        labels={["approved", "rejected", "needs_review"]}
        defaultValue={annotations?.verdict}
      />

      <CheckboxGroup
        name="flags"
        options={["spam", "hate_speech", "misinformation", "nsfw"]}
        defaultValue={annotations?.flags}
      />

      <TextField
        name="notes"
        placeholder="Optional moderator notes..."
        multiline
        defaultValue={annotations?.notes}
      />
    </div>
  );
}
```

This template combines three widgets and produces a nested annotation object:

```json
{
  "verdict": "rejected",
  "flags": ["spam", "misinformation"],
  "notes": "Clear spam with false claims"
}
```

## Template Storage

Templates are stored as source code strings in the backend:

```json
{
  "id": "template-uuid",
  "name": "sentiment-v1",
  "source": "function TextClassification(...) { ... }",
  "project_id": "project-uuid",
  "validated": true,
  "created_at": "2026-08-13T00:00:00Z",
  "updated_at": "2026-08-13T00:00:00Z"
}
```

The `validated` flag is set by the frontend when `LiveError` reports no errors
during editing. It is informational — the backend does not enforce it.

## Future Considerations

- **Template versioning** — track changes to templates over time
- **Template sharing** — reuse templates across projects
- **Pre-flight validation** — compile check templates on save
