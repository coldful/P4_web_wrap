import { api, getApiBase, setApiBase } from "./api.js?v=20260704-import-upload-fix1";
import { icon, legacyIcon } from "./icons.js?v=20260704-import-upload-fix1";
import {
  getFileJobConfig,
  getModuleJobConfig,
  isFileJob,
  isModuleJob,
  MODULE_JOB_SCHEMAS,
} from "./job-config.js?v=20260704-import-upload-fix1";
import {
  escapeHtml,
  formatBytes,
  formatDate,
  shortId,
  statusBadge,
} from "./utils.js?v=20260704-import-upload-fix1";

const RECENT_JOBS_KEY = "p4web.client.recentJobs";
const SELECTED_PROJECT_KEY = "p4web.client.selectedProjectId";
const SELECTED_VERSION_KEY = "p4web.client.selectedVersionId";
const SELECTED_JOB_KEY = "p4web.client.selectedJobId";
const LANGUAGE_KEY = "p4web.client.language";

const state = {
  health: null,
  projects: [],
  versions: [],
  files: [],
  projectArtifacts: [],
  versionArtifacts: [],
  jobs: [],
  jobLogs: [],
  selectedProjectId: localStorage.getItem(SELECTED_PROJECT_KEY),
  selectedVersionId: localStorage.getItem(SELECTED_VERSION_KEY),
  selectedJobId: localStorage.getItem(SELECTED_JOB_KEY),
  activeTab: "overview",
  activeRibbonPage: null,
  language: localStorage.getItem(LANGUAGE_KEY) || "de",
  openMenu: null,
  busy: false,
  modal: null,
  toast: null,
};

const root = document.getElementById("app");

function currentProject() {
  return state.projects.find((project) => project.id === state.selectedProjectId) || null;
}

function currentVersion() {
  return state.versions.find((version) => version.id === state.selectedVersionId) || null;
}

function currentJob() {
  return state.jobs.find((job) => job.id === state.selectedJobId) || null;
}

function currentArtifacts() {
  return state.versionArtifacts.length ? state.versionArtifacts : state.projectArtifacts;
}

function isRunnable() {
  return Boolean(currentProject() && currentVersion());
}

function render() {
  const project = currentProject();
  const version = currentVersion();
  root.innerHTML = `
    <div class="app-shell">
      ${renderTopbar()}
      ${renderRibbon(project, version)}
      <main class="workspace">
        ${renderProjectPanel()}
        ${renderMainPanel(project, version)}
        ${renderJobPanel()}
      </main>
      ${state.toast ? `<div class="toast">${escapeHtml(state.toast)}</div>` : ""}
      ${state.modal ? renderModal() : ""}
    </div>
  `;
  bindEvents();
}

function renderTopbar() {
  const health = state.health?.status || "offline";
  return `
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark">P4</div>
        <div class="brand-title">
          <strong>Publishing Server P4</strong>
          <span>${statusBadge(health)} ${escapeHtml(state.health?.environment || "client")}</span>
        </div>
      </div>
      <div class="connection">
        <input id="api-base-input" value="${escapeHtml(getApiBase())}" aria-label="API base" />
        <button class="icon-button" data-action="save-api-base" title="Connect">${icon("database")}</button>
      </div>
      <div class="top-actions">
        <select id="language-select" class="language-select" title="Language">
          ${["de", "en", "fr", "es", "pt", "ru", "zh"].map((lang) => `
            <option value="${lang}" ${lang === state.language ? "selected" : ""}>${lang}</option>
          `).join("")}
        </select>
        <button class="icon-button" data-action="refresh" title="Refresh">${icon("refresh")}</button>
      </div>
    </header>
  `;
}

function renderRibbon(project, version) {
  const disabled = isRunnable() ? "" : "disabled";
  const projectDisabled = project ? "" : "disabled";
  const pages = {
    File: [
      ribbonGroup("New", [
        legacyTool("new-project", "000pp001.bmp", "Create project"),
      ]),
      ribbonGroup("Open from folder", [
        legacyTool("open-upload-import", "penguin.png", "Change folder"),
        legacyDropdown("project-directory", "penguin.png", "Select project", renderProjectMenu("project-directory")),
      ]),
      ribbonGroup("Open directly", [
        legacyDropdown("last-used", "penguin.png", "Last used", renderProjectMenu("last-used")),
        legacyTool("open-upload-import", "gtk-open.png", "Archived"),
      ]),
    ],
    Project: [
      ribbonGroup("Generate", [
        legacyHybrid(
          "job:generate_pdf",
          "pdf-variants",
          "000pp013.bmp",
          "PDF",
          renderMenu("pdf-variants", [
            menuAction("job:generate_pdf", "default: all pdfs", disabled),
            menuParamAction("generate_pdf", "pdf_scope", "main", "only the main pdf", disabled),
            menuParamAction("generate_pdf", "pdf_scope", "extra", "only the extra pdfs", disabled),
            menuAction("job:texml_pdf", "TeXML PDF", disabled),
            menuAction("job:xsl_fo", "XSL-FO Processing", disabled),
          ]),
          disabled,
        ),
        legacyTool("job:generate_html", "000pp028.bmp", "HTML", disabled),
      ]),
      ribbonGroup("Aladin", [
        legacyTool("job:generate_html", "penguin.png", "Demo", disabled),
        legacyUnavailable("penguin.png", "HTML for one code"),
        legacyTool("job:generate_html", "000pp028.bmp", "HTML site", disabled),
      ]),
      ribbonGroup("Data source", [
        legacyUnavailable("000pp005.bmp", "Kustode in Excel"),
        legacyTabTool("files", "300pp031.bmp", "XML source", projectDisabled),
        legacyUnavailable("000pp016.bmp", "CSV import"),
        legacyTool("job:convert_sap_to_bit_xml", "000pp017.bmp", "ETK SAP import", disabled),
      ]),
      ribbonGroup("Translation", [
        legacyTool("job:import_translation", "000pp011.bmp", "Import", disabled),
        legacyTool("job:export_translation", "000pp010.bmp", "Export", disabled),
      ]),
      ribbonGroup("Languages", [
        renderLanguageButtons(),
      ]),
    ],
    Advanced: [
      ribbonGroup("Text modules", [
        legacyTool("job:pack_modules", "000pp008.bmp", "Pack", disabled),
        legacyTool("job:unpack_modules", "000pp009.bmp", "Unpack", disabled),
      ]),
      ribbonGroup("Uncategorized", [
        legacyUnavailable("branch.gif", "Trunk to branch"),
        legacyHybrid(
          "job:cut_source",
          "cut-source-variants",
          "300pp033.bmp",
          "Cut source",
          renderMenu("cut-source-variants", [
            menuAction("job:generate_lists", "Generate lists", disabled),
            menuDisabled("Generate drawing register"),
            menuAction("job:check_index", "Check index", disabled),
          ]),
          disabled,
        ),
        legacyUnavailable("000pp014.bmp", "Open keyseq file"),
        legacyUnavailable("penguin.png", "Create P2 project"),
      ]),
      ribbonGroup("Debug", [
        legacyUnavailable("000pp003.bmp", "More messages"),
        legacyUnavailable("000pp007.bmp", "Open as TeX"),
      ]),
    ],
    Subsystem: [
      ribbonGroup("Tools", [
        legacyUnavailable("000pp017.bmp", "Mini-ETK"),
      ]),
      ribbonGroup("Conversion", [
        legacyTool("job:convert_sap_to_bit_xml", "000pp017.bmp", "ETK SAP to bitplant XML", projectDisabled),
        legacyTool("job:convert_opmanual_to_bit_xml", "penguin.png", "Opmanual to bitplant XML", projectDisabled),
      ]),
    ],
    Config: [
      ribbonGroup("Resources", [
        legacyUnavailable("000pp002.bmp", "Stylesheets"),
        legacyUnavailable("000pp012.bmp", "Images"),
        legacyUnavailable("penguin.png", "Upload files"),
      ]),
      ribbonGroup("Settings", [
        legacyTool("focus-api-base", "000pp003.bmp", "Server IP"),
        legacyUnavailable("000pp004.bmp", "Paths"),
        legacyUnavailable("penguin.png", "Layout"),
      ]),
      ribbonGroup("Variables", [
        legacyUnavailable("penguin.png", "Defaults by keyseq"),
        legacyUnavailable("penguin.png", "Defaults in template"),
        legacyUnavailable("penguin.png", "Reconfigure project"),
      ]),
    ],
  };
  if (!pages[state.activeRibbonPage]) state.activeRibbonPage = project ? "Project" : "File";
  return `
    <nav class="ribbon legacy-ribbon" aria-label="P4 actions">
      <div class="ribbon-tabs" role="tablist">
        ${Object.keys(pages).map((page) => `
          <button
            class="ribbon-tab ${state.activeRibbonPage === page ? "active" : ""}"
            data-ribbon-page="${escapeHtml(page)}"
            role="tab"
            aria-selected="${state.activeRibbonPage === page ? "true" : "false"}"
          >${escapeHtml(page)}</button>
        `).join("")}
      </div>
      <div class="ribbon-page" role="tabpanel">
        ${pages[state.activeRibbonPage].join("")}
      </div>
    </nav>
  `;
}

