import type { ReactNode } from 'react';

export default function GradientBorderCard({
  children,
  className = '',
  gradient = 'from-sunset-500 via-coral-500 to-violet-500',
  color,
}: {
  children: ReactNode;
  className?: string;
  gradient?: string;
  color?: string;
}) {
  if (color && !gradient) {
    return (
      <div
        className={`rounded-xl bg-white shadow-sm border border-[var(--color-border)] hover:shadow-md transition-shadow ${className}`}
        style={{ borderLeft: `4px solid ${color}` }}
      >
        {children}
      </div>
    );
  }

  return (
    <div className={`p-[2px] rounded-xl bg-gradient-to-r ${gradient} shadow-sm hover:shadow-md transition-shadow ${className}`}>
      <div className="bg-white rounded-[calc(0.75rem-2px)] h-full">
        {children}
      </div>
    </div>
  );
}
