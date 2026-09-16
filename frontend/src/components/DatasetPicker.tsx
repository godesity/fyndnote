import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import { SkeletonBar } from "./SkeletonLoader";

export interface DatasetColumn {
  name: string;
  type: string;
}

export interface DatasetMeta {
  id: string;
  name: string | null;
  source: string;
  source_type: "huggingface" | "http" | "file";
  source_format: string | null;
  split: string | null;
  num_rows: number;
  columns: DatasetColumn[];
  created_at: string;
  s3_uploaded?: boolean;
  cache_available: boolean;
}

interface Props {
  value: string;
  datasets: DatasetMeta[];
  datasetsLoading: boolean;
  sampleStatus: "idle" | "loading" | "ready" | "error";
  sampleError: string | null;
  userId: string;
  onSelect: (id: string) => void;
  onDatasetsLoaded: (ds: DatasetMeta[]) => void;
  onRetrySample: () => void;
}

const ALL_TYPES = ["All", "HuggingFace", "URL", "File"] as const;
type TypeFilter = (typeof ALL_TYPES)[number];

const TYPE_OF: Record<DatasetMeta["source_type"], TypeFilter> = {
  huggingface: "HuggingFace",
  http: "URL",
  file: "File",
};

const TYPE_BADGE: Record<DatasetMeta["source_type"], string> = {
  huggingface: "HF",
  http: "URL",
  file: "FILE",
};

const SUPPORTED = ["csv", "json", "jsonl", "parquet"];
const extOf = (nameOrUrl: string) =>
  (nameOrUrl.split("?")[0].split("/").pop() ?? "").split(".").slice(1).join(".").toLowerCase();
const formatError = (ext: string) =>
  `Unsupported format: .${ext}. Supported: .csv, .json, .jsonl, .parquet`;

