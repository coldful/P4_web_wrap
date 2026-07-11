import { api, getApiBase, setApiBase } from "../src/api.js?v=20260711-reduced1";
import { MODULE_JOB_SCHEMAS } from "../src/job-config.js?v=20260711-reduced1";
import {
  escapeHtml,
  formatBytes,
  formatDate,
  statusBadge,
} from "../src/utils.js?v=20260711-reduced1";
import { icon } from "../src/icons.js?v=20260711-reduced1";

const RECENT_JOBS_KEY = "p4web.reduced.recentJobs";
const SELECTED_PROJECT_KEY = "p4web.reduced.selectedProjectId";
const SELECTED_JOB_KEY = "p4web.reduced.selectedJobId";
const SELECTED_SERVICE_KEY = "p4web.reduced.selectedService";
const LANGUAGE_KEY = "p4web.reduced.language";

const SERVICES = [
  {
    id: "import",
    visual: "import",
    icon: "gtk-open.png",
    title: "Open project folder",
    subtitle: "Import one legacy project folder and keep working with its latest snapshot.",
    heading: "Import or refresh one project",
    description:
      "Bring one local legacy project into the reduced workspace. Existing imports stay available as simple project entries.",
  },
  {
    id: "documents",
    visual: "documents",
    icon: "000pp013.bmp",
    title: "PDF and HTML",
    subtitle: "Run the main publishing outputs without opening the full control workspace.",
    heading: "Document outputs",
    description:
      "Use the latest imported snapshot and launch the same core PDF and HTML operations that matter in day-to-day legacy work.",
  },
  {
    id: "translation",
    visual: "translation",
    icon: "000pp010.bmp",
    title: "Translation export",
    subtitle: "Prepare a translation package from the current snapshot in one step.",
    heading: "Translation package",
    description:
      "Keep the reduced workspace focused on operational publishing: choose the language once and export the package directly.",
  },
  {
    id: "modules",
    visual: "modules",
    icon: "000pp008.bmp",
    title: "Text modules",
    subtitle: "Pack or unpack text modules with the schema you need for the selected project.",
    heading: "Text module tools",
    description:
      "Run the main text module transformations without exposing project version management or approval workflow screens.",
  },
  {
    id: "quality",
    visual: "quality",
    icon: "300pp033.bmp",
    title: "Lists and checks",
    subtitle: "Generate lists or run index checks against the current snapshot.",
    heading: "Source checks",
    description:
      "Use the compact tool surface for list generation and index validation while keeping the project model hidden in the background.",
  },
];

const LANGUAGES = ["de", "en", "fr", "es", "pt", "ru", "zh"];

const state = {
  health: null,
  projects: [],
  versions: [],
  files: [],
  artifacts: [],
  jobs: [],
  jobLogs: [],
  selectedProjectId: localStorage.getItem(SELECTED_PROJECT_KEY),
  selectedJobId: localStorage.getItem(SELECTED_JOB_KEY),
  selectedServiceId: localStorage.getItem(SELECTED_SERVICE_KEY) || "documents",
  selectedVersionId: null,
  language: localStorage.getItem(LANGUAGE_KEY) || "de",
  moduleSchema: MODULE_JOB_SCHEMAS[0]?.[0] || "proced.xsd",
  modal: null,
  toast: null,
  busy: false,
};

const root = document.getElementById("reduced-app");

function currentProject() {
  return state.projects.find((project) => project.id === state.selectedProjectId) || null;
}

function currentVersion() {
  return state.versions.find((version) => version.id === state.selectedVersionId) || null;
}

function currentJob() {
  return state.jobs.find((job) => job.id === state.selectedJobId) || null;
}

function currentService() {
  return SERVICES.find((service) => service.id === state.selectedServiceId) || SERVICES[0];
}

function isProjectReady() {
  return Boolean(currentProject() && currentVersion());
}

