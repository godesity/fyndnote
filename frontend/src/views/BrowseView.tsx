import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import BreadcrumbNav from '../components/BreadcrumbNav';
import { SkeletonBar } from '../components/SkeletonLoader';
import RowGrid from '../components/RowGrid';
import RowDetail from '../components/RowDetail';
import FilterBar from '../components/FilterBar';

interface Props {
  projectId: string;
}

export default function BrowseView({ projectId }: Props) {
  const { user } = useAuth();
  const [projectColor, setProjectColor] = useState('#F97316');
  const [projectName, setProjectName] = useState('');
  const [rows, setRows] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [selectedRow, setSelectedRow] = useState<any>(null);
  const [filter, setFilter] = useState<any[]>([]);
  const [datasetColumns, setDatasetColumns] = useState<{ name: string; type: string }[]>([]);
  const [annotationFields, setAnnotationFields] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [mlEnabled, setMlEnabled] = useState(false);
  const [mlMode, setMlMode] = useState('');
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchResult, setBatchResult] = useState<{ total: number; succeeded: number; failed: number } | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);
  const [datasetDetails, setDatasetDetails] = useState<any | null>(null);

  useEffect(() => {
    if (!user) return;
    api.getProject(projectId, user.user_id).then((p) => {
      setProjectColor(p.color || '#F97316');
      setProjectName(p.name || '');
      setAnnotationFields(p.annotation_fields || []);
      setMlEnabled(!!p.ml_enabled);
      setMlMode(p.ml_mode || '');
      api.listDatasets().then((res) => {
        const ds = res.datasets.find((d: any) => d.id === p.dataset_id);
        if (ds) setDatasetColumns(ds.columns || []);
      });
      api.getDatasetDetails(p.dataset_id).then(setDatasetDetails).catch(() => {});
    });
  }, [projectId, user]);

  const loadRows = () => {
    if (!user) return;
    setLoading(true);
    api.browseRows(projectId, user.user_id, page, filter).then((res) => {
      setRows(res.rows);
      setTotal(res.total);
      setLoading(false);
    });
  };

  useEffect(() => {
    loadRows();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, page, filter]);

  const handleSelect = async (idx: number) => {
    setSelectedIndex(idx);
    setRowError(null);
    if (!user) return;
    try {
      const project = await api.getProject(projectId, user.user_id);
      const rowData = await api.getRow(project.dataset_id, idx);
      setSelectedRow(rowData.row);
    } catch {
      setRowError("Failed to load row — dataset source may no longer be available");
      setSelectedRow(null);
    }
  };

  const handleBatchPrefill = async () => {
    if (!user) return;
    setBatchRunning(true);
    setBatchResult(null);
    try {
      const result = await api.mlBatch(projectId);
      setBatchResult(result);
      // Refresh rows
      const res = await api.browseRows(projectId, user.user_id, page, filter);
      setRows(res.rows);
      setTotal(res.total);
    } catch {
      setBatchResult({ total: 0, succeeded: 0, failed: 0 });
    }
    setBatchRunning(false);
  };

  const showBatchButton = mlEnabled && (mlMode === 'batch' || mlMode === 'both');

  return (
    <div className="min-h-screen bg-[var(--color-surface-secondary)]">
      <BreadcrumbNav crumbs={[
        { label: 'Projects', href: '#/projects' },
        { label: projectName },
      ]} />

      <div className="h-1" style={{ background: projectColor }} />

      <div className="max-w-5xl mx-auto px-6 py-6 animate-fade-in">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-[var(--color-text-heading)]">Browse Data</h2>
            {showBatchButton && (
              <button
                onClick={handleBatchPrefill}
                disabled={batchRunning}
                className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-violet-500 to-purple-500 text-white text-xs font-medium hover:from-violet-600 hover:to-purple-600 disabled:opacity-50 transition-all shadow-sm"
              >
                {batchRunning ? 'Prefilling...' : 'AI Prefill'}
              </button>
            )}
          </div>
          <div className="w-full max-w-xl ml-8">
            <FilterBar
              datasetColumns={datasetColumns}
              annotationFields={annotationFields}
              onFilterChange={(f) => { setFilter(f); setPage(1); }}
            />
          </div>
        </div>

        {datasetDetails && (
          <DatasetDetailsSection details={datasetDetails} />
        )}

        {batchResult && !batchRunning && (
          <div className={`mb-4 px-4 py-2 rounded-lg text-sm border ${
            batchResult.failed > 0
              ? 'bg-amber-50 text-amber-800 border-amber-200'
              : 'bg-emerald-50 text-emerald-800 border-emerald-200'
          }`}>
            Prefilled {batchResult.succeeded}/{batchResult.total} rows{batchResult.failed > 0 ? ` (${batchResult.failed} failed)` : ''}
          </div>
        )}

        {loading ? (
          <div className="space-y-3">
            {[1,2,3].map(i => (
              <div key={i} className="bg-white rounded-xl border border-[var(--color-border)] p-4">
                <SkeletonBar className="h-4 w-3/4 mb-2" />
                <SkeletonBar className="h-3 w-1/2" />
              </div>
            ))}
          </div>
        ) : (
          <RowGrid rows={rows} onSelect={handleSelect} page={page} total={total} onPageChange={setPage} color={projectColor} />
        )}

        {selectedIndex !== null && selectedRow && user && (
          <RowDetail
            index={selectedIndex}
            row={selectedRow}
            annotations={rows.find((r) => r.index === selectedIndex)?.annotations}
            projectId={projectId}
            userId={user.user_id}
            onClose={() => { setSelectedIndex(null); setRowError(null); }}
            onRefresh={loadRows}
          />
        )}
        {rowError && (
          <div className="mt-4 px-4 py-3 rounded-lg text-sm bg-red-50 text-red-700 border border-red-200">
            {rowError}
          </div>
        )}
      </div>
    </div>
  );
}

