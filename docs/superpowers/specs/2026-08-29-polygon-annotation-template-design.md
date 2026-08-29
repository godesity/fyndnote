# Polygon Annotation Template — Design

Date: 2026-08-29
Status: Approved (brainstorming)

## Goal

Add a selectable image-annotation template for polygons, usable when creating
and editing a project. Requires a new `PolygonField` widget plus an "Image
Polygon" predefined template entry.

## Constraints (from user)

- Only straight-line segments (no curves).
- Must support three shape types: **closed** polygon, **open** polyline, and
  **single point**.
- Editing: drag a vertex to move it; click a vertex to delete it; drag inside a
  shape's area to move the whole shape.

## Architecture

- **Widget** (`frontend/src/widgets/PolygonField.tsx`): a single React component
  handling drawing, editing, and rendering for all three shape types. Mirrors
  `BBoxField` conventions and prop surface.
- **Template** (`frontend/src/predefinedTemplates.ts`): new `IMAGE_POLYGON`
  source and `PREDEFINED_TEMPLATES` entry, group `image`, selectable in the
  Load Template dialog (used by both SetupView and EditProjectView).
- **Docs** (`frontend/src/components/WidgetDocs.tsx`): a `PolygonField` entry.
- **Export** (`frontend/src/widgets/index.ts`): register `PolygonField`.

No backend changes: polygons are ordinary annotation JSON values under a
widget `name`, exactly like `BBoxField`.

## Data shape

Stored value is `Shape[]` under the widget `name`:

```ts
interface Point { x: number; y: number }   // normalized 0..1
interface Shape {
  id: string;                    // stable identity for editing
  category: string;
  type: 'closed' | 'open' | 'point';
  points: Point[];               // point: 1, open: ≥2, closed: ≥3
}
```

Coordinates are normalized to image bounds (0..1), matching `BBoxField`.

## Widget props

```ts
interface Props {
  name: string;          // required — annotation key
  imageUrl: string;      // required
  categories: string[];  // required
  defaultValue?: Shape[];
  colors?: string[];     // per-category color override (defaults shared w/ BBoxField palette)
}
```

## Drawing interaction

- Category buttons select the active category (color-coded, like `BBoxField`).
- Mode buttons: **Closed / Open / Point**.
- Click on the image to place vertices. A live preview line follows the cursor
  from the last placed vertex.
- Finish the shape with a **double-click** or **Enter**. The widget
  auto-assigns `id`, `category`, and `type` from the active mode.
- Minimum points by mode: point = 1, open = 2, closed = 3. Shapes below the
  minimum are rejected (not added).

## Editing behavior

- Click a **vertex** → delete that vertex. If removal leaves a shape below its
  mode minimum, the whole shape is deleted.
- **Drag a vertex** → move it.
- **Drag inside a shape's area** (not on a vertex) → move the whole shape.
- **Click the shape body** (not a vertex) → delete the whole shape (parity with
  `BBoxField`).

## Rendering

An SVG overlay (`<polygon>` / `<polyline>` / `<circle>`) sized to the image
bounds. Category-colored stroke/fill with a show/hide labels toggle, matching
`BBoxField` visuals. SVG is used because vertex counts are arbitrary and
`polygon`/`polyline`/`circle` map directly to the three shape types.

## Predefined template

Name: **Image Polygon** (group `image`). Template uses `name="objects"`, reads
`data.image_url`, and default annotations include one closed, one open, and one
point shape to demonstrate all types in the preview.

## Verification

No frontend test framework exists (scripts: `dev` / `build` / `lint` /
`preview`). Verification is:
- `npx tsc --noEmit` (and `tsc -b`) compile clean.
- `npm run lint` passes.
- Manual live-preview check: the template renders and draws all three shape
  types in `LoadTemplateDialog` preview and `LabelView`.

## Files

- `frontend/src/widgets/PolygonField.tsx` — new widget (draw + edit + render).
- `frontend/src/widgets/index.ts` — export `PolygonField`.
- `frontend/src/predefinedTemplates.ts` — add `IMAGE_POLYGON` + template entry.
- `frontend/src/components/WidgetDocs.tsx` — add `PolygonField` doc entry.
- `docs/superpowers/specs/2026-08-29-polygon-annotation-template-design.md` — this spec.
