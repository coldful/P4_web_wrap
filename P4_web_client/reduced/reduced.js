import { api } from "../src/api.js?v=20260712-server-import1";
import { MODULE_JOB_SCHEMAS } from "../src/job-config.js?v=20260711-reduced1";
import {
  escapeHtml,
  formatBytes,
  formatDate,
  statusBadge,
} from "../src/utils.js?v=20260711-reduced1";
import { icon } from "../src/icons.js?v=20260712-reduced2";

const RECENT_JOBS_KEY = "p4web.reduced.recentJobs";
const SELECTED_PROJECT_KEY = "p4web.reduced.selectedProjectId";
const SELECTED_JOB_KEY = "p4web.reduced.selectedJobId";
const LOG_JOB_KEY = "p4web.reduced.logJobId";
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
  jobLogsJobId: null,
  jobLogsLoading: false,
  screen: "menu",
  selectedProjectId: localStorage.getItem(SELECTED_PROJECT_KEY),
  selectedJobId: localStorage.getItem(SELECTED_JOB_KEY),
  logJobId: localStorage.getItem(LOG_JOB_KEY),
  selectedServiceId: localStorage.getItem(SELECTED_SERVICE_KEY) || "documents",
  selectedVersionId: null,
  language: localStorage.getItem(LANGUAGE_KEY) || "de",
  moduleSchema: MODULE_JOB_SCHEMAS[0]?.[0] || "proced.xsd",
  modal: null,
  projectMenuId: null,
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

function jobsForCurrentProject() {
  const project = currentProject();
  return project ? state.jobs.filter((job) => job.project_id === project.id) : state.jobs;
}

function isProjectReady() {
  return Boolean(currentProject() && currentVersion());
}

function reducedLegacyIcon(fileName, className = "") {
  return `<img class="${className}" src="../src/legacy-images/${fileName}" alt="" aria-hidden="true" />`;
}

const DELIVERY_FLOW = [
  { status: 1, id: "new", label: "Captured" },
  { status: 2, id: "in_work", label: "In Work" },
  { status: 3, id: "freigegeben", label: "Released" },
  { status: 4, id: "in_translation", label: "In Translation" },
  { status: 5, id: "closed", label: "Closed" },
];

function deliveryStepsFromState(deliveryState) {
  const steps = Array.isArray(deliveryState?.steps) && deliveryState.steps.length
    ? deliveryState.steps
    : DELIVERY_FLOW;
  return steps.map((step) => ({
    id: step.id || `stage-${step.status}`,
    label: step.label || `Stage ${step.status}`,
    status: step.status,
  }));
}

