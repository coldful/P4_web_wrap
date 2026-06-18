export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString();
}

export function formatBytes(value) {
  const n = Number(value || 0);
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

export function classForStatus(status) {
  if (["succeeded", "approved", "published", "active", "ok"].includes(status)) return "good";
  if (["failed", "rejected", "canceled"].includes(status)) return "bad";
  if (["running", "submitted", "pending", "queued", "draft"].includes(status)) return "work";
  return "muted";
}

export function statusBadge(status) {
  return `<span class="badge ${classForStatus(status)}">${escapeHtml(status || "unknown")}</span>`;
}

export function shortId(value) {
  return String(value || "").slice(0, 8);
}

