export interface TemplateAttribute {
  // Identifier as it appears in the template source: `data.<key>` or
  // `<obj>.<key>` (annotation widget `name` + defaultValue lookup).
  key: string;
  kind: "data" | "annotation";
  label: string;
}

export interface PredefinedTemplate {
  name: string;
  description: string;
  group: "text" | "image" | "audio";
  source: string;
  data: Record<string, any>;
  annotations: Record<string, any>;
  // Temporary attribute names shown in the Load Template dialog. Renaming one
  // rewrites the template source so it reads the user's own column names.
  attributes?: TemplateAttribute[];
}

const VALID_KEY = /^[A-Za-z_]\w*$/;

// Applies user-supplied attribute renames (original key -> new key) to a
// template in one pass: rewrites `data.<key>`, `annotations?.<key>`, and
// `name="<key>"` in the source, and remaps the sample data/annotation keys so
// the preview keeps working. Invalid identifiers are ignored (key unchanged).
export function applyAttributeRenames(
  tpl: PredefinedTemplate,
  renames: Record<string, string>
): { source: string; data: Record<string, any>; annotations: Record<string, any> } {
  const map: Record<string, string> = {};
  for (const attr of tpl.attributes ?? []) {
    const next = (renames[attr.key] ?? "").trim();
    if (next && next !== attr.key && VALID_KEY.test(next)) map[attr.key] = next;
  }
  if (Object.keys(map).length === 0) {
    return { source: tpl.source, data: tpl.data, annotations: tpl.annotations };
  }

  let source = tpl.source.replace(
    /\bdata\.([A-Za-z_]\w*)/g,
    (m, k) => (map[k] ? `data.${map[k]}` : m)
  );
  source = source.replace(
    /\bannotations\?\.([A-Za-z_]\w*)/g,
    (m, k) => (map[k] ? `annotations?.${map[k]}` : m)
  );
  source = source.replace(
    /name="([A-Za-z_]\w*)"/g,
    (m, k) => (map[k] ? `name="${map[k]}"` : m)
  );

  return { source, data: renameKeys(tpl.data, map), annotations: renameKeys(tpl.annotations, map) };
}

function renameKeys(obj: Record<string, any>, map: Record<string, string>): Record<string, any> {
  const out: Record<string, any> = {};
  for (const [k, v] of Object.entries(obj)) out[map[k] ?? k] = v;
  return out;
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

const IMAGE_POLYGON = `<div>
  <h3>Annotate polygons in the image</h3>
  {data.image_url && (
    <PolygonField
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
    attributes: [
      { key: "text", kind: "data", label: "Input text" },
      { key: "sentiment", kind: "annotation", label: "Sentiment" },
    ],
  },
  {
    name: "Image BBox",
    description: "Bounding box annotation for object detection",
    group: "image",
    data: { image_url: "./labeling_template/image-sample.png" },
    annotations: { objects: [] },
    source: IMAGE_BBOX,
    attributes: [
      { key: "image_url", kind: "data", label: "Image URL" },
      { key: "objects", kind: "annotation", label: "Objects" },
    ],
  },
  {
    name: "Image Polygon",
    description: "Annotate closed polygons, open polylines, and points",
    group: "image",
    data: { image_url: "./labeling_template/image-sample.png" },
    annotations: {
      objects: [
        {
          id: "demo-closed",
          category: "cat",
          type: "closed",
          points: [
            { x: 0.1, y: 0.1 },
            { x: 0.3, y: 0.2 },
            { x: 0.25, y: 0.4 },
            { x: 0.1, y: 0.35 },
          ],
        },
        {
          id: "demo-open",
          category: "dog",
          type: "open",
          points: [
            { x: 0.5, y: 0.1 },
            { x: 0.6, y: 0.3 },
            { x: 0.7, y: 0.2 },
          ],
        },
        {
          id: "demo-point",
          category: "person",
          type: "point",
          points: [{ x: 0.8, y: 0.8 }],
        },
      ],
    },
    source: IMAGE_POLYGON,
    attributes: [
      { key: "image_url", kind: "data", label: "Image URL" },
      { key: "objects", kind: "annotation", label: "Objects" },
    ],
  },
  {
    name: "NER",
    description: "Named entity recognition with token-level tags",
    group: "text",
    data: { text: "Apple Inc. is based in Cupertino, California." },
    annotations: {
      entities: [
        { start: 0, end: 9, entity: "ORG" },
        { start: 23, end: 33, entity: "LOC" },
        { start: 36, end: 46, entity: "LOC" },
      ],
    },
    source: NER,
    attributes: [
      { key: "text", kind: "data", label: "Input text" },
      { key: "entities", kind: "annotation", label: "Entities" },
    ],
  },
  {
    name: "Free Text",
    description: "Open-ended text response field",
    group: "text",
    data: { text: "A cat sitting on a windowsill watching the rain." },
    annotations: { response: "The image depicts a domestic cat perched on a windowsill, gazing outward at the rainfall." },
    source: FREE_TEXT,
    attributes: [
      { key: "text", kind: "data", label: "Input text" },
      { key: "input", kind: "data", label: "Fallback input" },
      { key: "response", kind: "annotation", label: "Response" },
    ],
  },
  {
    name: "Rating + Checkbox",
    description: "Star rating with multi-select category checkboxes",
    group: "text",
    data: { text: "This article was very helpful for understanding the topic." },
    annotations: { rating: 4, tags: ["informative"] },
    source: RATING_CHECKBOX,
    attributes: [
      { key: "text", kind: "data", label: "Input text" },
      { key: "rating", kind: "annotation", label: "Rating" },
      { key: "tags", kind: "annotation", label: "Categories" },
    ],
  },
  {
    name: "Audio Segments",
    description: "Timeline-based audio segment labeling with labels",
    group: "audio",
    data: { audio_url: "./labeling_template/audio-sample.mp3" },
    annotations: { segments: [] },
    source: AUDIO_SEGMENTS,
    attributes: [
      { key: "audio_url", kind: "data", label: "Audio URL" },
      { key: "segments", kind: "annotation", label: "Segments" },
    ],
  },
  {
    name: "Audio Playback",
    description: "Play audio with an overall classification dropdown",
    group: "audio",
    data: { audio_url: "./labeling_template/audio-sample.mp3" },
    annotations: { classification: "speech" },
    source: AUDIO_PLAYBACK,
    attributes: [
      { key: "audio_url", kind: "data", label: "Audio URL" },
      { key: "classification", kind: "annotation", label: "Classification" },
    ],
  },
];