function ribbonGroup(title, buttons) {
  return `
    <section class="ribbon-group">
      <div class="ribbon-buttons">${buttons.join("")}</div>
      <div class="ribbon-title">${escapeHtml(title)}</div>
    </section>
  `;
}

function legacyTool(action, iconFile, title, disabled = "") {
  return `
    <button class="tool-button legacy-tool" data-action="${escapeHtml(action)}" title="${escapeHtml(title)}" ${disabled}>
      ${legacyIcon(iconFile)}
      <span>${escapeHtml(title)}</span>
    </button>
  `;
}

function legacyTabTool(tab, iconFile, title, disabled = "") {
  return `
    <button class="tool-button legacy-tool" data-tab="${escapeHtml(tab)}" title="${escapeHtml(title)}" ${disabled}>
      ${legacyIcon(iconFile)}
      <span>${escapeHtml(title)}</span>
    </button>
  `;
}

function legacyUnavailable(iconFile, title) {
  return `
    <button class="tool-button legacy-tool unavailable" title="${escapeHtml(title)} is not available in the web version yet" disabled>
      ${legacyIcon(iconFile)}
      <span>${escapeHtml(title)}</span>
    </button>
  `;
}

function legacyDropdown(menuId, iconFile, title, menuHtml, disabled = "") {
  return `
    <div class="ribbon-menu-wrap">
      <button class="tool-button legacy-tool dropdown-only" data-action="toggle-menu" data-menu-id="${escapeHtml(menuId)}" title="${escapeHtml(title)}" ${disabled}>
        ${legacyIcon(iconFile)}
        <span>${escapeHtml(title)}</span>
        <span class="drop-mark" aria-hidden="true"></span>
      </button>
      ${menuHtml}
    </div>
  `;
}

function legacyHybrid(action, menuId, iconFile, title, menuHtml, disabled = "") {
  return `
    <div class="legacy-hybrid ribbon-menu-wrap">
      <button class="tool-button legacy-tool hybrid-main" data-action="${escapeHtml(action)}" title="${escapeHtml(title)}" ${disabled}>
        ${legacyIcon(iconFile)}
        <span>${escapeHtml(title)}</span>
      </button>
      <button class="hybrid-drop" data-action="toggle-menu" data-menu-id="${escapeHtml(menuId)}" title="${escapeHtml(title)} variants" ${disabled}>
        <span class="drop-mark" aria-hidden="true"></span>
      </button>
      ${menuHtml}
    </div>
  `;
}

function renderMenu(menuId, items) {
  return `
    <div class="ribbon-menu ${state.openMenu === menuId ? "open" : ""}" role="menu">
      ${items.join("")}
    </div>
  `;
}

function renderProjectMenu(menuId) {
  const items = state.projects.map((project) => `
    <button class="ribbon-menu-item" data-project-id="${escapeHtml(project.id)}" role="menuitem">
      ${legacyIcon("000pp001.bmp", "menu-icon")}
      <span>${escapeHtml(project.name)}</span>
    </button>
  `);
  if (!items.length) items.push(`<button class="ribbon-menu-item" disabled>No projects</button>`);
  return renderMenu(menuId, items);
}

function menuAction(action, label, disabled = "") {
  return `
    <button class="ribbon-menu-item plain-menu-item" data-action="${escapeHtml(action)}" ${disabled} role="menuitem">
      <span>${escapeHtml(label)}</span>
    </button>
  `;
}

function menuParamAction(kind, key, value, label, disabled = "") {
  return `
    <button
      class="ribbon-menu-item plain-menu-item"
      data-action="job-param"
      data-job-kind="${escapeHtml(kind)}"
      data-param-key="${escapeHtml(key)}"
      data-param-value="${escapeHtml(value)}"
      ${disabled}
      role="menuitem"
    >
      <span>${escapeHtml(label)}</span>
    </button>
  `;
}

function menuDisabled(label) {
  return `<button class="ribbon-menu-item plain-menu-item" disabled role="menuitem">${escapeHtml(label)}</button>`;
}

function renderLanguageButtons() {
  return `
    <div class="ribbon-language-buttons">
      ${["de", "en", "fr", "es", "pt", "ru", "zh"].map((lang) => `
        <button
          class="language-flag ${state.language === lang ? "active" : ""}"
          data-language="${lang}"
          title="${escapeHtml(lang)}"
          aria-label="${escapeHtml(lang)}"
        >
          <span>${escapeHtml(lang)}</span>
        </button>
      `).join("")}
    </div>
  `;
}