function DatasetDetailsSection({ details }: { details: any }) {
  const d = details.dataset;
  const projects = details.projects;
  return (
    <details className="mb-4 group">
      <summary className="text-sm font-medium text-[var(--color-text-muted)] cursor-pointer hover:text-[var(--color-text)] select-none">
        Dataset: {d.name || d.source} · {d.num_rows.toLocaleString()} rows · {projects.length} {projects.length === 1 ? "project" : "projects"}
      </summary>
      <div className="mt-3 bg-white rounded-xl border border-[var(--color-border)] p-4 shadow-sm space-y-3">
        <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
          <span className="text-[var(--color-text-muted)]">Source</span>
          <span className="text-[var(--color-text)] break-all">{d.source}</span>
          <span className="text-[var(--color-text-muted)]">Split</span>
          <span className="text-[var(--color-text)]">{d.split || '—'}</span>
          <span className="text-[var(--color-text-muted)]">Rows</span>
          <span className="text-[var(--color-text)]">{d.num_rows.toLocaleString()}</span>
          <span className="text-[var(--color-text-muted)]">Added</span>
          <span className="text-[var(--color-text)]">{new Date(d.created_at).toLocaleDateString()}</span>
        </div>
        <div>
          <h4 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-2">Projects using this dataset</h4>
          {projects.map((proj: any) => (
            <div key={proj.id} className="flex items-center gap-2 text-sm py-1">
              <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: proj.color }} />
              <span className="font-medium text-[var(--color-text)]">{proj.name}</span>
              <span className="text-[var(--color-text-muted)]">
                {proj.annotated_rows} rows annotated · {proj.annotations} annotations · {proj.predictions} predictions
              </span>
            </div>
          ))}
        </div>
        <p className="text-sm text-[var(--color-text-muted)] border-t border-[var(--color-border)] pt-2">
          Totals: {details.totals.annotations} annotations · {details.totals.predictions} predictions
        </p>
      </div>
    </details>
  );
}
