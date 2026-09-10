export function SkeletonBar({ className = '' }: { className?: string }) {
  return (
    <div className={`relative overflow-hidden rounded bg-[var(--color-surface-sunken)] ${className}`}>
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent animate-shimmer" />
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="p-[2px] rounded-xl bg-gradient-to-r from-[var(--color-border)] via-[var(--color-surface-sunken)] to-[var(--color-border)] animate-fade-in">
      <div className="bg-[var(--color-surface)] rounded-[calc(0.75rem-2px)] p-5 space-y-3">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[var(--color-surface-sunken)] relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent animate-shimmer" />
          </div>
          <SkeletonBar className="h-4 w-1/2" />
        </div>
        <SkeletonBar className="h-3 w-1/3" />
        <div className="flex gap-1.5">
          <SkeletonBar className="h-5 w-12 rounded-md" />
          <SkeletonBar className="h-5 w-16 rounded-md" />
        </div>
      </div>
    </div>
  );
}

export function SkeletonLabelView() {
  return (
    <div className="p-6 space-y-4 animate-fade-in">
      <SkeletonBar className="h-4 w-32" />
      <SkeletonBar className="h-2 w-full rounded-full" />
      <div className="flex gap-6 mt-6">
        <div className="flex-1 space-y-3">
          <SkeletonBar className="h-4 w-3/4" />
          <SkeletonBar className="h-4 w-1/2" />
          <SkeletonBar className="h-4 w-2/3" />
          <div className="flex gap-2 mt-4">
            <SkeletonBar className="h-8 w-20 rounded-lg" />
            <SkeletonBar className="h-8 w-20 rounded-lg" />
            <SkeletonBar className="h-8 w-20 rounded-lg" />
          </div>
        </div>
        <div className="w-8 rounded-lg bg-gradient-to-b from-sunset-500 to-coral-500" />
      </div>
    </div>
  );
}