function renderProjectPanel() {
  const rows = state.projects.map((project) => {
    const active = project.id === state.selectedProjectId ? "active" : "";
    return `
      <button class="project-row ${active}" data-project-id="${escapeHtml(project.id)}">
        <span class="project-glyph">${icon("folder")}</span>
        <span class="project-meta">
          <strong>${escapeHtml(project.name)}</strong>
          <span class="muted small truncate">${escapeHtml(project.default_client || project.slug)}</span>
          <span class="muted small">${statusBadge(project.lifecycle)}</span>
        </span>
      </button>
    `;
  }).join("");

  return `
    <aside class="panel">
      <div class="panel-header">
        <h2>Projects</h2>
        <button class="icon-button" data-action="new-project" title="Create project">${icon("plus")}</button>
      </div>
      <div class="panel-body">
        <div class="project-list">
          ${rows || `<div class="empty">No projects</div>`}
        </div>
      </div>
    </aside>
  `;
}

function renderMainPanel(project, version) {
  if (!project) {
    return `
      <section class="panel main-panel">
        <div class="panel-header">
          <div class="project-title">
            <span class="project-glyph">${icon("folder")}</span>
            <h1>P4 workspace</h1>
          </div>
        </div>
        <div class="tab-panel">
          <div class="empty">No project selected</div>
        </div>
      </section>
    `;
  }

  const tabs = [
    ["overview", "Overview"],
    ["versions", "Versions"],
    ["files", "Files"],
    ["artifacts", "Artifacts"],
    ["jobs", "Jobs"],
  ];
  return `
    <section class="panel main-panel">
      <div class="panel-header">
        <div class="project-title">
          <span class="project-glyph">${icon("folder")}</span>
          <h1>${escapeHtml(project.name)}</h1>
          ${statusBadge(project.lifecycle)}
        </div>
        <button class="icon-button" data-action="new-version" title="Create version">${icon("file")}</button>
      </div>
      ${renderSummary(project, version)}
      <div class="tabs">
        ${tabs.map(([id, label]) => `
          <button class="tab ${state.activeTab === id ? "active" : ""}" data-tab="${id}">
            ${escapeHtml(label)}
          </button>
        `).join("")}
      </div>
      <div class="tab-panel">${renderActiveTab(project, version)}</div>
    </section>
  `;
}

function renderSummary(project, version) {
  return `
    <div class="summary-grid">
      <div class="metric">
        <span class="muted small">Client</span>
        <strong>${escapeHtml(project.default_client || "-")}</strong>
      </div>
      <div class="metric">
        <span class="muted small">Version</span>
        <strong>${version ? `#${version.version_number}` : "-"}</strong>
      </div>
      <div class="metric">
        <span class="muted small">State</span>
        <strong>${version ? statusBadge(version.status) : statusBadge("draft")}</strong>
      </div>
      <div class="metric">
        <span class="muted small">Artifacts</span>
        <strong>${state.versionArtifacts.length || state.projectArtifacts.length}</strong>
      </div>
    </div>
  `;
}

function renderActiveTab(project, version) {
  if (state.activeTab === "versions") return renderVersions();
  if (state.activeTab === "files") return renderFiles();
  if (state.activeTab === "artifacts") return renderArtifacts();
  if (state.activeTab === "jobs") return renderJobsTable();
  return renderOverview(project, version);
}

function renderOverview(project, version) {
  return `
    <div class="split-two">
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>File</th><th>Role</th><th>Size</th><th>SHA256</th></tr>
          </thead>
          <tbody>
            ${state.files.slice(0, 8).map((file) => `
              <tr>
                <td class="truncate">${escapeHtml(file.path)}</td>
                <td>${escapeHtml(file.role)}</td>
                <td>${formatBytes(file.size_bytes)}</td>
                <td><span class="muted small">${escapeHtml(shortId(file.sha256))}</span></td>
              </tr>
            `).join("") || `<tr><td colspan="4" class="muted">No files</td></tr>`}
          </tbody>
        </table>
      </div>
      <div class="panel">
        <div class="panel-header"><h3>Project Sheet</h3></div>
        <div class="panel-body keyvals">
          ${kv("Project", project.name)}
          ${kv("Slug", project.slug)}
          ${kv("Local path", project.local_path_hint || "-")}
          ${kv("Selected version", version ? `#${version.version_number}` : "-")}
          ${kv("Snapshot", version?.snapshot_prefix || "-")}
        </div>
      </div>
    </div>
  `;
}

function kv(key, value) {
  return `
    <div class="kv">
      <span class="muted">${escapeHtml(key)}</span>
      <span class="truncate">${escapeHtml(value)}</span>
    </div>
  `;
}

function renderVersions() {
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>#</th><th>Status</th><th>Label</th><th>Created</th><th>Snapshot</th><th></th></tr>
        </thead>
        <tbody>
          ${state.versions.map((version) => `
            <tr>
              <td>#${version.version_number}</td>
              <td>${statusBadge(version.status)}</td>
              <td>${escapeHtml(version.label || "")}</td>
              <td>${escapeHtml(formatDate(version.created_at))}</td>
              <td><span class="muted small truncate">${escapeHtml(version.snapshot_prefix)}</span></td>
              <td class="row-actions">
                <button class="text-button ${version.id === state.selectedVersionId ? "primary" : ""}" data-version-id="${escapeHtml(version.id)}">Select</button>
              </td>
            </tr>
          `).join("") || `<tr><td colspan="6" class="muted">No versions</td></tr>`}
        </tbody>
      </table>
    </div>
  `;
}

function renderFiles() {
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Path</th><th>Role</th><th>Size</th><th>SHA256</th><th>Storage</th><th></th></tr>
        </thead>
        <tbody>
          ${state.files.map((file) => `
            <tr>
              <td class="truncate">${renderStoredObjectName(file.path, isPreviewSupported(file), "preview-file", file.id)}</td>
              <td>${escapeHtml(file.role)}</td>
              <td>${formatBytes(file.size_bytes)}</td>
              <td><span class="muted small">${escapeHtml(file.sha256)}</span></td>
              <td><span class="muted small truncate">${escapeHtml(file.storage_key)}</span></td>
              <td class="row-actions">
                ${isPreviewSupported(file) ? `<button class="text-button" data-action="preview-file" data-file-id="${escapeHtml(file.id)}">Open</button>` : ""}
                <button class="text-button" data-action="download-file" data-file-id="${escapeHtml(file.id)}">${icon("download")} Download</button>
              </td>
            </tr>
          `).join("") || `<tr><td colspan="6" class="muted">No files</td></tr>`}
        </tbody>
      </table>
    </div>
  `;
}

function renderArtifacts() {
  const artifacts = currentArtifacts();
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Kind</th><th>Path</th><th>Size</th><th>Created</th><th>Storage</th><th></th></tr>
        </thead>
        <tbody>
          ${artifacts.map((artifact) => `
            <tr>
              <td>${escapeHtml(artifact.kind)}</td>
              <td class="truncate">${renderStoredObjectName(artifact.path, isPreviewSupported(artifact), "preview-artifact", artifact.id)}</td>
              <td>${formatBytes(artifact.size_bytes)}</td>
              <td>${escapeHtml(formatDate(artifact.created_at))}</td>
              <td><span class="muted small truncate">${escapeHtml(artifact.storage_key)}</span></td>
              <td class="row-actions">
                ${isPreviewSupported(artifact) ? `<button class="text-button" data-action="preview-artifact" data-artifact-id="${escapeHtml(artifact.id)}">Open</button>` : ""}
                <button class="text-button" data-action="download-artifact" data-artifact-id="${escapeHtml(artifact.id)}">${icon("download")} Download</button>
              </td>
            </tr>
          `).join("") || `<tr><td colspan="6" class="muted">No artifacts</td></tr>`}
        </tbody>
      </table>
    </div>
  `;
}

