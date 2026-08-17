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

  useEffect(() => {
    if (!user) return;
    api.getProject(projectId, user.user_id).then((p) => {
      setProjectColor(p.color || '#F97316');
      setProjectName(p.name || '');
      setAnnotationFields(p.annotation_fields || []);
      api.listDatasets().then((res) => {
        const ds = res.datasets.find((d: any) => d.id === p.dataset_id);
        if (ds) setDatasetColumns(ds.columns || []);
      });
    });
  }, [projectId, user]);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    api.browseRows(projectId, user.user_id, page, filter).then((res) => {
      setRows(res.rows);
      setTotal(res.total);
      setLoading(false);
    });
  }, [projectId, page, filter]);

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
          <div className="w-full max-w-xl ml-8">
            <FilterBar
              datasetColumns={datasetColumns}
              annotationFields={annotationFields}
              onFilterChange={(f) => { setFilter(f); setPage(1); }}
            />
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
          <RowGrid rows={rows} onSelect={handleSelect} page={page} total={total} onPageChange={setPage} color={projectColor} />
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
