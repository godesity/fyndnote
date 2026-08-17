import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import BreadcrumbNav from '../components/BreadcrumbNav';
import { SkeletonBar } from '../components/SkeletonLoader';
import RowGrid from '../components/RowGrid';
import RowDetail from '../components/RowDetail';

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
  const [statusFilter, setStatusFilter] = useState('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    api.getProject(projectId, user.user_id).then((p) => {
      setProjectColor(p.color || '#F97316');
      setProjectName(p.name || '');
    });
  }, [projectId, user]);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    api.browseRows(projectId, user.user_id, page, statusFilter, 1).then((res) => {
      setRows(res.rows);
      setTotal(res.total);
      setLoading(false);
    });
  }, [projectId, page, statusFilter]);

  const handleSelect = async (idx: number) => {
    setSelectedIndex(idx);
    if (!user) return;
    const project = await api.getProject(projectId, user.user_id);
    const rowData = await api.getRow(project.dataset_id, idx);
    setSelectedRow(rowData.row);
  };

  return (
    <div className="min-h-screen bg-[var(--color-surface-secondary)]">
      <BreadcrumbNav crumbs={[
        { label: 'Projects', href: '#/projects' },
        { label: projectName },
      ]} />

      <div className="h-1" style={{ background: projectColor }} />

      <div className="max-w-5xl mx-auto px-6 py-6 animate-fade-in">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-[var(--color-text-heading)]">Browse Data</h2>
          <div className="flex items-center gap-2">
            <label className="text-sm text-[var(--color-text-muted)]">Status:</label>
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
              className="px-3 py-1.5 border border-[var(--color-border)] rounded-lg text-sm bg-white focus:outline-none focus:border-sunset-400"
            >
              <option value="all">All</option>
              <option value="annotated_by_me">Annotated by me</option>
              <option value="unannotated">Unannotated</option>
            </select>
          </div>
        </div>

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
          <RowGrid rows={rows} onSelect={handleSelect} page={page} total={total} onPageChange={setPage} />
        )}

        {selectedIndex !== null && selectedRow && (
          <RowDetail
            index={selectedIndex}
            row={selectedRow}
            annotations={rows.find((r) => r.index === selectedIndex)?.annotations}
            onClose={() => setSelectedIndex(null)}
          />
        )}
      </div>
    </div>
  );
}