function renderJobsTable() {
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Job</th><th>Kind</th><th>Status</th><th>Progress</th><th>Created</th><th></th></tr>
        </thead>
        <tbody>
          ${state.jobs.map((job) => `
            <tr>
              <td>${escapeHtml(shortId(job.id))}</td>
              <td>${escapeHtml(job.kind)}</td>
              <td>${statusBadge(job.status)}</td>
              <td>${job.progress_current}/${job.progress_total}</td>
              <td>${escapeHtml(formatDate(job.created_at))}</td>
              <td class="row-actions">
                <button class="text-button ${job.id === state.selectedJobId ? "primary" : ""}" data-job-id="${escapeHtml(job.id)}">Open</button>
              </td>
            </tr>
          `).join("") || `<tr><td colspan="6" class="muted">No jobs</td></tr>`}
        </tbody>
      </table>
    </div>
  `;
}

function renderJobPanel() {
  const job = currentJob();
  const logText = state.jobLogs.map((log) => {
    const ts = formatDate(log.created_at);
    return `[${ts}] ${log.level.toUpperCase()} ${log.message}`;
  }).join("\n");

  return `
    <aside class="panel job-panel">
      <div class="panel-header">
        <h2>Jobs</h2>
        <button class="icon-button" data-action="refresh-jobs" title="Refresh jobs">${icon("refresh")}</button>
      </div>
      <div class="panel-body">
        <div class="job-list">
          ${state.jobs.slice(0, 8).map((item) => `
            <button class="job-row ${item.id === state.selectedJobId ? "active" : ""}" data-job-id="${escapeHtml(item.id)}">
              <span>
                <strong>${escapeHtml(item.kind)}</strong>
                <span class="muted small truncate">${escapeHtml(shortId(item.id))}</span>
              </span>
              ${statusBadge(item.status)}
            </button>
          `).join("") || `<div class="empty">No jobs</div>`}
        </div>
        <div style="height: 12px"></div>
        ${job ? `
          <div class="keyvals">
            ${kv("Current job", shortId(job.id))}
            ${kv("Status", job.status)}
            ${kv("Progress", `${job.progress_current}/${job.progress_total}`)}
          </div>
          <div style="height: 10px"></div>
          <div class="log-view">${escapeHtml(logText || "No log entries")}</div>
        ` : ""}
      </div>
    </aside>
  `;
}

function renderModal() {
  if (state.modal.type === "project") return renderProjectModal();
  if (state.modal.type === "copy-project") return renderCopyProjectModal();
  if (state.modal.type === "delete-project") return renderDeleteProjectModal();
  if (state.modal.type === "local-import") return renderLocalImportModal();
  if (state.modal.type === "version") return renderVersionModal();
  if (state.modal.type === "module-job") return renderModuleJobModal();
  if (state.modal.type === "file-job") return renderFileJobModal();
  if (state.modal.type === "approval") return renderApprovalModal();
  if (state.modal.type === "preview") return renderPreviewModal();
  return "";
}

function renderPreviewModal() {
  const modal = state.modal;
  if (!modal || modal.type !== "preview") return "";
  return `
    <div class="modal-backdrop">
      <section class="modal preview-modal" style="width: min(96vw, 1680px); height: min(94vh, 1120px);">
        <header class="preview-header">
          <button type="button" class="text-button" data-action="close-modal">${icon("back")} Back</button>
          <div class="preview-title">
            <h2>${escapeHtml(modal.title)}</h2>
            <span class="muted small">${escapeHtml(modal.subtitle || "")}</span>
          </div>
          <button type="button" class="text-button" data-action="${escapeHtml(modal.downloadAction)}" ${modal.downloadIdAttr}>
            ${icon("download")} Download
          </button>
        </header>
        <div class="preview-body">
          ${renderPreviewBody(modal)}
        </div>
      </section>
    </div>
  `;
}

function renderPreviewBody(modal) {
  if (modal.loading) {
    return `<div class="empty">Loading preview...</div>`;
  }
  if (modal.error) {
    return `<div class="empty">${escapeHtml(modal.error)}</div>`;
  }
  if (modal.previewKind === "text") {
    return `<pre class="preview-text">${escapeHtml(modal.textContent || "")}</pre>`;
  }
  if (modal.previewKind === "image") {
    return `
      <div class="preview-image-wrap">
        <img class="preview-image" src="${escapeHtml(modal.sourceUrl)}" alt="${escapeHtml(modal.title)}" />
      </div>
    `;
  }
  if (modal.previewKind === "pdf") {
    return `<iframe class="preview-frame" src="${escapeHtml(modal.sourceUrl)}" title="${escapeHtml(modal.title)}"></iframe>`;
  }
  return `<div class="empty">Preview is not available for this file.</div>`;
}

function renderStoredObjectName(path, previewable, action, id) {
  if (!previewable) return escapeHtml(path);
  const idAttr = action === "preview-file"
    ? `data-file-id="${escapeHtml(id)}"`
    : `data-artifact-id="${escapeHtml(id)}"`;
  return `<button class="link-button truncate" data-action="${escapeHtml(action)}" ${idAttr}>${escapeHtml(path)}</button>`;
}

function previewKindFor(item) {
  const path = String(item?.path || "").toLowerCase();
  const contentType = String(item?.content_type || "").toLowerCase();
  if (contentType.includes("pdf") || path.endsWith(".pdf")) return "pdf";
  if (
    contentType.startsWith("image/") ||
    [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp"].some((suffix) => path.endsWith(suffix))
  ) {
    return "image";
  }
  if (
    contentType.startsWith("text/") ||
    contentType.includes("xml") ||
    [".txt", ".xml", ".log", ".fo"].some((suffix) => path.endsWith(suffix))
  ) {
    return "text";
  }
  return null;
}

function isPreviewSupported(item) {
  return Boolean(previewKindFor(item));
}

function versionFileContentUrl(versionId, fileId) {
  return `${getApiBase()}/versions/${versionId}/files/${fileId}/content`;
}

function versionFileDownloadUrl(versionId, fileId) {
  return `${getApiBase()}/versions/${versionId}/files/${fileId}/download`;
}

function artifactContentUrl(artifactId) {
  return `${getApiBase()}/artifacts/${artifactId}/content`;
}

function artifactDownloadUrl(artifactId) {
  return `${getApiBase()}/artifacts/${artifactId}/download`;
}

async function fetchPreviewText(url) {
  const response = await fetch(url, {
    headers: { Accept: "text/plain, application/xml, text/xml;q=0.9,*/*;q=0.8" },
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return await response.text();
}

async function downloadStoredObject(url, filename) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
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

async function responseErrorMessage(response) {
  const text = await response.text();
  try {
    const data = text ? JSON.parse(text) : null;
    return data?.detail || response.statusText || "Request failed";
  } catch {
    return text || response.statusText || "Request failed";
  }
}

function renderProjectModal() {
  return `
    <div class="modal-backdrop">
      <form class="modal" id="project-form">
        <header>
          <h2>Create project</h2>
          <button type="button" class="icon-button" data-action="close-modal" title="Close">${icon("x")}</button>
        </header>
        <div class="modal-body">
          ${field("name", "Name", "text", "", true)}
          ${field("slug", "Slug", "text")}
          ${field("default_client", "Client", "text")}
          ${field("local_path_hint", "Local path", "text")}
          ${textareaField("description", "Description")}
        </div>
        <footer>
          <button type="button" class="text-button" data-action="close-modal">Cancel</button>
          <button class="text-button primary" type="submit">Create</button>
        </footer>
      </form>
    </div>
  `;
}

function renderCopyProjectModal() {
  const project = currentProject();
  if (!project) return "";
  return `
    <div class="modal-backdrop">
      <form class="modal" id="copy-project-form">
        <header>
          <h2>Copy project</h2>
          <button type="button" class="icon-button" data-action="close-modal" title="Close">${icon("x")}</button>
        </header>
        <div class="modal-body">
          ${field("name", "Name", "text", `${project.name} copy`, true)}
          ${field("slug", "Slug", "text")}
          ${textareaField("description", "Description", project.description || "")}
        </div>
        <footer>
          <button type="button" class="text-button" data-action="close-modal">Cancel</button>
          <button class="text-button primary" type="submit">Copy</button>
        </footer>
      </form>
    </div>
  `;
}

function renderDeleteProjectModal() {
  const project = currentProject();
  if (!project) return "";
  return `
    <div class="modal-backdrop">
      <form class="modal" id="delete-project-form">
        <header>
          <h2>Delete project</h2>
          <button type="button" class="icon-button" data-action="close-modal" title="Close">${icon("x")}</button>
        </header>
        <div class="modal-body">
          ${field("confirm_name", "Confirm name", "text", "", true)}
        </div>
        <footer>
          <button type="button" class="text-button" data-action="close-modal">Cancel</button>
          <button class="text-button danger" type="submit">Delete</button>
        </footer>
      </form>
    </div>
  `;
}

function renderLocalImportModal() {
  const targetOptions = [
    ["", "New project"],
    ...state.projects.map((project) => [project.id, project.name]),
  ];
  const selectedFiles = state.modal?.uploadedFiles || [];
  const detectedFolderName = state.modal?.detectedFolderName || "";
  return `
    <div class="modal-backdrop">
      <form class="modal" id="local-import-form">
        <header>
          <h2>Import local project</h2>
          <button type="button" class="icon-button" data-action="close-modal" title="Close">${icon("x")}</button>
        </header>
        <div class="modal-body">
          <input id="local-import-folder-input" type="file" webkitdirectory directory multiple hidden />
          <div class="field">
            <label>Project folder</label>
            <div class="folder-picker-row">
              <button type="button" class="text-button" data-action="browse-local-folder">${icon("folder")} Choose folder</button>
              <div class="folder-picker-meta">
                <strong>${escapeHtml(detectedFolderName || "No folder selected")}</strong>
                <span class="muted small">${selectedFiles.length ? `${selectedFiles.length} files selected` : "The whole folder will be uploaded with subfolders."}</span>
              </div>
            </div>
          </div>
          ${selectField("project_id", "Target", targetOptions)}
          ${field("project_name", "Project name", "text")}
          ${field("label", "Version label", "text", "manual import")}
        </div>
        <footer>
          <button type="button" class="text-button" data-action="close-modal">Cancel</button>
          <button class="text-button primary" type="submit">Import</button>
        </footer>
      </form>
    </div>
  `;
}

function renderVersionModal() {
  return `
    <div class="modal-backdrop">
      <form class="modal" id="version-form">
        <header>
          <h2>Create version</h2>
          <button type="button" class="icon-button" data-action="close-modal" title="Close">${icon("x")}</button>
        </header>
        <div class="modal-body">
          ${field("label", "Label", "text")}
          ${textareaField("manifest", "Manifest JSON", JSON.stringify({ source: "web-client" }, null, 2))}
        </div>
        <footer>
          <button type="button" class="text-button" data-action="close-modal">Cancel</button>
          <button class="text-button primary" type="submit">Create</button>
        </footer>
      </form>
    </div>
  `;
}

function renderModuleJobModal() {
  const config = getModuleJobConfig(state.modal.kind);
  const version = currentVersion();
  if (!config || !version) return "";
  return `
    <div class="modal-backdrop">
      <form class="modal" id="module-job-form">
        <header>
          <h2>${escapeHtml(config.title)}</h2>
          <button type="button" class="icon-button" data-action="close-modal" title="Close">${icon("x")}</button>
        </header>
        <div class="modal-body">
          ${selectField("schema", "Schema", MODULE_JOB_SCHEMAS, MODULE_JOB_SCHEMAS[0][0])}
          ${field("version_label", "Result label", "text", config.defaultLabel, true)}
          ${field("source_version", "Source version", "text", `#${version.version_number}`, false)}
        </div>
        <footer>
          <button type="button" class="text-button" data-action="close-modal">Cancel</button>
          <button class="text-button primary" type="submit">${escapeHtml(config.submitLabel)}</button>
        </footer>
      </form>
    </div>
  `;
}

function renderFileJobModal() {
  const config = getFileJobConfig(state.modal.kind);
  if (!config) return "";
  const fields = [];
  if (state.modal.kind === "convert_sap_to_bit_xml") {
    fields.push(field("etk_file", "ETK XML path", "text", "", true));
    fields.push(field("output_file", "Output XML path", "text"));
  }
  if (state.modal.kind === "convert_opmanual_to_bit_xml") {
    fields.push(textareaField("opmanual_files", "Opmanual XML paths"));
  }
  return `
    <div class="modal-backdrop">
      <form class="modal" id="file-job-form">
        <header>
          <h2>${escapeHtml(config.title)}</h2>
          <button type="button" class="icon-button" data-action="close-modal" title="Close">${icon("x")}</button>
        </header>
        <div class="modal-body">
          <p class="muted small">${escapeHtml(config.description || "")}</p>
          ${fields.join("")}
        </div>
        <footer>
          <button type="button" class="text-button" data-action="close-modal">Cancel</button>
          <button class="text-button primary" type="submit">${escapeHtml(config.submitLabel)}</button>
        </footer>
      </form>
    </div>
  `;
}

function renderApprovalModal() {
  const titles = {
    submit: "Submit version",
    approve: "Approve version",
    reject: "Reject version",
  };
  return `
    <div class="modal-backdrop">
      <form class="modal" id="approval-form">
        <header>
          <h2>${escapeHtml(titles[state.modal.approvalAction] || "Review version")}</h2>
          <button type="button" class="icon-button" data-action="close-modal" title="Close">${icon("x")}</button>
        </header>
        <div class="modal-body">
          ${textareaField("comment", "Comment")}
        </div>
        <footer>
          <button type="button" class="text-button" data-action="close-modal">Cancel</button>
          <button class="text-button primary" type="submit">Save</button>
        </footer>
      </form>
    </div>
  `;
}

function field(name, label, type, value = "", required = false) {
  return `
    <div class="field">
      <label for="${name}">${escapeHtml(label)}</label>
      <input id="${name}" name="${name}" type="${type}" value="${escapeHtml(value)}" ${required ? "required" : ""} />
    </div>
  `;
}

function textareaField(name, label, value = "") {
  return `
    <div class="field">
      <label for="${name}">${escapeHtml(label)}</label>
      <textarea id="${name}" name="${name}">${escapeHtml(value)}</textarea>
    </div>
  `;
}

function selectField(name, label, options, value = "") {
  return `
    <div class="field">
      <label for="${name}">${escapeHtml(label)}</label>
      <select id="${name}" name="${name}">
        ${options.map(([optionValue, optionLabel]) => `
          <option value="${escapeHtml(optionValue)}" ${optionValue === value ? "selected" : ""}>
            ${escapeHtml(optionLabel)}
          </option>
        `).join("")}
      </select>
    </div>
  `;
}

function bindEvents() {
  root.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", onAction);
  });
  root.querySelectorAll("[data-project-id]").forEach((button) => {
    button.addEventListener("click", () => selectProject(button.dataset.projectId));
  });
  root.querySelectorAll("[data-version-id]").forEach((button) => {
    button.addEventListener("click", () => selectVersion(button.dataset.versionId));
  });
  root.querySelectorAll("[data-job-id]").forEach((button) => {
    button.addEventListener("click", () => selectJob(button.dataset.jobId));
  });
  root.querySelectorAll("[data-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeTab = button.dataset.tab;
      state.openMenu = null;
      render();
    });
  });
  root.querySelectorAll("[data-ribbon-page]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeRibbonPage = button.dataset.ribbonPage;
      state.openMenu = null;
      render();
    });
  });
  root.querySelectorAll("[data-language]").forEach((button) => {
    button.addEventListener("click", () => {
      state.language = button.dataset.language;
      localStorage.setItem(LANGUAGE_KEY, state.language);
      state.openMenu = null;
      render();
    });
  });
  root.querySelector("#language-select")?.addEventListener("change", (event) => {
    state.language = event.target.value;
    localStorage.setItem(LANGUAGE_KEY, state.language);
    render();
  });
  root.querySelector("#project-form")?.addEventListener("submit", submitProjectForm);
  root.querySelector("#copy-project-form")?.addEventListener("submit", submitCopyProjectForm);
  root.querySelector("#delete-project-form")?.addEventListener("submit", submitDeleteProjectForm);
  root.querySelector("#local-import-form")?.addEventListener("submit", submitLocalImportForm);
  root.querySelector("#local-import-folder-input")?.addEventListener("change", onLocalImportFolderChange);
  root.querySelector("#version-form")?.addEventListener("submit", submitVersionForm);
  root.querySelector("#module-job-form")?.addEventListener("submit", submitModuleJobForm);
  root.querySelector("#file-job-form")?.addEventListener("submit", submitFileJobForm);
  root.querySelector("#approval-form")?.addEventListener("submit", submitApprovalForm);
}

async function onAction(event) {
  const action = event.currentTarget.dataset.action;
  const fileId = event.currentTarget.dataset.fileId;
  const artifactId = event.currentTarget.dataset.artifactId;
  if (!action || event.currentTarget.disabled) return;
  if (action === "toggle-menu") {
    const menuId = event.currentTarget.dataset.menuId;
    state.openMenu = state.openMenu === menuId ? null : menuId;
    render();
    return;
  }
  state.openMenu = null;
  if (action === "job-param") {
    const kind = event.currentTarget.dataset.jobKind;
    const key = event.currentTarget.dataset.paramKey;
    const value = event.currentTarget.dataset.paramValue;
    if (kind && key) await startJob(kind, { [key]: value });
    return;
  }
  if (action.startsWith("job:")) {
    const kind = action.slice(4);
    if (isModuleJob(kind)) {
      openModal({ type: "module-job", kind });
      return;
    }
    if (isFileJob(kind)) {
      openModal({ type: "file-job", kind });
      return;
    }
    await startJob(kind);
    return;
  }
  const handlers = {
    refresh: refreshAll,
    "refresh-jobs": refreshRecentJobs,
    "save-api-base": saveApiBase,
    "focus-api-base": focusApiBase,
    "browse-local-folder": browseLocalFolder,
    "new-project": () => openModal({ type: "project" }),
    "copy-project": () => openModal({ type: "copy-project" }),
    "delete-project": () => openModal({ type: "delete-project" }),
    "open-upload-import": () => openModal({ type: "local-import" }),
    "new-version": () => openModal({ type: "version" }),
    "close-modal": closeModal,
    "preview-file": () => openFilePreview(fileId),
    "download-file": () => downloadFile(fileId),
    "preview-artifact": () => openArtifactPreview(artifactId),
    "download-artifact": () => downloadArtifact(artifactId),
    "submit-version": () => openModal({ type: "approval", approvalAction: "submit" }),
    "approve-version": () => openModal({ type: "approval", approvalAction: "approve" }),
    "reject-version": () => openModal({ type: "approval", approvalAction: "reject" }),
  };
  await handlers[action]?.();
}

function focusApiBase() {
  const input = root.querySelector("#api-base-input");
  input?.focus();
  input?.select();
}

function browseLocalFolder() {
  root.querySelector("#local-import-folder-input")?.click();
}

async function saveApiBase() {
  const input = root.querySelector("#api-base-input");
  setApiBase(input?.value || "");
  notify("Connection updated");
  await refreshAll();
}

function openModal(modal) {
  if (modal?.type === "local-import") {
    state.modal = {
      uploadedFiles: [],
      detectedFolderName: "",
      ...modal,
    };
  } else {
    state.modal = modal;
  }
  render();
}

function closeModal() {
  state.modal = null;
  render();
}

async function openFilePreview(fileId) {
  const version = currentVersion();
  const file = state.files.find((item) => item.id === fileId);
  if (!version || !file) return;
  await openStoredObjectPreview({
    item: file,
    contentUrl: versionFileContentUrl(version.id, file.id),
    downloadAction: "download-file",
    downloadIdAttr: `data-file-id="${escapeHtml(file.id)}"`,
  });
}

async function openArtifactPreview(artifactId) {
  const artifact = currentArtifacts().find((item) => item.id === artifactId);
  if (!artifact) return;
  await openStoredObjectPreview({
    item: artifact,
    contentUrl: artifactContentUrl(artifact.id),
    downloadAction: "download-artifact",
    downloadIdAttr: `data-artifact-id="${escapeHtml(artifact.id)}"`,
  });
}

async function openStoredObjectPreview({ item, contentUrl, downloadAction, downloadIdAttr }) {
  const previewKind = previewKindFor(item);
  if (!previewKind) {
    notify("Preview is not available for this file type");
    return;
  }
  const modal = {
    type: "preview",
    title: item.path,
    subtitle: item.content_type || item.kind || "",
    previewKind,
    sourceUrl: previewKind === "text" ? "" : contentUrl,
    textContent: "",
    loading: previewKind === "text",
    error: "",
    downloadAction,
    downloadIdAttr,
  };
  state.modal = modal;
  render();
  if (previewKind !== "text") return;
  try {
    const text = await fetchPreviewText(contentUrl);
    if (state.modal !== modal) return;
    state.modal = { ...modal, loading: false, textContent: text };
    render();
  } catch (error) {
    if (state.modal !== modal) return;
    state.modal = { ...modal, loading: false, error: error.message || "Preview failed" };
    render();
  }
}

async function downloadFile(fileId) {
  const version = currentVersion();
  const file = state.files.find((item) => item.id === fileId);
  if (!version || !file) return;
  await runAction(async () => {
    await downloadStoredObject(versionFileDownloadUrl(version.id, file.id), file.path.split("/").pop());
  }, { skipRender: true });
}

async function downloadArtifact(artifactId) {
  const artifact = currentArtifacts().find((item) => item.id === artifactId);
  if (!artifact) return;
  await runAction(async () => {
    await downloadStoredObject(artifactDownloadUrl(artifact.id), artifact.path.split("/").pop());
  }, { skipRender: true });
}

async function submitProjectForm(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  const payload = {
    name: data.name,
    slug: data.slug || null,
    description: data.description || null,
    default_client: data.default_client || null,
    local_path_hint: data.local_path_hint || null,
  };
  await runAction(async () => {
    const project = await api.createProject(payload);
    state.selectedProjectId = project.id;
    localStorage.setItem(SELECTED_PROJECT_KEY, project.id);
    state.modal = null;
    await refreshAll();
    notify("Project created");
  });
}

async function submitCopyProjectForm(event) {
  event.preventDefault();
  const project = currentProject();
  if (!project) return;
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  const payload = {
    name: data.name,
    slug: data.slug || null,
    description: data.description || null,
  };
  await runAction(async () => {
    const copiedProject = await api.copyProject(project.id, payload);
    state.selectedProjectId = copiedProject.id;
    state.selectedVersionId = null;
    localStorage.setItem(SELECTED_PROJECT_KEY, copiedProject.id);
    localStorage.removeItem(SELECTED_VERSION_KEY);
    state.modal = null;
    await refreshAll();
    notify("Project copied");
  });
}

async function submitDeleteProjectForm(event) {
  event.preventDefault();
  const project = currentProject();
  if (!project) return;
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  if ((data.confirm_name || "") !== project.name) {
    notify("Project name does not match");
    return;
  }
  await runAction(async () => {
    await api.deleteProject(project.id);
    state.selectedProjectId = null;
    state.selectedVersionId = null;
    state.selectedJobId = null;
    state.files = [];
    state.projectArtifacts = [];
    state.versionArtifacts = [];
    state.jobLogs = [];
    localStorage.removeItem(SELECTED_PROJECT_KEY);
    localStorage.removeItem(SELECTED_VERSION_KEY);
    localStorage.removeItem(SELECTED_JOB_KEY);
    state.modal = null;
    await refreshAll();
    notify("Project deleted");
  });
}

async function submitLocalImportForm(event) {
  event.preventDefault();
  const files = state.modal?.uploadedFiles || [];
  if (!files.length) {
    notify("Choose a project folder first");
    return;
  }
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file, file.webkitRelativePath || file.name);
  }
  formData.append("project_id", data.project_id || "");
  formData.append("project_name", data.project_name || "");
  formData.append("label", data.label || "manual import");
  await runAction(async () => {
    const result = await api.importUpload(formData);
    state.selectedProjectId = result.project.id;
    state.selectedVersionId = result.version.id;
    localStorage.setItem(SELECTED_PROJECT_KEY, result.project.id);
    localStorage.setItem(SELECTED_VERSION_KEY, result.version.id);
    state.modal = null;
    await refreshAll();
    notify("Local project imported");
  });
}

function onLocalImportFolderChange(event) {
  const files = Array.from(event.target.files || []);
  state.modal = {
    ...(state.modal || {}),
    type: "local-import",
    uploadedFiles: files,
    detectedFolderName: detectUploadedFolderName(files),
  };
  render();
}

function detectUploadedFolderName(files) {
  const relativePath = files.find((file) => file.webkitRelativePath)?.webkitRelativePath || "";
  return relativePath.split("/").filter(Boolean)[0] || "";
}

async function submitVersionForm(event) {
  event.preventDefault();
  const project = currentProject();
  if (!project) return;
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  let manifest = {};
  try {
    manifest = data.manifest ? JSON.parse(data.manifest) : {};
  } catch {
    notify("Invalid manifest JSON");
    return;
  }
  await runAction(async () => {
    const version = await api.createVersion(project.id, {
      label: data.label || null,
      base_version_id: state.selectedVersionId || null,
      manifest,
    });
    state.selectedVersionId = version.id;
    localStorage.setItem(SELECTED_VERSION_KEY, version.id);
    state.modal = null;
    await loadProject(project.id);
    notify("Version created");
  });
}

async function submitApprovalForm(event) {
  event.preventDefault();
  const version = currentVersion();
  if (!version) return;
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  const comment = data.comment || "";
  await runAction(async () => {
    if (state.modal.approvalAction === "approve") await api.approveVersion(version.id, comment);
    else if (state.modal.approvalAction === "reject") await api.rejectVersion(version.id, comment);
    else await api.submitVersion(version.id, comment);
    state.modal = null;
    await loadProject(version.project_id);
    notify("Review state updated");
  });
}

async function submitModuleJobForm(event) {
  event.preventDefault();
  const kind = state.modal?.kind || "";
  const config = getModuleJobConfig(kind);
  if (!config) return;
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  state.modal = null;
  render();
  await startJob(kind, {
    schema: data.schema || null,
    version_label: data.version_label || config.defaultLabel,
  });
}

async function submitFileJobForm(event) {
  event.preventDefault();
  const kind = state.modal?.kind || "";
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  if (kind === "convert_sap_to_bit_xml") {
    state.modal = null;
    render();
    await startJob(kind, {
      etk_file: data.etk_file || null,
      output_file: data.output_file || null,
    });
    return;
  }
  if (kind === "convert_opmanual_to_bit_xml") {
    const opmanualFiles = String(data.opmanual_files || "")
      .replaceAll(",", "\n")
      .split("\n")
      .map((value) => value.trim())
      .filter(Boolean);
    if (!opmanualFiles.length) {
      notify("Enter at least one opmanual XML path");
      return;
    }
    state.modal = null;
    render();
    await startJob(kind, {
      opmanual_files: opmanualFiles,
    });
  }
}

async function startJob(kind, overrides = {}) {
  const project = currentProject();
  const version = currentVersion();
  if (!project || !version) return;
  const parameters = {
    language: state.language,
    ...overrides,
  };

  await runAction(async () => {
    const job = await api.createJob({
      project_id: project.id,
      version_id: version.id,
      kind,
      parameters,
      run_async: true,
    });
    rememberJob(job.id);
    upsertJob(job);
    state.selectedJobId = job.id;
    localStorage.setItem(SELECTED_JOB_KEY, job.id);
    state.jobLogs = [];
    await refreshJob(job.id);
    notify("Job queued");
  });
}

async function selectProject(projectId) {
  state.selectedProjectId = projectId;
  state.openMenu = null;
  localStorage.setItem(SELECTED_PROJECT_KEY, projectId);
  await loadProject(projectId);
  render();
}

async function selectVersion(versionId) {
  state.selectedVersionId = versionId;
  state.openMenu = null;
  localStorage.setItem(SELECTED_VERSION_KEY, versionId);
  await loadVersion(versionId);
  render();
}

async function selectJob(jobId) {
  state.selectedJobId = jobId;
  state.openMenu = null;
  localStorage.setItem(SELECTED_JOB_KEY, jobId);
  state.jobLogs = [];
  await refreshJob(jobId);
  render();
}

async function refreshAll() {
  await runAction(async () => {
    state.health = await api.health();
    state.projects = await api.listProjects();
    if (!state.projects.some((project) => project.id === state.selectedProjectId)) {
      state.selectedProjectId = state.projects[0]?.id || null;
      if (state.selectedProjectId) localStorage.setItem(SELECTED_PROJECT_KEY, state.selectedProjectId);
    }
    if (state.selectedProjectId) await loadProject(state.selectedProjectId);
    await refreshRecentJobs();
  }, { silent: true });
}

async function loadProject(projectId) {
  state.versions = await api.listVersions(projectId);
  if (!state.versions.some((version) => version.id === state.selectedVersionId)) {
    state.selectedVersionId = state.versions[0]?.id || null;
    if (state.selectedVersionId) localStorage.setItem(SELECTED_VERSION_KEY, state.selectedVersionId);
  }
  state.projectArtifacts = await api.listProjectArtifacts(projectId);
  if (state.selectedVersionId) await loadVersion(state.selectedVersionId);
  else {
    state.files = [];
    state.versionArtifacts = [];
  }
}

async function loadVersion(versionId) {
  state.files = await api.listVersionFiles(versionId);
  state.versionArtifacts = await api.listVersionArtifacts(versionId);
}

async function refreshRecentJobs() {
  const ids = loadRecentJobs();
  const jobs = [];
  for (const id of ids) {
    try {
      jobs.push(await api.getJob(id));
    } catch {
      // Old jobs may have been removed with a local database reset.
    }
  }
  state.jobs = jobs;
  if (!state.jobs.some((job) => job.id === state.selectedJobId)) {
    state.selectedJobId = state.jobs[0]?.id || null;
    if (state.selectedJobId) localStorage.setItem(SELECTED_JOB_KEY, state.selectedJobId);
  }
  if (state.selectedJobId) await refreshJob(state.selectedJobId);
  render();
}

async function refreshJob(jobId) {
  const job = await api.getJob(jobId);
  upsertJob(job);
  const logs = await api.getJobLogs(jobId);
  state.jobLogs = logs.items || [];
  if (["succeeded", "failed", "canceled"].includes(job.status) && state.selectedProjectId === job.project_id) {
    const previousVersionId = state.selectedVersionId;
    await loadProject(job.project_id);
    const producedVersionId = job.parameters?.produced_version_id || null;
    if (producedVersionId && producedVersionId !== previousVersionId) {
      const producedVersion = state.versions.find((version) => version.id === producedVersionId);
      if (producedVersion) {
        state.selectedVersionId = producedVersion.id;
        localStorage.setItem(SELECTED_VERSION_KEY, producedVersion.id);
        await loadVersion(producedVersion.id);
        notify(`Created version #${producedVersion.version_number}`);
      }
    }
  }
}

