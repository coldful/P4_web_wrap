const LOCAL_API_BASE = "http://localhost:8000/api";
const STORAGE_KEY = "p4web.client.apiBase";

export class ApiError extends Error {
  constructor(message, status, details) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

function isLocalHostName(hostname) {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "[::1]";
}

function isLocalApiBase(value) {
  try {
    const url = new URL(value);
    return isLocalHostName(url.hostname);
  } catch {
    return value.includes("localhost") || value.includes("127.0.0.1");
  }
}

function detectDefaultApiBase() {
  if (typeof window !== "undefined" && window.location?.origin) {
    const { hostname, origin } = window.location;
    if (!isLocalHostName(hostname)) {
      return `${origin}/api`;
    }
  }
  return LOCAL_API_BASE;
}

function resolveApiBase() {
  const stored = localStorage.getItem(STORAGE_KEY);
  const detected = detectDefaultApiBase();
  if (!stored) {
    return detected;
  }
  if (typeof window !== "undefined" && isLocalApiBase(stored) && !isLocalHostName(window.location.hostname)) {
    return detected;
  }
  return stored;
}

export function getApiBase() {
  return resolveApiBase();
}

export function setApiBase(value) {
  const clean = value.trim().replace(/\/$/, "");
  localStorage.setItem(STORAGE_KEY, clean || detectDefaultApiBase());
}

export function buildApiUrl(path) {
  return `${getApiBase()}${path}`;
}

function parseResponseBody(text) {
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

function networkErrorMessage(error) {
  const apiBase = getApiBase();
  if (error?.name === "TypeError" || String(error?.message || "").includes("NetworkError")) {
    return `Cannot reach API at ${apiBase}. Check the API URL, nginx client_max_body_size, and CORS settings.`;
  }
  return error?.message || "Network request failed";
}

async function performFetch(path, options = {}) {
  try {
    return await fetch(buildApiUrl(path), options);
  } catch (error) {
    throw new ApiError(networkErrorMessage(error), 0, null);
  }
}

export async function request(path, options = {}) {
  const response = await performFetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const text = await response.text();
  const data = parseResponseBody(text);
  if (!response.ok) {
    const message = data?.detail || response.statusText || "API request failed";
    throw new ApiError(message, response.status, data);
  }
  return data;
}

export async function requestForm(path, body, options = {}) {
  const response = await performFetch(path, {
    ...options,
    method: options.method || "POST",
    body,
  });

  const text = await response.text();
  const data = parseResponseBody(text);
  if (!response.ok) {
    let message = data?.detail || response.statusText || "API request failed";
    if (response.status === 413) {
      message = "Upload too large for the server (nginx client_max_body_size).";
    }
    throw new ApiError(message, response.status, data);
  }
  return data;
}

async function rawRequest(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    throw new ApiError(networkErrorMessage(error), 0, null);
  }
  if (!response.ok) {
    const text = await response.text();
    const data = parseResponseBody(text);
    const message = data?.detail || response.statusText || "API request failed";
    throw new ApiError(message, response.status, data);
  }
  return response;
}

async function downloadFromUrl(url, filename) {
  const response = await rawRequest(url);
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename || "download";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
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
  importUpload: (formData) =>
    requestForm("/sync/import-upload", formData, {
      method: "POST",
    }),
  importupload: (formData) =>
    requestForm("/sync/import-upload", formData, {
      method: "POST",
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
  versionFileContentUrl: (versionId, fileId) =>
    buildApiUrl(`/versions/${versionId}/files/${fileId}/content`),
  versionFileDownloadUrl: (versionId, fileId) =>
    buildApiUrl(`/versions/${versionId}/files/${fileId}/download`),
  artifactContentUrl: (artifactId) => buildApiUrl(`/artifacts/${artifactId}/content`),
  artifactDownloadUrl: (artifactId) => buildApiUrl(`/artifacts/${artifactId}/download`),
  fetchTextFromUrl: async (url) => {
    const response = await rawRequest(url, {
      headers: { Accept: "text/plain, application/xml, text/xml;q=0.9,*/*;q=0.8" },
    });
    return await response.text();
  },
  downloadFromUrl,
  downloadUrl: downloadFromUrl,
  downloadURL: downloadFromUrl,

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