function reducedLegacyIcon(fileName, className = "") {
  return `<img class="${className}" src="../src/legacy-images/${fileName}" alt="" aria-hidden="true" />`;
}

function render() {
  root.innerHTML = `
    <div class="reduced-shell">
      ${renderTopbar()}
      <main class="main-content">
        ${renderHero()}
        ${renderServiceGrid()}
        <section class="workspace-grid">
          ${renderProjectPanel()}
          ${renderActionPanel()}
          ${renderActivityPanel()}
        </section>
      </main>
      ${state.toast ? `<div class="toast">${escapeHtml(state.toast)}</div>` : ""}
      ${state.modal ? renderModal() : ""}
      ${state.busy ? renderBusy() : ""}
    </div>
  `;
  bindEvents();
}

function renderTopbar() {
  const health = state.health?.status || "offline";
  return `
    <header class="reduced-topbar">
      <div class="reduced-brand">
        <div class="reduced-brand-mark"><strong>P4</strong></div>
        <div class="reduced-brand-copy">
          <strong>Reduced Workspace</strong>
          <span>${statusBadge(health)} Main legacy operations without version control screens</span>
        </div>
      </div>
      <div></div>
      <div class="reduced-connection">
        <div class="reduced-api-box">
          <input id="api-base-input" class="top-input" value="${escapeHtml(getApiBase())}" aria-label="API base" />
          <button class="cta" data-action="save-api-base">${icon("database")} Connect</button>
        </div>
        <button class="top-pill" data-action="refresh">${icon("refresh")} Refresh</button>
      </div>
    </header>
  `;
}

function renderHero() {
  const service = currentService();
  const steps = [
    {
      id: "service",
      title: "Choose a service",
      text: service.title,
      state: service ? "done" : "active",
    },
    {
      id: "project",
      title: "Select a project",
      text: currentProject() ? currentProject().name : "Pick one imported project",
      state: currentProject() ? "done" : service ? "active" : "",
    },
    {
      id: "run",
      title: "Run and review",
      text: currentJob() ? `${currentJob().kind} ${currentJob().status}` : "Launch a job and download results",
      state: currentJob() ? "done" : isProjectReady() ? "active" : "",
    },
  ];
  return `
    <section class="hero-card">
      <div class="hero-head">
        <div class="hero-title-block">
          <div class="breadcrumbs">
            <span>P4</span>
            <span>/</span>
            <span>Reduced workspace</span>
            <span>/</span>
            <span>${escapeHtml(service.title)}</span>
          </div>
          <h1 class="hero-title">Legacy publishing, trimmed to the essentials</h1>
          <p class="hero-copy">
            Import one project folder, keep only the latest working snapshot, and run the primary legacy publishing actions from a smaller front end.
          </p>
        </div>
      </div>
      <div class="hero-stepper">
        ${steps.map((step, index) => `
          <div class="step-chip ${step.state}">
            <div class="step-head">
              <div class="step-bullet"><span>${index + 1}</span></div>
              <div class="step-text">
                <strong>${escapeHtml(step.title)}</strong>
                <span>${escapeHtml(step.text)}</span>
              </div>
            </div>
          </div>
        `).join("")}
      </div>
    </section>
  `;
}

function renderServiceGrid() {
  return `
    <section class="service-grid">
      ${SERVICES.map((service) => `
        <button
          class="service-card ${service.id === state.selectedServiceId ? "active" : ""}"
          data-service-id="${escapeHtml(service.id)}"
          title="${escapeHtml(service.title)}"
        >
          <div class="service-visual ${service.visual}">
            <div class="service-badge">${reducedLegacyIcon(service.icon)}</div>
          </div>
          <div class="service-body">
            <strong>${escapeHtml(service.title)}</strong>
            <p>${escapeHtml(service.subtitle)}</p>
          </div>
        </button>
      `).join("")}
    </section>
  `;
}