function upsertJob(job) {
  const index = state.jobs.findIndex((item) => item.id === job.id);
  if (index >= 0) state.jobs[index] = job;
  else state.jobs.unshift(job);
}

function rememberJob(jobId) {
  const ids = loadRecentJobs().filter((id) => id !== jobId);
  ids.unshift(jobId);
  localStorage.setItem(RECENT_JOBS_KEY, JSON.stringify(ids.slice(0, 24)));
}

function loadRecentJobs() {
  try {
    const value = JSON.parse(localStorage.getItem(RECENT_JOBS_KEY) || "[]");
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

async function runAction(fn, options = {}) {
  state.busy = true;
  render();
  try {
    await fn();
  } catch (error) {
    notify(error.message || "Action failed");
  } finally {
    state.busy = false;
    if (!options.skipRender) render();
  }
}

function notify(message) {
  state.toast = message;
  render();
  window.clearTimeout(notify.timeout);
  notify.timeout = window.setTimeout(() => {
    state.toast = null;
    render();
  }, 3200);
}

window.setInterval(async () => {
  const job = currentJob();
  if (!job || !["queued", "running", "cancel_requested"].includes(job.status)) return;
  try {
    await refreshJob(job.id);
    render();
  } catch {
    // Keep polling quiet; explicit refresh will surface connection errors.
  }
}, 2500);

render();
refreshAll();
