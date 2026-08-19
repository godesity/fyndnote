import { useState } from 'react';

interface Prop {
  name: string;
  type: string;
  required?: boolean;
  desc: string;
}

interface Widget {
  name: string;
  description: string;
  props: Prop[];
}

const WIDGETS: Widget[] = [
  {
    name: 'SelectField',
    description: 'Single-select dropdown or button group.',
    props: [
      { name: 'name', type: 'string', required: true, desc: 'Field key stored in annotations.' },
      { name: 'labels', type: 'string[]', required: true, desc: 'Array of option labels, e.g. ["positive","negative"].' },
      { name: 'defaultValue', type: 'string', desc: 'Pre-selected value.' },
    ],
  },
  {
    name: 'TextField',
    description: 'Free-text input area.',
    props: [
      { name: 'name', type: 'string', required: true, desc: 'Field key stored in annotations.' },
      { name: 'defaultValue', type: 'string', desc: 'Initial text value.' },
      { name: 'placeholder', type: 'string', desc: 'Placeholder text shown when empty.' },
    ],
  },
  {
    name: 'CheckboxGroup',
    description: 'Multi-select checkbox group.',
    props: [
      { name: 'name', type: 'string', required: true, desc: 'Field key stored in annotations.' },
      { name: 'labels', type: 'string[]', required: true, desc: 'Array of checkbox labels.' },
      { name: 'defaultValue', type: 'string[]', desc: 'Pre-selected labels, e.g. ["option_a"].' },
    ],
  },
  {
    name: 'RatingField',
    description: 'Star / numeric rating selector.',
    props: [
      { name: 'name', type: 'string', required: true, desc: 'Field key stored in annotations.' },
      { name: 'max', type: 'number', desc: 'Maximum rating value (default 5).' },
      { name: 'defaultValue', type: 'number', desc: 'Pre-selected rating.' },
    ],
  },
  {
    name: 'NERField',
    description: 'Text annotation — select text to tag entities.',
    props: [
      { name: 'name', type: 'string', required: true, desc: 'Field key stored in annotations.' },
      { name: 'text', type: 'string', required: true, desc: 'The text content to annotate.' },
      { name: 'entityTypes', type: 'string[]', required: true, desc: 'Entity type labels, e.g. ["Person","Location"].' },
      { name: 'defaultValue', type: 'Entity[]', desc: 'Pre-existing entity spans.' },
      { name: 'colors', type: 'string[]', desc: 'Override entity colors (CSS color strings).' },
    ],
  },
  {
    name: 'BBoxField',
    description: 'Bounding box annotation on an image.',
    props: [
      { name: 'name', type: 'string', required: true, desc: 'Field key stored in annotations.' },
      { name: 'imageUrl', type: 'string', required: true, desc: 'URL or API path to the image.' },
      { name: 'categories', type: 'string[]', required: true, desc: 'Object category labels, e.g. ["cat","dog"].' },
      { name: 'defaultValue', type: 'BBox[]', desc: 'Pre-existing bounding boxes.' },
      { name: 'colors', type: 'string[]', desc: 'Override category colors (CSS color strings).' },
    ],
  },
  {
    name: 'AudioPlayer',
    description: 'Simple audio playback — play, pause, seek.',
    props: [
      { name: 'url', type: 'string', required: true, desc: 'URL to the audio file.' },
    ],
  },
  {
    name: 'AudioSegmentField',
    description: 'Timeline-based segment labeling on audio waveform.',
    props: [
      { name: 'name', type: 'string', required: true, desc: 'Field key stored in annotations.' },
      { name: 'url', type: 'string', required: true, desc: 'URL to the audio file.' },
      { name: 'labels', type: 'string[]', required: true, desc: 'Category labels, e.g. ["speaker_a","music"].' },
      { name: 'colors', type: 'string[]', desc: 'Override category colors (CSS color strings).' },
      { name: 'defaultValue', type: 'Segment[]', desc: 'Pre-existing segments [{start,end,label}].' },
    ],
  },
];

function CollapsibleWidget({ widget, defaultOpen }: { widget: Widget; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen || false);

  return (
    <div className="border border-[var(--color-border)] rounded-lg overflow-hidden bg-white">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-2.5 text-left hover:bg-gray-50 transition-colors"
      >
        <span className={`text-xs text-[var(--color-text-muted)] transition-transform ${open ? 'rotate-90' : ''}`}>▶</span>
        <code className="text-sm font-semibold text-sunset-600">{widget.name}</code>
        <span className="text-xs text-[var(--color-text-muted)] truncate">{widget.description}</span>
      </button>
      {open && (
        <div className="px-4 pb-3 pt-1 border-t border-[var(--color-border)] animate-fade-in">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                <th className="text-left py-1 pr-3 font-medium">Prop</th>
                <th className="text-left py-1 pr-3 font-medium">Type</th>
                <th className="text-left py-1 font-medium">Description</th>
              </tr>
            </thead>
            <tbody>
              {widget.props.map((prop) => (
                <tr key={prop.name} className="border-b border-[var(--color-border)] last:border-0">
                  <td className="py-1.5 pr-3">
                    <code className="text-[var(--color-text-heading)]">{prop.name}</code>
                    {prop.required && <span className="ml-1 text-red-400">*</span>}
                  </td>
                  <td className="py-1.5 pr-3">
                    <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">{prop.type}</code>
                  </td>
                  <td className="py-1.5 text-[var(--color-text-muted)]">{prop.desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function WidgetDocs() {
  return (
    <div className="space-y-1.5">
      {WIDGETS.map((w) => (
        <CollapsibleWidget key={w.name} widget={w} />
      ))}
    </div>
  );
}
