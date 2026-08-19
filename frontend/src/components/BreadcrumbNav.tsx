interface Crumb {
  label: string;
  href?: string;
}

export default function BreadcrumbNav({ crumbs }: { crumbs: Crumb[] }) {
  return (
    <nav className="flex items-center gap-2 text-sm text-[var(--color-text-muted)] px-6 py-3 border-b border-[var(--color-border)] bg-white">
      <a href="/" className="flex items-center">
        <span className="w-8 h-8 rounded-full bg-gradient-to-r from-sunset-500 to-coral-500 flex items-center justify-center">
          <img src="/favicon.svg" alt="Logo" className="h-4 w-4 brightness-0 invert" />
        </span>
      </a>
      <span className="text-[var(--color-border)]">|</span>
      {crumbs.map((crumb, i) => (
        <span key={i} className="flex items-center gap-2">
          {i > 0 && <span className="text-[var(--color-text-muted)]">/</span>}
          {crumb.href ? (
            <a
              href={crumb.href}
              className="hover:text-sunset-500 transition-colors no-underline"
            >
              {crumb.label}
            </a>
          ) : (
            <span className="font-semibold text-sunset-500">{crumb.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}