function renderProjectPanel() {
  const project = currentProject();
  const version = currentVersion();
  return `
    <aside class="project-list-card">
      <div class="card-head">
        <div>
          <h2>Projects</h2>
          <p>Latest imported snapshot only. Version history stays hidden here.</p>
        </div>
        <button class="secondary" data-action="open-import">${icon("upload")} Import</button>
      </div>
      <div class="card-body">
        ${project ? `
          <div class="project-summary">
            <strong>${escapeHtml(project.name)}</strong>
            <div class="summary-list">
              <div class="summary-row"><span>Snapshot</span><b>${version ? `#${version.version_number}` : "none"}</b></div>
              <div class="summary-row"><span>Files</span><b>${state.files.length}</b></div>
              <div class="summary-row"><span>Artifacts</span><b>${state.artifacts.length}</b></div>
              <div class="summary-row"><span>Language</span><b>${escapeHtml(state.language.toUpperCase())}</b></div>
            </div>
          </div>
        ` : `
          <div class="empty-state">Import a project folder or pick one existing project to begin.</div>
        `}
        <div class="project-stack">
          ${state.projects.map((item) => `
            <button class="project-item ${item.id === state.selectedProjectId ? "active" : ""}" data-project-id="${escapeHtml(item.id)}">
              <strong>${escapeHtml(item.name)}</strong>
              <span>${escapeHtml(item.slug)}</span>
              <span>${formatDate(item.updated_at) || "No update time"}</span>
            </button>
          `).join("") || `<div class="empty-state">No imported projects yet.</div>`}
        </div>
      </div>
    </aside>
  `;
}

function renderActionPanel() {
  const service = currentService();
  const project = currentProject();
  const version = currentVersion();
  return `
    <section class="action-panel">
      <div class="card-head">
        <div class="service-copy">
          <h2>${escapeHtml(service.heading)}</h2>
          <p>${escapeHtml(service.description)}</p>
        </div>
        <div class="status-strip">${project ? escapeHtml(project.name) : "No project selected"}</div>
      </div>
      <div class="card-body">
        <div class="field-grid">
          <div class="field">
            <label>Workspace language</label>
            <div class="chip-row">
              ${LANGUAGES.map((language) => `
                <button class="chip-button ${state.language === language ? "active" : ""}" data-language="${language}">
                  ${escapeHtml(language.toUpperCase())}
                </button>
              `).join("")}
            </div>
          </div>
          ${project && version ? `
            <div class="field-help">
              Running against snapshot #${version.version_number}${version.label ? ` (${escapeHtml(version.label)})` : ""}.
            </div>
          ` : `
            <div class="field-help">Choose or import one project to unlock publishing actions.</div>
          `}
        </div>
        ${renderServiceBody(service.id)}
      </div>
    </section>
  `;
}

