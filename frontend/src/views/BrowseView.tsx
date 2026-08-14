import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import RowGrid from '../components/RowGrid';
import RowDetail from '../components/RowDetail';

interface Props {
  projectId: string;
  onBack: () => void;
}

export default function BrowseView({ projectId, onBack }: Props) {
  const { user } = useAuth();
  const [rows, setRows] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [selectedRow, setSelectedRow] = useState<any>(null);
  const [statusFilter, setStatusFilter] = useState('all');

  useEffect(() => {
    if (!user) return;
    api.browseRows(projectId, user.user_id, page, statusFilter, 1).then((res) => {
      setRows(res.rows);
      setTotal(res.total);
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
    <div style={{ padding: 20 }}>
      <button onClick={onBack} style={{ marginBottom: 16 }}>&larr; Back</button>
      <h2>Browse Data</h2>

      <div style={{ marginBottom: 16 }}>
        <label>Status: </label>
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
          <option value="all">All</option>
          <option value="annotated_by_me">Annotated by me</option>
          <option value="unannotated">Unannotated</option>
        </select>
      </div>

      <RowGrid rows={rows} onSelect={handleSelect} page={page} total={total} onPageChange={setPage} />

      {selectedIndex !== null && selectedRow && (
        <RowDetail
          index={selectedIndex}
          row={selectedRow}
          annotations={rows.find((r) => r.index === selectedIndex)?.annotations}
          onClose={() => setSelectedIndex(null)}
        />
      )}
    </div>
  );
}
