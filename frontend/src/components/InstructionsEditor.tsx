interface Props {
  value: string;
  onChange: (value: string) => void;
}

export default function InstructionsEditor({ value, onChange }: Props) {
  return (
    <div className="space-y-3">
      <p className="text-xs text-[var(--color-text-muted)]">
        Supports <strong>HTML</strong> and basic <strong>Markdown</strong> syntax. These instructions will appear in the guidelines sidebar for annotators.
      </p>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="# Annotation Guidelines&#10;&#10;Use this space to describe how annotators should think when labeling..."
        className="w-full h-64 px-3 py-2.5 border border-[var(--color-border)] rounded-lg text-sm font-mono focus:outline-none focus:border-sunset-400 focus:ring-3 focus:ring-sunset-100 resize-y"
      />
      <details className="group">
        <summary className="text-xs font-medium text-[var(--color-text-muted)] cursor-pointer hover:text-[var(--color-text)] select-none">
          Preview
        </summary>
        <div className="mt-2 p-3 border border-[var(--color-border)] rounded-lg bg-[var(--color-surface-secondary)] text-sm prose prose-sm max-w-none">
          {value ? (
            <RenderInstructions html={value} />
          ) : (
            <span className="text-[var(--color-text-muted)] italic">No instructions yet.</span>
          )}
        </div>
      </details>
    </div>
  );
}

export function RenderInstructions({ html }: { html: string }) {
  const inline = (s: string) =>
    s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\*(.+?)\*/g, '<em>$1</em>');

  const blocks = html.split(/\n\n+/).map((block) => {
    const mHeading = block.match(/^(#{1,3})\s+(.+)/);
    if (mHeading) {
      const level = mHeading[1].length;
      const cls = ['mt-4 mb-1 font-bold', 'mt-3 mb-1 font-semibold', 'mt-3 mb-1 font-semibold text-sm'][level - 1];
      return `<${['h1','h2','h3'][level - 1]} class="${cls}">${inline(mHeading[2])}</${['h1','h2','h3'][level - 1]}>`;
    }
    if (block.startsWith('- ') || block.startsWith('* ')) {
      const items = block.split('\n').map((l) => `<li>${inline(l.replace(/^[-*]\s+/, ''))}</li>`).join('');
      return `<ul class="list-disc ml-5 mb-2">${items}</ul>`;
    }
    if (/^\d+\.\s/.test(block)) {
      const items = block.split('\n').map((l) => `<li>${inline(l.replace(/^\d+\.\s+/, ''))}</li>`).join('');
      return `<ol class="list-decimal ml-5 mb-2">${items}</ol>`;
    }
    const lines = block.split('\n').map((l) => inline(l)).join('<br>');
    return `<p class="mb-2">${lines}</p>`;
  });

  return <div dangerouslySetInnerHTML={{ __html: blocks.join('\n') }} />;
}