function renderServiceBody(serviceId) {
  const disabled = isProjectReady() ? "" : "disabled";
  if (serviceId === "import") {
    return `
      <div class="action-grid">
        <div class="action-tile">
          <strong>Import one local folder</strong>
          <p>Upload a complete legacy project folder from your machine and keep the newest snapshot selected automatically.</p>
          <button class="cta" data-action="open-import">${icon("folder")} Choose folder</button>
        </div>
        <div class="action-tile">
          <strong>Reuse an imported project</strong>
          <p>Select any project from the left panel. The reduced workspace always binds itself to the latest available snapshot.</p>
          <button class="secondary" data-action="focus-projects">Review projects</button>
        </div>
      </div>
    `;
  }
  if (serviceId === "documents") {
    return `
      <div class="action-grid">
        ${actionTile("Standard PDF", "Run the main legacy PDF pipeline on the current snapshot.", "generate_pdf", disabled)}
        ${actionTile("TeXML PDF", "Use the new TeXML helper path while keeping the rest of the workspace reduced.", "texml_pdf", disabled)}
        ${actionTile("XSL-FO PDF", "Run the dedicated XSL-FO helper and collect the generated PDF artifact.", "xsl_fo", disabled)}
        ${actionTile("HTML", "Generate HTML output from the selected project snapshot.", "generate_html", disabled)}
      </div>
    `;
  }
  if (serviceId === "translation") {
    return `
      <div class="action-grid">
        ${actionTile("Export translation", "Prepare one translation package for the currently selected language.", "export_translation", disabled)}
        <div class="action-tile">
          <strong>Focused scope</strong>
          <p>The reduced workspace keeps translation work to artifact export and leaves project version flow in the full client.</p>
          <button class="ghost" disabled>Import stays in full workspace</button>
        </div>
      </div>
    `;
  }
  if (serviceId === "modules") {
    return `
      <div class="field">
        <label for="module-schema-select">Schema</label>
        <select id="module-schema-select" class="field-select">
          ${MODULE_JOB_SCHEMAS.map(([value, label]) => `
            <option value="${escapeHtml(value)}" ${state.moduleSchema === value ? "selected" : ""}>${escapeHtml(label)}</option>
          `).join("")}
        </select>
      </div>
      <div class="action-grid">
        ${actionTile("Pack modules", "Bundle text modules using the selected schema.", "pack_modules", disabled, true)}
        ${actionTile("Unpack modules", "Expand text modules using the selected schema.", "unpack_modules", disabled, true)}
      </div>
    `;
  }
  return `
    <div class="action-grid">
      ${actionTile("Generate lists", "Create source lists on the selected snapshot and switch to the produced result automatically.", "generate_lists", disabled)}
      ${actionTile("Check index", "Apply the legacy index repair rules to the current snapshot.", "check_index", disabled)}
    </div>
  `;
}

function actionTile(title, text, kind, disabled, needsSchema = false) {
  return `
    <div class="action-tile">
      <strong>${escapeHtml(title)}</strong>
      <p>${escapeHtml(text)}</p>
      <button class="cta" data-job-kind="${escapeHtml(kind)}" data-job-schema="${needsSchema ? "1" : ""}" ${disabled}>
        ${icon("play")} Run
      </button>
    </div>
  `;
}

function renderActivityPanel() {
  const project = currentProject();
  const jobs = project ? state.jobs.filter((job) => job.project_id === project.id) : state.jobs;
  return `
    <aside class="activity-panel">
      <div class="card-head">
        <div>
          <h3>Results and activity</h3>
          <p>Download produced files and keep an eye on recent reduced-workspace jobs.</p>
        </div>
      </div>
      <div class="card-body">
        <section class="list-block">
          <strong>Artifacts</strong>
          ${state.artifacts.slice(0, 8).map((artifact) => `
            <button class="artifact-button" data-artifact-id="${escapeHtml(artifact.id)}">
              ${icon("download")}
              <span>
                <strong>${escapeHtml(artifact.path)}</strong>
                <small>${escapeHtml(artifact.kind)} · ${formatBytes(artifact.size_bytes)} · ${formatDate(artifact.created_at)}</small>
              </span>
            </button>
          `).join("") || `<div class="empty-state">No artifacts yet for the current snapshot.</div>`}
        </section>
        <section class="list-block">
          <strong>Files in current snapshot</strong>
          ${state.files.slice(0, 8).map((file) => `
            <button class="project-link" data-file-id="${escapeHtml(file.id)}">
              ${icon("file")}
              <span>
                <strong>${escapeHtml(file.path)}</strong>
                <small>${escapeHtml(file.role)} · ${formatBytes(file.size_bytes)}</small>
              </span>
            </button>
          `).join("") || `<div class="empty-state">No files loaded for the current project.</div>`}
        </section>
        <section class="list-block">
          <strong>Recent jobs</strong>
          ${jobs.slice(0, 6).map((job) => `
            <button class="project-link" data-job-id="${escapeHtml(job.id)}">
              ${icon("clock")}
              <span>
                <strong>${escapeHtml(job.kind)}</strong>
                <small>${job.status ? statusBadge(job.status) : ""} ${formatDate(job.updated_at)}</small>
              </span>
            </button>
          `).join("") || `<div class="empty-state">No recent jobs remembered in this browser yet.</div>`}
        </section>
        <section class="list-block">
          <strong>Current log</strong>
          ${renderCurrentLogs()}
        </section>
      </div>
    </aside>
  `;
}

