export interface PredefinedTemplate {
  name: string;
  description: string;
  source: string;
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
    source: TEXT_CLASSIFICATION,
  },
  {
    name: "Image BBox",
    description: "Bounding box annotation for object detection",
    source: IMAGE_BBOX,
  },
  {
    name: "NER",
    description: "Named entity recognition with token-level tags",
    source: NER,
  },
  {
    name: "Free Text",
    description: "Open-ended text response field",
    source: FREE_TEXT,
  },
  {
    name: "Rating + Checkbox",
    description: "Star rating with multi-select category checkboxes",
    source: RATING_CHECKBOX,
  },
  {
    name: "Audio Segments",
    description: "Timeline-based audio segment labeling with labels",
    source: AUDIO_SEGMENTS,
  },
  {
    name: "Audio Playback",
    description: "Play audio with an overall classification dropdown",
    source: AUDIO_PLAYBACK,
  },
];