/** Binary thresholds; whole KB below 1 MB, one decimal above (812 KB, 1.1 GB). */
function formatBytes(n: number): string {
  if (!Number.isFinite(n) || n < 0) return "—";
  if (n < 1024) return `${n} B`;
  const kb = n / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(1)} GB`;
}

function tailOf(source: string): string {
  return (
    source
      .replace(/^file:\/\//, "")
      .replace(/\/$/, "")
      .split("/")
      .filter(Boolean)
      .pop() || source
  );
}


function timeAgo(iso: string): string {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 2592000) return `${Math.floor(s / 86400)}d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function DatasetPicker({
  value,
  datasets,
  datasetsLoading,
  sampleStatus,
  sampleError,
  userId,
  onSelect,
  onDatasetsLoaded,
  onRetrySample,
}: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("All");
  const [highlight, setHighlight] = useState(0);
  // Uploads are renamed to data/datasets/uploads/<uuid>.<ext> by save_upload,
  // so the API's `source` carries no original filename. The picker keeps the
  // names it learned this session; nothing persists across reload.
  const [localNames, setLocalNames] = useState<Record<string, string>>({});

  const [loadInput, setLoadInput] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [sourceBusy, setSourceBusy] = useState(false);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [addedLabel, setAddedLabel] = useState<string | null>(null);
  const [dropActive, setDropActive] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadingFile, setUploadingFile] = useState<File | null>(null);
  const [uploadCap, setUploadCap] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Server-side cap, used only for a pre-flight check; a failure here must not
  // block uploads, so the server error still surfaces (uploadCap stays null).
  useEffect(() => {
    let alive = true;
    api
      .datasetsConfig()
      .then((c) => {
        if (alive && typeof c?.max_upload_bytes === "number") setUploadCap(c.max_upload_bytes);
      })
      .catch(() => setUploadCap(null));
    return () => {
      alive = false;
    };
  }, []);

  const q = search.trim().toLowerCase();
  const filtered = datasets.filter((d) => {
    if (typeFilter !== "All" && TYPE_OF[d.source_type] !== typeFilter) return false;
    if (!q) return true;
    return (
      (localNames[d.id] ?? "").toLowerCase().includes(q) ||
      (d.name ?? "").toLowerCase().includes(q) ||
      d.source.toLowerCase().includes(q) ||
      d.columns.some((c) => c.name.toLowerCase().includes(q))
    );
  });

  useEffect(() => {
    setHighlight(0);
  }, [search, typeFilter, datasets]);

  // Datasets sharing the same `source` (e.g. repeated HF imports with name: null)
  // get " · #k" suffixes so adjacent rows are distinguishable. `source` is unique
  // per upload (uuid filename), so uploads never collide.
  const dupSuffix = useMemo(() => {
    const groups = new Map<string, string[]>();
    for (const d of datasets) groups.set(d.source, [...(groups.get(d.source) ?? []), d.id]);
    const suffix = new Map<string, string>();
    for (const ids of groups.values())
      if (ids.length > 1) ids.forEach((id, i) => suffix.set(id, ` · #${i + 1}`));
    return suffix;
  }, [datasets]);

  const labelOf = (d: DatasetMeta) =>
    (localNames[d.id] ?? d.name ?? tailOf(d.source)) + (dupSuffix.get(d.id) ?? "");
  const selected = value ? datasets.find((d) => d.id === value) : undefined;

  const pick = (id: string) => {
    setOpen(false);
    setAddedLabel(null);
    onSelect(id);
  };

  const openPanel = () => setOpen(true);

  // Focus once the panel has committed; a rAF callback can fire before
  // React flushes the conditional render, leaving the ref null.
  useEffect(() => {
    if (open) searchRef.current?.focus();
  }, [open]);

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setOpen(false);
      return;
    }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) {
        setHighlight(0);
        openPanel();
      } else {
        const n = filtered.length;
        setHighlight((prev) =>
          e.key === "ArrowDown" ? Math.min(prev + 1, n - 1) : Math.max(prev - 1, 0)
        );
      }
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      if (!open) {
        openPanel();
      } else if (filtered[highlight]) {
        pick(filtered[highlight].id);
      }
      return;
    }
    if (!open && e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      openPanel();
    }
  };

  // Shared success path for both load controls, so they cannot drift.
  const finishAdd = async (meta: { id: string; num_rows: number }, displayName: string) => {
    const res = await api.listDatasets();
    onDatasetsLoaded(res.datasets);
    setLocalNames((p) => ({ ...p, [meta.id]: displayName }));
    onSelect(meta.id);
    setAddedLabel(`Added ${displayName} · ${meta.num_rows.toLocaleString()} rows`);
    setLoadInput("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const submitSource = async (e: React.FormEvent) => {
    e.preventDefault();
    if (sourceBusy || uploadBusy || !loadInput.trim()) return;
    const s = loadInput.trim();
    // Mirror _detect_source's http branch: POST /datasets/load does not catch
    // ValueError, so a bad URL extension would surface as a bare 500.
    if (s.startsWith("http://") || s.startsWith("https://")) {
      const ext = extOf(s);
      if (!SUPPORTED.includes(ext)) {
        setLoadError(formatError(ext));
        return;
      }
    }
    setSourceBusy(true);
    setLoadError(null);
    try {
      const meta = await api.loadDataset(s, userId);
      await finishAdd(meta, meta.name ?? tailOf(meta.source));
      setUploadError(null);
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setSourceBusy(false);
    }
  };

  const uploadFile = async (file: File) => {
    const ext = extOf(file.name);
    if (!SUPPORTED.includes(ext)) {
      // Same string the server produces; the gate only avoids a wasted round-trip.
      setUploadError(formatError(ext));
      return;
    }
    if (uploadBusy || sourceBusy) return;
    // Same reason for the cap: skip the round-trip when the server would 413 us.
    if (uploadCap != null && file.size > uploadCap) {
      setUploadError(
        `File too large: ${formatBytes(file.size)} exceeds the ${formatBytes(uploadCap)} limit`
      );
      return;
    }
    const controller = new AbortController();
    abortRef.current = controller;
    setUploadBusy(true);
    setUploadingFile(file);
    setUploadProgress(0);
    setUploadError(null);
    try {
      const meta = await api.uploadDataset(file, userId, {
        onProgress: (sent, total) =>
          setUploadProgress(total > 0 ? Math.min(100, Math.round((sent / total) * 100)) : 0),
        signal: controller.signal,
      });
      await finishAdd(meta, file.name);
      setLoadError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 0 && err.message === "upload_cancelled") {
        setAddedLabel("Upload cancelled");
      } else {
        setUploadError(err instanceof ApiError ? err.message : String(err));
      }
    } finally {
      abortRef.current = null;
      setUploadBusy(false);
      setUploadingFile(null);
      setUploadProgress(0);
    }
  };

  return (
    <div>
      <div className="relative" ref={containerRef}>
        <button
          type="button"
          aria-haspopup="listbox"
          aria-expanded={open}
          onClick={openPanel}
          onKeyDown={handleKey}
          className={`w-full flex items-center justify-between gap-2 px-3 py-2 border rounded-lg text-sm bg-[var(--color-surface)] focus:outline-none ${
            open ? "border-sunset-400" : "border-[var(--color-border)]"
          }`}
        >
          {selected ? (
            <span className="truncate">
              {labelOf(selected)} · {selected.num_rows.toLocaleString()} rows ·{" "}
              {selected.columns.length} cols
            </span>
          ) : (
            <span className="text-[var(--color-text-muted)]">Select a dataset…</span>
          )}
          <span className={`transition-transform ${open ? "rotate-180" : ""}`}>▾</span>
        </button>

        {open && (
          <div
            id="dataset-listbox-root"
            className="absolute z-50 top-full mt-1 left-0 right-0 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-lg max-h-64 overflow-y-auto animate-fade-in"
          >
            <div className="p-2 pb-0">
              <div className="flex flex-wrap gap-1.5 mb-2">
                {ALL_TYPES.map((t) => (
                  <button
                    key={t}
                    type="button"
                    aria-pressed={typeFilter === t}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => setTypeFilter(t)}
                    className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                      typeFilter === t
                        ? "bg-sunset-50 text-sunset-600 font-medium"
                        : "bg-[var(--color-surface-sunken)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
              <div className="relative">
                <input
                  ref={searchRef}
                  role="combobox"
                  aria-controls="dataset-listbox"
                  aria-expanded={open}
                  aria-activedescendant={
                    filtered[highlight] ? `ds-option-${filtered[highlight].id}` : undefined
                  }
                  aria-label="Filter datasets"
                  placeholder="Filter by name, source, or column…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  onKeyDown={handleKey}
                  className={`w-full border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400 py-2 pl-3 ${
                    search ? "pr-8" : "pr-3"
                  }`}
                />
                {search && (
                  <button
                    type="button"
                    aria-label="Clear search"
                    title="Clear search"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => setSearch("")}
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center rounded text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-sunken)] transition-colors"
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>

            {/* Status area: mutually exclusive, loading > empty > no-match > count header */}
            {datasetsLoading ? (
              <div className="px-3 py-2">
                <SkeletonBar className="h-12 w-full mb-2" />
                <SkeletonBar className="h-12 w-full mb-2" />
                <SkeletonBar className="h-12 w-full mb-2" />
              </div>
            ) : datasets.length === 0 ? (
              <div className="px-3 py-4 text-sm text-[var(--color-text-muted)]">
                No datasets yet — load one below.
              </div>
            ) : filtered.length === 0 ? (
              <div className="px-3 py-4 text-sm text-[var(--color-text-muted)]">
                No datasets match “{search.trim()}”{" "}
                <button
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    setSearch("");
                    setTypeFilter("All");
                  }}
                  className="text-sm text-sunset-600 hover:underline"
                >
                  Clear filter
                </button>
              </div>
            ) : (
              <div className="px-3 pt-2 text-[11px] text-[var(--color-text-muted)] uppercase tracking-wider">
                {filtered.length} of {datasets.length}
              </div>
            )}

            <ul id="dataset-listbox" role="listbox" aria-label="Datasets">
              {filtered.map((d, i) => (
                <li
                  key={d.id}
                  role="option"
                  id={`ds-option-${d.id}`}
                  aria-selected={d.id === value}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    pick(d.id);
                  }}
                  onMouseEnter={() => setHighlight(i)}
                  className={`px-3 py-2 cursor-pointer transition-colors ${
                    d.id === value
                      ? "bg-sunset-50 border-l-2 border-sunset-500"
                      : i === highlight
                        ? "bg-[var(--color-surface-sunken)]"
                        : ""
                  } ${d.cache_available ? "" : "opacity-60"}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-[var(--color-text)] truncate">
                        {labelOf(d)}
                      </div>
                      <div className="text-xs text-[var(--color-text-muted)] truncate">
                        {d.source_type === "huggingface"
                          ? `${d.split ?? "train"} · ${timeAgo(d.created_at)}`
                          : `${d.source} · ${timeAgo(d.created_at)}`}
                      </div>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {d.columns.slice(0, 6).map((c) => (
                          <span
                            key={c.name}
                            className="px-1.5 py-0.5 rounded bg-[var(--color-surface-sunken)] text-[11px] font-mono text-[var(--color-text-muted)]"
                          >
                            {c.name}
                          </span>
                        ))}
                        {d.columns.length > 6 && (
                          <span className="px-1.5 py-0.5 rounded bg-[var(--color-surface-sunken)] text-[11px] font-mono text-[var(--color-text-muted)]">
                            +{d.columns.length - 6}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1 shrink-0">
                      <span className="px-1.5 py-0.5 rounded bg-[var(--color-surface-sunken)] font-medium text-[11px] text-[var(--color-text-muted)]">
                        {TYPE_BADGE[d.source_type]}
                      </span>
                      <span className="text-[11px] text-[var(--color-text-muted)]">
                        {d.num_rows.toLocaleString()} rows
                      </span>
                      <span className="text-[11px] text-[var(--color-text-muted)]">
                        {d.columns.length} cols
                      </span>
                      {!d.cache_available && (
                        <span className="text-[11px] text-amber-600">not cached</span>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {selected && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5 text-sm text-[var(--color-text-muted)]">
          <span className="text-xs font-semibold uppercase tracking-wider">Columns:</span>
          {selected.columns.slice(0, 6).map((c) => (
            <span
              key={c.name}
              className="px-1.5 py-0.5 rounded bg-[var(--color-surface-sunken)] text-[11px] font-mono text-[var(--color-text-muted)]"
            >
              {c.name}
            </span>
          ))}
          {selected.columns.length > 6 && (
            <span className="px-1.5 py-0.5 rounded bg-[var(--color-surface-sunken)] text-[11px] font-mono text-[var(--color-text-muted)]">
              +{selected.columns.length - 6}
            </span>
          )}
          <span>
            · {selected.num_rows.toLocaleString()} rows · added {timeAgo(selected.created_at)}
          </span>
        </div>
      )}

      {sampleStatus === "loading" && (
        <div className="mt-2 flex items-center gap-2 text-sm text-[var(--color-text-muted)]">
          <span>Loading sample row…</span>
          <SkeletonBar className="h-3 w-40" />
        </div>
      )}
      {sampleStatus === "error" && (
        <div className="mt-2 flex items-center gap-2">
          <p className="text-sm text-red-500">{sampleError}</p>
          <button
            type="button"
            onClick={onRetrySample}
            className="text-sm text-sunset-600 hover:underline"
          >
            Retry
          </button>
        </div>
      )}
      {sampleStatus === "ready" && selected && selected.cache_available === false && (
        <p className="mt-2 text-sm text-amber-600">
          Not cached locally — the first row load re-downloads from the source.
        </p>
      )}

      <hr className="my-4 border-[var(--color-border)]" />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <form onSubmit={submitSource}>
          <div className="flex gap-2">
            <input
              value={loadInput}
              onChange={(e) => setLoadInput(e.target.value)}
              placeholder="HF dataset ID, https://… URL, or file:// path"
              className="flex-1 px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-sunset-400"
            />
            <button
              type="submit"
              disabled={sourceBusy || uploadBusy || !loadInput.trim()}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-sunset-500 to-coral-500 text-white text-sm font-medium hover:from-sunset-600 hover:to-coral-600 disabled:opacity-50 transition-all whitespace-nowrap"
            >
              {sourceBusy ? "Loading…" : "Load"}
            </button>
          </div>
          {loadError && <p className="text-sm text-red-500 mt-2">{loadError}</p>}
        </form>

        <div>
          <label
            onDragOver={(e) => {
              e.preventDefault();
              setDropActive(true);
            }}
            onDragLeave={() => setDropActive(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDropActive(false);
              const f = e.dataTransfer.files?.[0];
              if (f) uploadFile(f);
            }}
            className={`flex items-center justify-center gap-2 px-4 py-3 rounded-lg border border-dashed bg-[var(--color-surface-secondary)] text-sm text-[var(--color-text-muted)] cursor-pointer hover:bg-[var(--color-surface-sunken)] transition-all ${
              dropActive ? "border-sunset-400 bg-sunset-50" : "border-[var(--color-border)]"
            } ${uploadBusy ? "pointer-events-none" : ""}`}
          >
            {uploadBusy && uploadingFile ? (
              <span className="flex w-full items-center gap-3">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[var(--color-text)]">
                    {uploadingFile.name} · {formatBytes(uploadingFile.size)}
                  </span>
                  <span className="mt-1.5 block h-1.5 w-full rounded-full bg-[var(--color-surface-sunken)]">
                    <span
                      className="block h-1.5 rounded-full bg-gradient-to-r from-sunset-500 to-coral-500 transition-all"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </span>
                </span>
                <span className="shrink-0 tabular-nums">{uploadProgress}%</span>
                <button
                  type="button"
                  onClick={() => abortRef.current?.abort()}
                  className="shrink-0 px-2 py-1 rounded-lg border border-[var(--color-border)] text-xs hover:bg-[var(--color-surface-sunken)] transition-colors"
                >
                  Cancel
                </button>
              </span>
            ) : (
              <span>⬆ Drop .csv, .json, .jsonl or .parquet — or browse</span>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.json,.jsonl,.parquet"
              disabled={uploadBusy}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) uploadFile(f);
              }}
              className="hidden"
            />
          </label>
          {!uploadBusy && (
            <p className="text-[11px] text-[var(--color-text-muted)] mt-2">
              Drop .csv, .json, .jsonl or .parquet — or browse
              {uploadCap != null ? ` max ${formatBytes(uploadCap)}` : ""}
            </p>
          )}
          {uploadError && <p className="text-sm text-red-500 mt-2">{uploadError}</p>}
        </div>
      </div>

      {addedLabel && <p className="text-sm text-green-600 mt-2">{addedLabel}</p>}
    </div>
  );
}