function renderCurrentLogs() {
  const job = currentJob();
  if (!job) return `<div class="empty-state">Run a job to populate the live log stream here.</div>`;
  if (!state.jobLogs.length) return `<div class="empty-state">No log lines loaded for the selected job.</div>`;
  return state.jobLogs.slice(-10).map((log) => `
    <div class="list-item">
      <strong>${escapeHtml(log.level.toUpperCase())}</strong>
      <small>${formatDate(log.created_at)}</small>
      <div>${escapeHtml(log.message)}</div>
    </div>
  `).join("");
}

function renderModal() {
  if (state.modal?.type !== "import") return "";
  const targetOptions = [
    ["", "Create new project"],
    ...state.projects.map((project) => [project.id, project.name]),
  ];
  const files = state.modal.files || [];
  return `
    <div class="modal-backdrop">
      <form class="modal-card" id="import-form">
        <div class="modal-header">
          <div>
            <h2>Import project folder</h2>
            <p>Choose one local project folder and import it as the latest snapshot for a new or existing project.</p>
          </div>
          <button class="ghost" type="button" data-action="close-modal">${icon("x")} Close</button>
        </div>
        <div class="modal-body">
          <input id="folder-input" type="file" webkitdirectory directory multiple hidden />
          <div class="field">
            <label>Folder</label>
            <div class="folder-picker">
              <button class="secondary" type="button" data-action="browse-folder">${icon("folder")} Choose folder</button>
              <div class="folder-meta">
                <strong>${escapeHtml(state.modal.folderName || "No folder selected")}</strong>
                <span>${files.length ? `${files.length} files will be uploaded with subfolders` : "Pick the complete project folder from your computer."}</span>
              </div>
            </div>
          </div>
          <div class="field">
            <label for="import-target">Target project</label>
            <select id="import-target" name="project_id" class="field-select">
              ${targetOptions.map(([value, label]) => `
                <option value="${escapeHtml(value)}" ${state.modal.projectId === value ? "selected" : ""}>${escapeHtml(label)}</option>
              `).join("")}
            </select>
          </div>
          <div class="field">
            <label for="import-project-name">Project name</label>
            <input
              id="import-project-name"
              name="project_name"
              class="field-input"
              value="${escapeHtml(state.modal.projectName || state.modal.folderName || "")}"
              placeholder="Used when creating a new project"
            />
          </div>
          <div class="field">
            <label for="import-label">Snapshot label</label>
            <input
              id="import-label"
              name="label"
              class="field-input"
              value="${escapeHtml(state.modal.label || "manual import")}"
            />
          </div>
        </div>
        <div class="modal-footer">
          <button class="ghost" type="button" data-action="close-modal">Cancel</button>
          <button class="cta" type="submit">${icon("upload")} Import folder</button>
        </div>
      </form>
    </div>
  `;
}

function renderBusy() {
  return `
    <div class="busy-cover">
      <div class="busy-pill">
        <span class="spinner"></span>
        <span>Working with the reduced workspace...</span>
      </div>
    </div>
  `;
}

