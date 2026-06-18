const DEFAULT_API_BASE = "http://localhost:8000/api";
const STORAGE_KEY = "p4web.client.apiBase";

export class ApiError extends Error {
  constructor(message, status, details) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

export function getApiBase() {
  return localStorage.getItem(STORAGE_KEY) || DEFAULT_API_BASE;
}

export function setApiBase(value) {
  const clean = value.trim().replace(/\/$/, "");
  localStorage.setItem(STORAGE_KEY, clean || DEFAULT_API_BASE);
}

export async function request(path, options = {}) {
  const base = getApiBase();
  const response = await fetch(`${base}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const message = data?.detail || response.statusText || "API request failed";
    throw new ApiError(message, response.status, data);
  }
  return data;
}

export const api = {
  health: () => request("/health"),

  listProjects: () => request("/projects"),
  createProject: (payload) =>
    request("/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  copyProject: (projectId, payload) =>
    request(`/projects/${projectId}/copy`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteProject: (projectId) => request(`/projects/${projectId}`, { method: "DELETE" }),
  importLocal: (payload) =>
    request("/sync/import-local", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getProject: (projectId) => request(`/projects/${projectId}`),

  listVersions: (projectId) => request(`/projects/${projectId}/versions`),
  createVersion: (projectId, payload) =>
    request(`/projects/${projectId}/versions`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getVersion: (versionId) => request(`/versions/${versionId}`),
  listVersionFiles: (versionId) => request(`/versions/${versionId}/files`),

  createJob: (payload) =>
    request("/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getJob: (jobId) => request(`/jobs/${jobId}`),
  getJobLogs: (jobId, cursor = null) => {
    const query = cursor === null || cursor === undefined ? "" : `?cursor=${cursor}`;
    return request(`/jobs/${jobId}/logs${query}`);
  },
  cancelJob: (jobId) => request(`/jobs/${jobId}/cancel`, { method: "POST" }),

  listProjectArtifacts: (projectId) => request(`/projects/${projectId}/artifacts`),
  listVersionArtifacts: (versionId) => request(`/versions/${versionId}/artifacts`),

  submitVersion: (versionId, comment = "") =>
    request(`/versions/${versionId}/submit`, {
      method: "POST",
      body: JSON.stringify({ comment }),
    }),
  approveVersion: (versionId, comment = "") =>
    request(`/versions/${versionId}/approve`, {
      method: "POST",
      body: JSON.stringify({ comment }),
    }),
  rejectVersion: (versionId, comment = "") =>
    request(`/versions/${versionId}/reject`, {
      method: "POST",
      body: JSON.stringify({ comment }),
    }),
};
