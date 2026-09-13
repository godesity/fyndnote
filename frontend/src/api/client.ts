const BASE = '/api/v1';

export const apiBase = BASE;

export interface User {
  user_id: string;
  name: string;
  global_role: string;
  project_roles: Record<string, string> | null;
  sso_roles?: string[];
}

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
    // Session cookie must be sent for the SSO callback (state / CSRF check).
    credentials: 'include',
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail || res.statusText);
  }
  return res.json();
}

export interface DspyField {
  name: string;
  source: string;
  kind?: string;
  desc: string;
  options?: string[];
  max?: number | null;
  enabled?: boolean;
}

export interface DspyConfig {
  version: number;
  instruction: string;
  input_fields: DspyField[];
  output_fields: DspyField[];
  program_state: unknown;
  tuned_at: string | null;
  train_metrics: Record<string, unknown> | null;
  n_demos: number;
  derived_from: string;
  model: string;
  api_base: string;
  annotator: string;
  ml_enabled: boolean;
  ml_mode: string;
  ml_type: string;
  llm_key_set: boolean;
  unsupported: string[];
}

export interface DspyUpdateBody {
  instruction?: string;
  model?: string;
  api_base?: string;
  input_fields?: DspyField[];
  output_fields?: DspyField[];
}

export interface DspyTestResult {
  inputs: Record<string, string>;
  fields: { name: string; desc: string; kind: string; value: unknown }[];
  annotation: Record<string, unknown>;
  instruction: string;
  tuned: boolean;
}

export interface DspyTrainResult {
  status: string;
  score: number;
  n_demos: number;
  instruction: string;
  optimizer: string;
  train_size: number;
  val_size: number;
}

export const api = {
  base: BASE,
  login: (userId: string) =>
    request<{ user_id: string; name: string; global_role: string; project_roles: Record<string, string> | null }>(
      '/auth/login', { method: 'POST', body: JSON.stringify({ user_id: userId }) }
    ),
  authConfig: () => request<{ sso_enabled: boolean }>('/auth/config'),
  me: (token: string) =>
    request<{ user: User }>('/sso/me', { headers: { Authorization: `Bearer ${token}` } }),
  ssoCallback: (code: string, state: string) =>
    request<{ token: string; refresh_token?: string; id_token?: string; user: User }>(
      `/sso/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`),
  ssoLogin: () =>
    fetch(`${BASE}/sso/login`, { credentials: 'include' }).then((r) => {
      if (!r.ok) throw new ApiError(r.status, 'sso_not_enabled');
      return r;
    }),
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
  getDatasetDetails: (dsId: string) =>
    request<any>(`/datasets/${dsId}/details`),
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
    mlEnabled?: boolean, mlUrl?: string, mlAnnotator?: string, mlMode?: string, userId?: string,
    mlType?: string, dspyModel?: string, dspyApiBase?: string) =>
    request<any>('/projects', { method: 'POST', body: JSON.stringify({ name, dataset_id: datasetId, template_id: templateId, color, tags, instructions, ml_enabled: mlEnabled, ml_url: mlUrl, ml_annotator: mlAnnotator, ml_mode: mlMode, user_id: userId, ml_type: mlType, dspy_model: dspyModel, dspy_api_base: dspyApiBase }) }),
  getProject: (id: string, userId: string) =>
    request<any>(`/projects/${id}?user_id=${userId}`),
  updateProject: (id: string, name: string, color?: string, tags?: string, instructions?: string,
    mlEnabled?: boolean, mlUrl?: string, mlAnnotator?: string, mlMode?: string,
    mlType?: string, dspyModel?: string, dspyApiBase?: string) =>
    request<any>(`/projects/${id}`, { method: 'PUT', body: JSON.stringify({ name, color, tags, instructions, ml_enabled: mlEnabled, ml_url: mlUrl, ml_annotator: mlAnnotator, ml_mode: mlMode, ml_type: mlType, dspy_model: dspyModel, dspy_api_base: dspyApiBase }) }),
  deleteProject: (id: string) =>
    request<any>(`/projects/${id}`, { method: 'DELETE' }),
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
  dspyConfig: (pid: string) =>
    request<DspyConfig>(`/projects/${pid}/dspy`),
  dspyUpdate: (pid: string, body: DspyUpdateBody) =>
    request<DspyConfig>(`/projects/${pid}/dspy`, { method: 'PUT', body: JSON.stringify(body) }),
  dspyDerive: (pid: string) =>
    request<DspyConfig>(`/projects/${pid}/dspy/derive`, { method: 'POST', body: '{}' }),
  dspyTest: (pid: string, rowIndex: number) =>
    request<DspyTestResult>(`/projects/${pid}/dspy/test`, { method: 'POST', body: JSON.stringify({ row_index: rowIndex }) }),
  dspyTrain: (pid: string, optimizer: string, maxExamples: number) =>
    request<DspyTrainResult>(`/projects/${pid}/dspy/train`, { method: 'POST', body: JSON.stringify({ optimizer, max_examples: maxExamples }) }),
  dspyReset: (pid: string) =>
    request<DspyConfig>(`/projects/${pid}/dspy/reset`, { method: 'POST', body: '{}' }),
  getMLAnnotation: (projectId: string, rowIndex: number) =>
    request<{ row_index: number; annotator: string; data: Record<string, any>; created_at: string }>(
      `/projects/${projectId}/ml-annotations/${rowIndex}`),
  deleteAnnotation: (pid: string, rowIndex: number, userId?: string) =>
    request(`/projects/${pid}/annotations/${rowIndex}${userId ? `?user_id=${userId}` : ''}`, { method: 'DELETE' }),
  deleteAllAnnotations: (pid: string) =>
    request(`/projects/${pid}/annotations`, { method: 'DELETE' }),
  deleteMLAnnotation: (pid: string, rowIndex: number) =>
    request(`/projects/${pid}/ml-annotations/${rowIndex}`, { method: 'DELETE' }),
  deleteAllMLAnnotations: (pid: string) =>
    request(`/projects/${pid}/ml-annotations`, { method: 'DELETE' }),
  bulkClearAnnotations: (pid: string, userId: string, filter: any[] = []) =>
    request(`/projects/${pid}/annotations/bulk?user_id=${userId}`, {
      method: 'DELETE',
      body: JSON.stringify({ filter }),
    }),
  bulkClearMLAnnotations: (pid: string, userId: string, filter: any[] = []) =>
    request(`/projects/${pid}/ml-annotations/bulk?user_id=${userId}`, {
      method: 'DELETE',
      body: JSON.stringify({ filter }),
    }),
  importRows: (pid: string, rows: any[]) =>
    request<any>(`/projects/${pid}/rows/bulk`, { method: 'POST', body: JSON.stringify({ rows }) }),
};