function bindEvents() {
  root.querySelectorAll("[data-service-id]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedServiceId = button.dataset.serviceId;
      localStorage.setItem(SELECTED_SERVICE_KEY, state.selectedServiceId);
      render();
    });
  });
  root.querySelectorAll("[data-language]").forEach((button) => {
    button.addEventListener("click", () => {
      state.language = button.dataset.language;
      localStorage.setItem(LANGUAGE_KEY, state.language);
      render();
    });
  });
  root.querySelectorAll("[data-project-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      await selectProject(button.dataset.projectId);
    });
  });
  root.querySelectorAll("[data-job-kind]").forEach((button) => {
    button.addEventListener("click", async () => {
      const parameters = {};
      if (button.dataset.jobSchema) parameters.schema = state.moduleSchema;
      await startJob(button.dataset.jobKind, parameters);
    });
  });
  root.querySelectorAll("[data-artifact-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      await downloadArtifact(button.dataset.artifactId);
    });
  });
  root.querySelectorAll("[data-file-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      await downloadFile(button.dataset.fileId);
    });
  });
  root.querySelectorAll("[data-job-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      await selectJob(button.dataset.jobId);
    });
  });
  root.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", onAction);
  });
  root.querySelector("#module-schema-select")?.addEventListener("change", (event) => {
    state.moduleSchema = event.target.value;
  });
  root.querySelector("#import-form")?.addEventListener("submit", submitImportForm);
  root.querySelector("#folder-input")?.addEventListener("change", onFolderChange);
  root.querySelector("#import-target")?.addEventListener("change", (event) => {
    state.modal = {
      ...(state.modal || {}),
      projectId: event.target.value,
    };
  });
  root.querySelector("#import-project-name")?.addEventListener("input", (event) => {
    state.modal = {
      ...(state.modal || {}),
      projectName: event.target.value,
    };
  });
  root.querySelector("#import-label")?.addEventListener("input", (event) => {
    state.modal = {
      ...(state.modal || {}),
      label: event.target.value,
    };
  });
}

async function onAction(event) {
  const action = event.currentTarget.dataset.action;
  if (!action) return;
  if (action === "save-api-base") {
    await saveApiBase();
    return;
  }
  if (action === "refresh") {
    await refreshAll();
    return;
  }
  if (action === "open-import") {
    state.modal = {
      type: "import",
      files: [],
      folderName: "",
      label: "manual import",
      projectId: "",
      projectName: "",
    };
    render();
    return;
  }
  if (action === "close-modal") {
    state.modal = null;
    render();
    return;
  }
  if (action === "browse-folder") {
    root.querySelector("#folder-input")?.click();
    return;
  }
  if (action === "focus-projects") {
    root.querySelector(".project-stack")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

async function saveApiBase() {
  const input = root.querySelector("#api-base-input");
  setApiBase(input?.value || "");
  notify("API base updated");
  await refreshAll();
}

function onFolderChange(event) {
  const files = Array.from(event.target.files || []);
  const folderName = detectFolderName(files);
  state.modal = {
    ...(state.modal || {}),
    type: "import",
    files,
    folderName,
    projectName: state.modal?.projectName || folderName,
  };
  render();
}

function detectFolderName(files) {
  const relativePath = files.find((file) => file.webkitRelativePath)?.webkitRelativePath || "";
  return relativePath.split("/").filter(Boolean)[0] || "";
}

async function submitImportForm(event) {
  event.preventDefault();
  const files = state.modal?.files || [];
  if (!files.length) {
    notify("Choose a project folder first");
    return;
  }
  const form = new FormData(event.currentTarget);
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file, file.webkitRelativePath || file.name);
  }
  formData.append("project_id", String(form.get("project_id") || ""));
  formData.append("project_name", String(form.get("project_name") || ""));
  formData.append("label", String(form.get("label") || "manual import"));

  await runAction(async () => {
    const result = await api.importUpload(formData);
    state.modal = null;
    state.selectedProjectId = result.project.id;
    state.selectedVersionId = result.version.id;
    localStorage.setItem(SELECTED_PROJECT_KEY, result.project.id);
    await refreshAll();
    notify(`Imported ${result.project.name}`);
  });
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
    else {
      state.versions = [];
      state.selectedVersionId = null;
      state.files = [];
      state.artifacts = [];
    }
    await refreshRecentJobs();
  }, { silent: true });
}

