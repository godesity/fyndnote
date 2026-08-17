interface Props {
  byMe: boolean;
  byAny: boolean;
  annotators: string[];
}

export default function AnnotationStatusBadge({ byMe, byAny, annotators }: Props) {
  if (byMe) {
    return (
      <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600 border border-emerald-200 text-xs font-medium whitespace-nowrap">
        Annotated by me
      </span>
    );
  }
  if (byAny) {
    return (
      <span className="px-2 py-0.5 rounded-full bg-amber-50 text-amber-600 border border-amber-200 text-xs font-medium whitespace-nowrap">
        {annotators.join(', ')}
      </span>
    );
  }
  return (
    <span className="px-2 py-0.5 rounded-full bg-gray-50 text-gray-400 border border-gray-200 text-xs whitespace-nowrap">
      Unannotated
    </span>
  );
}
