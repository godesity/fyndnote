const BASE = 'http://localhost:8000/api/v1';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  login: (userId: string) =>
    request<{ user_id: string; name: string; global_role: string; project_roles: Record<string, string> | null }>(
      '/auth/login', { method: 'POST', body: JSON.stringify({ user_id: userId }) }
    ),
  listDatasets: () =>
    request<{ datasets: any[] }>('/datasets'),
  uploadDataset: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return fetch(`${BASE}/datasets/upload`, {
      method: 'POST',
      body: formData,
    }).then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new ApiError(res.status, body.detail || res.statusText);
      }
      return res.json();
    });
  },
  loadDataset: (source: string, split = 'train') =>
    request<any>('/datasets/load', { method: 'POST', body: JSON.stringify({ source, split }) }),
  getRow: (dsId: string, index: number) =>
    request<{ index: number; row: Record<string, any> }>(`/datasets/${dsId}/rows/${index}`),
  listTemplates: () =>
    request<{ templates: any[] }>('/templates'),
  getTemplate: (id: string) =>
    request<any>(`/templates/${id}`),
  createTemplate: (name: string, source: string) =>
    request<any>('/templates', { method: 'POST', body: JSON.stringify({ name, source }) }),
  updateTemplate: (id: string, source: string, validated?: boolean) =>
    request<any>(`/templates/${id}`, { method: 'PUT', body: JSON.stringify({ source, validated }) }),
  listProjects: (userId: string) =>
    request<{ projects: any[] }>(`/projects?user_id=${userId}`),
  createProject: (name: string, datasetId: string, templateId: string, color?: string, tags?: string, instructions?: string,
    mlEnabled?: boolean, mlUrl?: string, mlAnnotator?: string, mlMode?: string) =>
    request<any>('/projects', { method: 'POST', body: JSON.stringify({ name, dataset_id: datasetId, template_id: templateId, color, tags, instructions, ml_enabled: mlEnabled, ml_url: mlUrl, ml_annotator: mlAnnotator, ml_mode: mlMode }) }),
  getProject: (id: string, userId: string) =>
    request<any>(`/projects/${id}?user_id=${userId}`),
  updateProject: (id: string, name: string, color?: string, tags?: string, instructions?: string,
    mlEnabled?: boolean, mlUrl?: string, mlAnnotator?: string, mlMode?: string) =>
    request<any>(`/projects/${id}`, { method: 'PUT', body: JSON.stringify({ name, color, tags, instructions, ml_enabled: mlEnabled, ml_url: mlUrl, ml_annotator: mlAnnotator, ml_mode: mlMode }) }),
  nextRow: (projectId: string, userId: string) =>
    request<{ index: number | null; row: Record<string, any> | null }>(`/projects/${projectId}/next-row?user_id=${userId}`),
  getProjectRow: (projectId: string, rowIndex: number, userId: string) =>
    request<{ index: number; row: Record<string, any>; annotation_status: { by_me: boolean; by_any: boolean; annotators: string[] } }>(
      `/projects/${projectId}/rows/${rowIndex}?user_id=${userId}`),
  navigateRow: (projectId: string, rowIndex: number, userId: string, direction: 1 | -1) =>
    request<{ index: number; row: Record<string, any>; annotation_status: { by_me: boolean; by_any: boolean; annotators: string[] } }>(
      `/projects/${projectId}/rows/${rowIndex}/${direction === 1 ? 'next' : 'prev'}?user_id=${userId}`),
  submitAnnotation: (projectId: string, rowIndex: number, userId: string, data: any) =>
    request<any>(`/projects/${projectId}/annotate`, {
      method: 'POST',
      body: JSON.stringify({ row_index: rowIndex, user_id: userId, data }),
    }),
  getAnnotation: (projectId: string, rowIndex: number, userId: string) =>
    request<any>(`/projects/${projectId}/annotations/${rowIndex}?user_id=${userId}`),
  browseRows: (projectId: string, userId: string, page = 1, filter: any[] = []) =>
    request<any>(`/projects/${projectId}/rows`, {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, page, filter }),
    }),
  mlPrefill: (projectId: string, rowIndex: number) =>
    request<{ row_index: number; annotation: Record<string, any> | null; annotator: string | null }>(
      `/projects/${projectId}/ml-prefill`, { method: 'POST', body: JSON.stringify({ row_index: rowIndex }) }),
  mlBatch: (projectId: string, rowIndices?: number[]) =>
    request<{ total: number; succeeded: number; failed: number }>(
      `/projects/${projectId}/ml-batch`, { method: 'POST', body: JSON.stringify({ row_indices: rowIndices ?? null }) }),
  getMLAnnotation: (projectId: string, rowIndex: number) =>
    request<{ row_index: number; annotator: string; data: Record<string, any>; created_at: string }>(
      `/projects/${projectId}/ml-annotations/${rowIndex}`),
};