async function loadProject(projectId) {
  const versions = await api.listVersions(projectId);
  state.versions = [...versions].sort((left, right) => right.version_number - left.version_number);
  state.selectedVersionId = state.versions[0]?.id || null;
  if (state.selectedVersionId) {
    state.files = await api.listVersionFiles(state.selectedVersionId);
    state.artifacts = await api.listVersionArtifacts(state.selectedVersionId);
  } else {
    state.files = [];
    state.artifacts = [];
  }
}

async function selectProject(projectId) {
  if (!projectId) return;
  state.selectedProjectId = projectId;
  localStorage.setItem(SELECTED_PROJECT_KEY, projectId);
  await runAction(async () => {
    await loadProject(projectId);
  }, { silent: true });
}

async function startJob(kind, overrides = {}) {
  const project = currentProject();
  const version = currentVersion();
  if (!project || !version) {
    notify("Choose a project first");
    return;
  }
  await runAction(async () => {
    const job = await api.createJob({
      project_id: project.id,
      version_id: version.id,
      kind,
      parameters: {
        language: state.language,
        ...overrides,
      },
      run_async: true,
    });
    rememberJob(job.id);
    upsertJob(job);
    state.selectedJobId = job.id;
    localStorage.setItem(SELECTED_JOB_KEY, job.id);
    state.jobLogs = [];
    await refreshJob(job.id);
    notify(`${kind} queued`);
  });
}

async function refreshRecentJobs() {
  const ids = loadRecentJobs();
  const jobs = [];
  for (const id of ids) {
    try {
      jobs.push(await api.getJob(id));
    } catch {
      // Ignore reset or deleted jobs.
    }
  }
  state.jobs = jobs.sort((left, right) => String(right.updated_at).localeCompare(String(left.updated_at)));
  if (!state.jobs.some((job) => job.id === state.selectedJobId)) {
    state.selectedJobId = state.jobs[0]?.id || null;
    if (state.selectedJobId) localStorage.setItem(SELECTED_JOB_KEY, state.selectedJobId);
  }
  if (state.selectedJobId) await refreshJob(state.selectedJobId);
}

async function selectJob(jobId) {
  if (!jobId) return;
  state.selectedJobId = jobId;
  localStorage.setItem(SELECTED_JOB_KEY, jobId);
  await runAction(async () => {
    await refreshJob(jobId);
  }, { silent: true });
}

async function refreshJob(jobId) {
  const job = await api.getJob(jobId);
  upsertJob(job);
  const logs = await api.getJobLogs(jobId);
  state.jobLogs = logs.items || [];
  if (["succeeded", "failed", "canceled"].includes(job.status) && job.project_id === state.selectedProjectId) {
    const producedVersionId = job.parameters?.produced_version_id || null;
    await loadProject(job.project_id);
    if (producedVersionId && state.versions.some((version) => version.id === producedVersionId)) {
      state.selectedVersionId = producedVersionId;
      state.files = await api.listVersionFiles(producedVersionId);
      state.artifacts = await api.listVersionArtifacts(producedVersionId);
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

async function downloadArtifact(artifactId) {
  const artifact = state.artifacts.find((item) => item.id === artifactId);
  if (!artifact) return;
  await runAction(async () => {
    await api.downloadFromUrl(api.artifactDownloadUrl(artifact.id), artifact.path.split("/").pop() || "artifact");
  });
}

async function downloadFile(fileId) {
  const version = currentVersion();
  const file = state.files.find((item) => item.id === fileId);
  if (!version || !file) return;
  await runAction(async () => {
    await api.downloadFromUrl(
      api.versionFileDownloadUrl(version.id, file.id),
      file.path.split("/").pop() || "file",
    );
  });
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
    render();
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
    // Keep polling quiet in the reduced client too.
  }
}, 2500);

render();
refreshAll();