function deliveryStatusModel(version) {
  const deliveryState = version?.manifest?.delivery_state;
  if (deliveryState) {
    const steps = deliveryStepsFromState(deliveryState);
    const status = Number(deliveryState.status) || 0;
    const currentIndex = status > 0 ? status - 1 : -1;
    let title = "Not started";
    if (status > 0) {
      title = steps[currentIndex]?.label || `Stage ${status}`;
    } else if (!deliveryState.is_activated) {
      title = "Not activated";
    }
    const progress = status > 0 ? Math.round((status / steps.length) * 100) : 0;
    let tone = "work";
    if (deliveryState.is_overdue) {
      tone = "bad";
    } else if (deliveryState.is_complete) {
      tone = "good";
    } else if (!deliveryState.is_activated && status <= 0) {
      tone = "muted";
    }
    let caption = status > 0
      ? `${status} of ${steps.length} delivery stages complete.`
      : "Click to advance delivery status.";
    if (deliveryState.source === "project_sheet" && !deliveryState.has_delivery_status) {
      caption = status > 0
        ? `${status} of ${steps.length} delivery stages complete. Click to advance.`
        : "Click to advance delivery status in the project sheet.";
    }
    if (deliveryState.is_complete) {
      caption = "Delivery status completed. Click to reset.";
    } else if (deliveryState.is_overdue && deliveryState.current_deadline) {
      caption = `Current step overdue since ${deliveryState.current_deadline}. Click to advance.`;
    } else if (deliveryState.current_deadline) {
      caption = `Current step deadline: ${deliveryState.current_deadline}. Click to advance.`;
    } else if (!deliveryState.is_activated && deliveryState.has_delivery_status) {
      caption = "Delivery status is not activated yet. Click to advance.";
    }
    const clickable = Boolean(deliveryState.can_advance && version && !state.busy);
    return {
      title,
      caption,
      progress,
      tone,
      clickable,
      tooltip: clickable ? "Click to advance delivery status" : "",
      steps: steps.map((step, index) => ({
        ...step,
        state: currentIndex < 0
          ? "pending"
          : index < currentIndex
            ? "complete"
            : index === currentIndex
              ? "current"
              : "pending",
      })),
    };
  }

  const legacyDelivery = version?.manifest?.legacy_delivery;
  if (legacyDelivery?.stage) {
    const steps = Array.isArray(legacyDelivery.steps) && legacyDelivery.steps.length
      ? legacyDelivery.steps
      : DELIVERY_FLOW;
    const currentIndex = steps.findIndex((step) => step.id === legacyDelivery.stage);
    if (currentIndex < 0) {
      return {
        title: "Unknown",
        caption: "Legacy project status could not be resolved from the project sheet.",
        progress: 0,
        tone: "muted",
        clickable: false,
        tooltip: "",
        steps: steps.map((step) => ({ ...step, state: "pending" })),
      };
    }
    const progress = Math.round(((currentIndex + 1) / steps.length) * 100);
    return {
      title: steps[currentIndex]?.label || "Captured",
      caption: `${currentIndex + 1} of ${steps.length} inferred workflow stages.`,
      progress,
      tone: legacyDelivery.stage === "closed" ? "good" : "work",
      clickable: false,
      tooltip: "",
      steps: steps.map((step, index) => ({
        ...step,
        state: index < currentIndex ? "complete" : index === currentIndex ? "current" : "pending",
      })),
    };
  }

  if (!version) {
    return {
      title: "No snapshot",
      caption: "Import or select a project snapshot first.",
      progress: 0,
      tone: "idle",
      clickable: false,
      tooltip: "",
      steps: DELIVERY_FLOW.map((step) => ({ ...step, state: "pending" })),
    };
  }

  return {
    title: "Unavailable",
    caption: "Delivery status is not configured in this project sheet.",
    progress: 0,
    tone: "muted",
    clickable: false,
    tooltip: "",
    steps: DELIVERY_FLOW.map((step) => ({ ...step, state: "pending" })),
  };
}

function renderDeliveryProgress(version) {
  const model = deliveryStatusModel(version);
  const clickable = model.clickable;
  return `
    <div
      class="delivery-progress tone-${escapeHtml(model.tone)}${clickable ? " is-clickable" : ""}"
      ${clickable ? 'data-action="advance-delivery-status" role="button" tabindex="0"' : ""}
      ${model.tooltip && clickable ? `title="${escapeHtml(model.tooltip)}"` : ""}
    >
      <div class="delivery-progress-head">
        <span>Delivery status</span>
        <strong>${escapeHtml(model.title)}</strong>
      </div>
      <div class="delivery-progress-track" aria-hidden="true">
        <span class="delivery-progress-fill" style="width: ${model.progress}%;"></span>
        <div class="delivery-progress-points">
          ${model.steps.map((step) => `<span class="delivery-point ${step.state}" title="${escapeHtml(step.label)}"></span>`).join("")}
        </div>
      </div>
      <p class="delivery-progress-caption">${escapeHtml(model.caption)}</p>
    </div>
  `;
}

function render() {
  root.innerHTML = `
    <div class="reduced-shell">
      <main class="main-content">
        ${state.screen === "menu" ? renderMenuScreen() : renderWorkspaceScreen()}
      </main>
      ${state.toast ? `<div class="toast">${escapeHtml(state.toast)}</div>` : ""}
      ${state.modal ? renderModal() : ""}
      ${state.busy ? renderBusy() : ""}
    </div>
  `;
  bindEvents();
}

function renderMenuScreen() {
  return `
    <section class="menu-screen">
      ${renderServiceGrid()}
    </section>
  `;
}

function renderWorkspaceScreen() {
  return `
    <section class="workspace-screen">
      <button class="floating-menu-button" type="button" data-action="back-to-menu">${icon("back")} Menu</button>
      ${renderWorkspaceTopPanel()}
      <section class="workspace-grid">
        ${renderProjectPanel()}
        ${renderActionPanel()}
        ${renderActivityPanel()}
      </section>
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
          aria-label="${escapeHtml(service.title)}"
        >
          <div class="service-visual ${service.visual}">
            <div class="service-badge">${reducedLegacyIcon(service.icon)}</div>
          </div>
          <div class="service-body">
            <strong>${escapeHtml(service.title)}</strong>
            <p class="service-tooltip">${escapeHtml(service.subtitle)}</p>
          </div>
        </button>
      `).join("")}
    </section>
  `;
}

function renderWorkspaceTopPanel() {
  const service = currentService();
  const project = currentProject();
  const version = currentVersion();
  return `
    <section class="workspace-top-panel">
      <div class="workspace-top-head">
        <div class="workspace-top-title">
          <h1>${escapeHtml(service.title)}</h1>
          <p>${escapeHtml(service.subtitle)}</p>
        </div>
      </div>
      <div class="workspace-summary-grid">
        <div class="workspace-summary-card">
          <span>Project</span>
          <strong>${escapeHtml(project?.name || "No project selected")}</strong>
        </div>
        <div class="workspace-summary-card workspace-summary-card-delivery">
          ${renderDeliveryProgress(version)}
        </div>
        <div class="workspace-summary-card">
          <span>Snapshot</span>
          <strong>${version ? `#${version.version_number}` : "none"}</strong>
        </div>
        <div class="workspace-summary-card">
          <span>Artifacts</span>
          <strong>${state.artifacts.length}</strong>
        </div>
        <div class="workspace-summary-card">
          <span>Files</span>
          <strong>${state.files.length}</strong>
        </div>
      </div>
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
            <div class="project-entry ${item.id === state.selectedProjectId ? "active" : ""}">
              <button
                class="project-item ${item.id === state.selectedProjectId ? "active" : ""}"
                data-project-id="${escapeHtml(item.id)}"
                title="Click to select project"
              >
                <strong>${escapeHtml(item.name)}</strong>
                <span>${escapeHtml(item.slug)}</span>
                <span>${formatDate(item.updated_at) || "No update time"}</span>
              </button>
              <button
                class="project-menu-trigger"
                type="button"
                data-action="toggle-project-menu"
                data-project-id="${escapeHtml(item.id)}"
                aria-label="Project actions"
                aria-expanded="${item.id === state.projectMenuId ? "true" : "false"}"
              >
                ${icon("more")}
              </button>
              ${item.id === state.projectMenuId ? `
                <div class="project-menu">
                  <button
                    class="project-menu-item project-menu-item-danger"
                    type="button"
                    data-action="delete-project"
                    data-project-id="${escapeHtml(item.id)}"
                  >
                    ${icon("trash")} Delete project
                  </button>
                </div>
              ` : ""}
            </div>
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
  const jobs = jobsForCurrentProject();
  const artifacts = [...state.artifacts].sort((left, right) => {
    return String(right.created_at || "").localeCompare(String(left.created_at || ""));
  });
  const recentArtifact = artifacts[0] || null;
  const recentJob = jobs[0] || null;
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
          <div class="list-head">
            <strong>Artifacts</strong>
            <button
              class="history-launch ${artifacts.length ? "" : "disabled"}"
              type="button"
              data-action="open-artifact-history"
              title="Click to open artifact list"
              ${artifacts.length ? "" : "disabled"}
            >
              ${icon("download")}
            </button>
          </div>
          ${recentArtifact ? `
            <button class="artifact-button recent-artifact-card" type="button" data-action="open-artifact" data-artifact-id="${escapeHtml(recentArtifact.id)}">
              ${icon("download")}
              <span>
                <strong>${escapeHtml(recentArtifact.path)}</strong>
                <small>${escapeHtml(recentArtifact.kind)} · ${formatBytes(recentArtifact.size_bytes)} · ${formatDate(recentArtifact.created_at)}</small>
              </span>
            </button>
          ` : `<div class="empty-state">No artifacts yet for the current snapshot.</div>`}
        </section>
        <section class="list-block">
          <div class="list-head">
            <strong>Jobs &amp; Logs</strong>
            <button
              class="history-launch ${jobs.length ? "" : "disabled"}"
              type="button"
              data-action="open-job-history"
              title="Click to open recent job history"
              ${jobs.length ? "" : "disabled"}
            >
              ${icon("clock")}
            </button>
          </div>
          ${recentJob ? `
            <button class="project-link recent-job-card" type="button" data-action="open-job-history" data-job-id="${escapeHtml(recentJob.id)}">
              ${icon("clock")}
              <span>
                <strong>${escapeHtml(recentJob.kind)}</strong>
                <small>${recentJob.status ? statusBadge(recentJob.status) : ""} ${formatDate(recentJob.updated_at)}</small>
              </span>
            </button>
          ` : `<div class="empty-state">No recent jobs remembered in this browser yet.</div>`}
        </section>
      </div>
    </aside>
  `;
}

function renderModal() {
  if (!state.modal) return "";
  if (state.modal.type === "import") return renderImportModal();
  if (state.modal.type === "project-files") return renderProjectFilesModal();
  if (state.modal.type === "artifact-history") return renderArtifactHistoryModal();
  if (state.modal.type === "job-history") return renderJobHistoryModal();
  if (state.modal.type === "preview") return renderPreviewModal();
  return "";
}

function renderImportModal() {
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

function renderProjectFilesModal() {
  const project = currentProject();
  const version = currentVersion();
  return `
    <div class="modal-backdrop">
      <section class="modal-card modal-wide">
        <div class="modal-header">
          <div>
            <h2>Files in current snapshot</h2>
            <p>${project ? escapeHtml(project.name) : "No project selected"}${version ? ` · snapshot #${version.version_number}` : ""}</p>
          </div>
          <button class="ghost" type="button" data-action="close-modal">${icon("x")} Close</button>
        </div>
        <div class="modal-body">
          <section class="file-grid">
            ${state.files.map((file) => `
              <button class="file-tile" data-action="open-file" data-file-id="${escapeHtml(file.id)}" title="${escapeHtml(file.path)}">
                ${icon("file")}
                <span>
                  <strong>${escapeHtml(file.path)}</strong>
                  <small>${escapeHtml(file.role)} · ${formatBytes(file.size_bytes)}</small>
                </span>
              </button>
            `).join("") || `<div class="empty-state">No files loaded for the current project.</div>`}
          </section>
        </div>
      </section>
    </div>
  `;
}

function renderJobHistoryModal() {
  const project = currentProject();
  const jobs = jobsForCurrentProject();
  const selectedJob = jobs.find((job) => job.id === state.logJobId) || jobs[0] || null;
  return `
    <div class="modal-backdrop">
      <section class="modal-card modal-wide job-history-modal">
        <div class="modal-header">
          <div>
            <h2>Jobs &amp; Logs</h2>
            <p>${project ? `Recent jobs for ${escapeHtml(project.name)}` : "Recent reduced-workspace jobs"}</p>
          </div>
          <button class="ghost" type="button" data-action="close-modal">${icon("x")} Close</button>
        </div>
        <div class="modal-body">
          <section class="compact-grid">
            ${jobs.map((job) => `
              <button class="compact-tile ${selectedJob?.id === job.id ? "active" : ""}" type="button" data-log-job-id="${escapeHtml(job.id)}" title="${escapeHtml(job.kind)}">
                ${icon("clock")}
                <span>
                  <strong>${escapeHtml(job.kind)}</strong>
                  <small>${job.status ? statusBadge(job.status) : ""} ${formatDate(job.updated_at)}</small>
                </span>
              </button>
            `).join("") || `<div class="empty-state">No recent jobs remembered in this browser yet.</div>`}
          </section>
          <section class="job-log-panel">${renderJobLogPanel(selectedJob)}</section>
        </div>
      </section>
    </div>
  `;
}

function renderJobLogPanel(selectedJob) {
  const logs = selectedJob && selectedJob.id === state.jobLogsJobId ? state.jobLogs : [];
  return `
    <div class="job-log-head">
      <div>
        <strong>${selectedJob ? escapeHtml(selectedJob.kind) : "No job selected"}</strong>
        <p>${selectedJob ? `${escapeHtml(String(selectedJob.status || "unknown"))} · ${formatDate(selectedJob.updated_at)}` : "Choose a job above to inspect its execution log."}</p>
      </div>
      ${selectedJob ? `<span class="job-log-meta">${escapeHtml(String(selectedJob.id).slice(0, 8))}</span>` : ""}
    </div>
    <div class="job-log-view">
      ${selectedJob ? renderJobLogLines(logs, state.jobLogsLoading && state.jobLogsJobId === selectedJob.id) : `<div class="empty-state">No job selected.</div>`}
    </div>
  `;
}

function renderJobLogLines(logs, loading = false) {
  if (loading) return `<div class="empty-state">Loading logs...</div>`;
  if (!logs.length) return `<div class="empty-state">No logs available for this job yet.</div>`;
  return `
    <pre class="job-log-text">${escapeHtml(logs.map((entry) => `[${entry.level || "info"}] ${entry.message || ""}`).join("\n"))}</pre>
  `;
}

function renderArtifactHistoryModal() {
  const project = currentProject();
  const artifacts = [...state.artifacts].sort((left, right) => {
    return String(right.created_at || "").localeCompare(String(left.created_at || ""));
  });
  return `
    <div class="modal-backdrop">
      <section class="modal-card modal-wide">
        <div class="modal-header">
          <div>
            <h2>Artifacts</h2>
            <p>${project ? `Artifacts for ${escapeHtml(project.name)}` : "Artifacts for the current snapshot"}</p>
          </div>
          <button class="ghost" type="button" data-action="close-modal">${icon("x")} Close</button>
        </div>
        <div class="modal-body">
          <section class="compact-grid">
            ${artifacts.map((artifact) => `
              <button class="compact-tile" type="button" data-action="open-artifact" data-artifact-id="${escapeHtml(artifact.id)}" title="${escapeHtml(artifact.path)}">
                ${icon("download")}
                <span>
                  <strong>${escapeHtml(artifact.path)}</strong>
                  <small>${escapeHtml(artifact.kind)} · ${formatBytes(artifact.size_bytes)} · ${formatDate(artifact.created_at)}</small>
                </span>
              </button>
            `).join("") || `<div class="empty-state">No artifacts yet for the current snapshot.</div>`}
          </section>
        </div>
      </section>
    </div>
  `;
}

function renderPreviewModal() {
  const modal = state.modal;
  if (!modal || modal.type !== "preview") return "";
  return `
    <div class="modal-backdrop">
      <section class="modal-card preview-modal">
        <div class="modal-header preview-header">
          <button class="ghost" type="button" data-action="close-modal">${icon("back")} Back</button>
          <div class="preview-title">
            <h2>${escapeHtml(modal.title)}</h2>
            <p>${escapeHtml(modal.subtitle || "")}</p>
          </div>
          <button type="button" class="secondary" data-action="${escapeHtml(modal.downloadAction)}" ${modal.downloadIdAttr}>
            ${icon("download")} Download
          </button>
        </div>
        <div class="preview-body">
          ${renderPreviewBody(modal)}
        </div>
      </section>
    </div>
  `;
}

function renderPreviewBody(modal) {
  if (modal.loading) return `<div class="empty-state">Loading preview...</div>`;
  if (modal.error) return `<div class="empty-state">${escapeHtml(modal.error)}</div>`;
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
  return `<div class="empty-state">Preview is not available for this file.</div>`;
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
      state.screen = "workspace";
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
    if (button.classList.contains("project-item")) {
      button.addEventListener("click", async () => {
        await selectProject(button.dataset.projectId);
      });
      button.addEventListener("dblclick", async () => {
        await openProjectFiles(button.dataset.projectId);
      });
    }
  });
  root.querySelectorAll("[data-job-kind]").forEach((button) => {
    button.addEventListener("click", async () => {
      const parameters = {};
      if (button.dataset.jobSchema) parameters.schema = state.moduleSchema;
      await startJob(button.dataset.jobKind, parameters);
    });
  });
  root.querySelectorAll("[data-log-job-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      await selectJobLog(button.dataset.logJobId);
    });
  });
  root.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", onAction);
    if (button.dataset.action === "advance-delivery-status") {
      button.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") {
          return;
        }
        event.preventDefault();
        onAction({ currentTarget: button });
      });
    }
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
  if (action === "back-to-menu") {
    state.projectMenuId = null;
    state.screen = "menu";
    render();
    return;
  }
  if (action === "toggle-project-menu") {
    const projectId = actionTargetId(event.currentTarget.dataset.projectId);
    state.projectMenuId = state.projectMenuId === projectId ? null : projectId;
    render();
    return;
  }
  if (action === "delete-project") {
    await deleteProject(actionTargetId(event.currentTarget.dataset.projectId));
    return;
  }
  if (action === "open-file") {
    await openFile(actionTargetId(event.currentTarget.dataset.fileId));
    return;
  }
  if (action === "open-artifact") {
    await openArtifact(actionTargetId(event.currentTarget.dataset.artifactId));
    return;
  }
  if (action === "download-file") {
    await downloadFile(actionTargetId(event.currentTarget.dataset.fileId));
    return;
  }
  if (action === "download-artifact") {
    await downloadArtifact(actionTargetId(event.currentTarget.dataset.artifactId));
    return;
  }
  if (action === "open-job-history") {
    await openJobHistoryModal(actionTargetId(event.currentTarget.dataset.jobId));
    return;
  }
  if (action === "open-artifact-history") {
    state.modal = { type: "artifact-history" };
    render();
    return;
  }
  if (action === "focus-projects") {
    root.querySelector(".project-stack")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  if (action === "advance-delivery-status") {
    await advanceDeliveryStatus();
  }
}

async function advanceDeliveryStatus() {
  const version = currentVersion();
  if (!version || state.busy) {
    return;
  }
  await runAction(async () => {
    const result = await api.advanceDeliveryStatus(version.id);
    state.selectedVersionId = result.version.id;
    await loadProject(currentProject().id);
    const status = result.delivery_state?.status;
    const label = deliveryStepsFromState(result.delivery_state).find((step) => step.status === status)?.label;
    notify(label ? `Delivery status: ${label}` : "Delivery status updated");
  });
}

function actionTargetId(value) {
  return value || "";
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
  const preferred = state.selectedVersionId;
  if (!preferred || !state.versions.some((item) => item.id === preferred)) {
    state.selectedVersionId = state.versions[0]?.id || null;
  }
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
  state.projectMenuId = null;
  localStorage.setItem(SELECTED_PROJECT_KEY, projectId);
  await runAction(async () => {
    await loadProject(projectId);
  }, { silent: true });
}

async function openProjectFiles(projectId) {
  if (!projectId) return;
  if (projectId !== state.selectedProjectId) {
    await selectProject(projectId);
  }
  state.modal = { type: "project-files", projectId };
  render();
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

async function openFile(fileId) {
  const version = currentVersion();
  const file = state.files.find((item) => item.id === fileId);
  if (!version || !file) return;
  if (!isPreviewSupported(file)) {
    await downloadFile(fileId);
    return;
  }
  await openStoredObjectPreview({
    item: file,
    contentUrl: api.versionFileContentUrl(version.id, file.id),
    downloadAction: "download-file",
    downloadIdAttr: `data-file-id="${escapeHtml(file.id)}"`,
  });
}

async function openArtifact(artifactId) {
  const artifact = state.artifacts.find((item) => item.id === artifactId);
  if (!artifact) return;
  if (!isPreviewSupported(artifact)) {
    await downloadArtifact(artifactId);
    return;
  }
  await openStoredObjectPreview({
    item: artifact,
    contentUrl: api.artifactContentUrl(artifact.id),
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
    const text = await api.fetchTextFromUrl(contentUrl);
    if (state.modal !== modal) return;
    state.modal = { ...modal, loading: false, textContent: text };
    render();
  } catch (error) {
    if (state.modal !== modal) return;
    state.modal = { ...modal, loading: false, error: error.message || "Preview failed" };
    render();
  }
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
  if (!state.jobs.some((job) => job.id === state.logJobId)) {
    state.logJobId = state.jobs[0]?.id || null;
    if (state.logJobId) localStorage.setItem(LOG_JOB_KEY, state.logJobId);
  }
  if (state.selectedJobId) await refreshJob(state.selectedJobId);
  if (!state.logJobId) {
    state.jobLogs = [];
    state.jobLogsJobId = null;
    localStorage.removeItem(LOG_JOB_KEY);
  }
}

async function selectJob(jobId) {
  if (!jobId) return;
  state.selectedJobId = jobId;
  localStorage.setItem(SELECTED_JOB_KEY, jobId);
  await runAction(async () => {
    await refreshJob(jobId);
  }, { silent: true });
}

async function selectJobLog(jobId) {
  if (!jobId) return;
  state.logJobId = jobId;
  localStorage.setItem(LOG_JOB_KEY, jobId);
  state.jobLogsJobId = jobId;
  state.jobLogsLoading = true;
  if (!syncJobHistoryModal()) {
    render();
  }
  try {
    const [job, logs] = await Promise.all([
      api.getJob(jobId),
      api.getJobLogs(jobId),
    ]);
    upsertJob(job);
    if (state.logJobId !== jobId) return;
    state.jobLogs = logs.items || [];
  } catch (error) {
    if (state.logJobId !== jobId) return;
    state.jobLogs = [];
    notify(error.message || "Could not load job logs");
  } finally {
    if (state.logJobId === jobId) {
      state.jobLogsJobId = jobId;
      state.jobLogsLoading = false;
      if (!syncJobHistoryModal()) {
        render();
      }
    }
  }
}

async function openJobHistoryModal(preferredJobId = "") {
  const jobs = jobsForCurrentProject();
  const targetJobId = preferredJobId || jobs.find((job) => job.id === state.logJobId)?.id || jobs[0]?.id || null;
  state.modal = { type: "job-history" };
  render();
  if (targetJobId) {
    await selectJobLog(targetJobId);
  } else {
    state.logJobId = null;
    state.jobLogs = [];
    state.jobLogsJobId = null;
    state.jobLogsLoading = false;
    localStorage.removeItem(LOG_JOB_KEY);
    render();
  }
}

function syncJobHistoryModal() {
  if (state.modal?.type !== "job-history") return false;
  const modal = root.querySelector(".job-history-modal");
  if (!modal) return false;
  const jobs = jobsForCurrentProject();
  const selectedJob = jobs.find((job) => job.id === state.logJobId) || jobs[0] || null;
  modal.querySelectorAll("[data-log-job-id]").forEach((button) => {
    button.classList.toggle("active", button.dataset.logJobId === selectedJob?.id);
  });
  const panel = modal.querySelector(".job-log-panel");
  if (panel) {
    panel.innerHTML = renderJobLogPanel(selectedJob);
  }
  return true;
}

async function refreshJob(jobId) {
  const job = await api.getJob(jobId);
  upsertJob(job);
  const logs = await api.getJobLogs(jobId);
  if (state.selectedJobId === jobId) {
    state.jobLogs = logs.items || [];
  }
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

async function deleteProject(projectId) {
  const project = state.projects.find((item) => item.id === projectId);
  if (!project) return;
  const confirmed = window.confirm(`Delete project "${project.name}"?`);
  if (!confirmed) return;
  await runAction(async () => {
    await api.deleteProject(project.id);
    if (state.selectedProjectId === project.id) {
      state.selectedProjectId = null;
      state.selectedVersionId = null;
      state.selectedJobId = null;
      state.files = [];
      state.artifacts = [];
      state.jobLogs = [];
      localStorage.removeItem(SELECTED_PROJECT_KEY);
      localStorage.removeItem(SELECTED_JOB_KEY);
    }
    state.projectMenuId = null;
    await refreshAll();
    notify("Project deleted");
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
