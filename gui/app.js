"use strict";
const $ = id => document.getElementById(id);
let projects = [], project = null, experiment = null, activeTab = "metadata", workspaceView = "overview";
let drafts = {metadata: {}, parameters: {}}, creating = false, busy = false, selectionRequest = 0;
let folder = null, folderTarget = null, expanded = new Set(), editorExpanded = new Set(), savedMessage = "", lastBackup = "";
let newProject = null;
// File-browser state: the project whose experiments are listed (null = all projects),
// the row shown in the details sidebar, and the list ordering.
let currentProjectId = null, selectedItem = null, sortState = {key: "number", dir: 1};
const element = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};
function icon(name, className = "icon") {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg"), use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  svg.setAttribute("class", className); svg.setAttribute("aria-hidden", "true"); use.setAttribute("href", `#${name}`); svg.append(use);
  return svg;
}
function labelledButton(iconName, text, className) {
  const button = element("button", undefined, className); button.type = "button";
  button.append(icon(iconName), document.createTextNode(text)); return button;
}
const dirty = section => Object.keys(drafts[section]).length > 0 || (section === "parameters" && creating);
const anyDirty = () => dirty("metadata") || dirty("parameters") || (typeof extraUnsaved === "function" && extraUnsaved());
function canLeave() { return !busy && (!anyDirty() || window.confirm("Leave without saving your changes? Choose Cancel to keep editing.")); }
function clearError() { $("error").hidden = true; }
function showError(error) {
  $("error-text").textContent = error.message;
  $("error-reload").hidden = !error.reload || !project;
  $("error").hidden = false;
  $("error").focus();
}
async function request(url, options) {
  let response;
  try { response = await fetch(url, options); }
  catch { throw new Error("The experiment application is not responding. Restart it and try again. Your unsaved changes are still on this page."); }
  const result = await response.json();
  if (!response.ok) { const error = new Error(result.error || `Request failed (${response.status}).`); error.reload = result.reload; throw error; }
  return result;
}
const post = (url, payload) => request(url, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
function isoDate(raw) {
  if (!/^\d{6}$/.test(raw)) return "";
  const year = Number(raw.slice(0, 2));
  const value = `${year <= 68 ? "20" : "19"}${raw.slice(0, 2)}-${raw.slice(2, 4)}-${raw.slice(4, 6)}`;
  const date = new Date(value + "T12:00:00Z");
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value ? value : "";
}
function friendlyDate(raw) {
  const iso = isoDate(raw);
  return iso ? new Date(iso + "T12:00:00Z").toLocaleDateString(undefined, {day: "numeric", month: "short", year: "numeric", timeZone: "UTC"}) : (raw || "Date not set");
}
function rowName(row) { return row.title || row.subject || `Experiment ${row.number}`; }
function replaceProject(next) {
  const index = projects.findIndex(item => item.id === next.id);
  if (index < 0) projects.push(next); else projects[index] = next;
}
function actionableRow(tr, action) {
  tr.tabIndex = 0;
  tr.onclick = action;
  tr.onkeydown = event => {
    if (event.target === tr && ["Enter", " "].includes(event.key)) { event.preventDefault(); action(); }
  };
}
// Last few folders of a long path; the full path stays in the tooltip and sidebar.
const shortPath = (path, keep = 3) => { const parts = path.split(/[\\/]/).filter(Boolean); return parts.length > keep ? `…/${parts.slice(-keep).join("/")}` : path; };
const modality = row => row.miniscope && row.ephys ? "mm" : row.miniscope ? "ca" : row.ephys ? "ep" : "none";
function recordingTags(row) {
  const tags = [row.miniscope && element("span", "Calcium", "tag tag-ca"), row.ephys && element("span", "Ephys", "tag tag-ep")].filter(Boolean);
  return tags.length ? tags : [element("span", "Not set", "muted")];
}
function settingsStatus(row) {
  const [text, kind] = row.parameter_error ? ["File needs attention", "bad"] : row.has_parameters ? ["Available", "ok"] : ["No settings", "warn"];
  return element("span", text, `status status-${kind}`);
}
function projectStatus(item) {
  const missing = item.missing_parameters.length;
  const [text, kind] = item.parameter_error ? ["File needs attention", "bad"] : missing ? [`${missing} without settings`, "warn"] : ["All experiments have settings", "ok"];
  return element("span", text, `status status-${kind}`);
}
// Latest run per experiment and saved preview images, fetched per project for the list and grid.
const activity = new Map(), activityRequests = new Set();
let viewMode = (() => { try { return localStorage.getItem("ace-gui-view") === "grid" ? "grid" : "list"; } catch { return "list"; } })();
function loadActivity(projectId) {
  if (activity.has(projectId) || activityRequests.has(projectId)) return;
  activityRequests.add(projectId);
  request(`/api/project/activity?project=${encodeURIComponent(projectId)}`)
    .then(result => activity.set(projectId, result), () => activity.set(projectId, {latest_runs: {}, previews: {}}))
    .finally(() => { activityRequests.delete(projectId); if (!$("home").hidden) renderProjects(); });
}
const latestRun = (projectId, number) => activity.get(projectId)?.latest_runs?.[number] || null;
const previewVersion = (projectId, number) => activity.get(projectId)?.previews?.[number];
function timeAgo(iso) {
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000;
  if (!Number.isFinite(seconds)) return "";
  if (seconds < 60) return "just now";
  for (const [limit, size, unit] of [[3600, 60, "min"], [86400, 3600, "h"], [2592000, 86400, "d"]]) if (seconds < limit) return `${Math.floor(seconds / size)} ${unit} ago`;
  return new Date(iso).toLocaleDateString(undefined, {day: "numeric", month: "short", year: "numeric"});
}
function runPill(run) {
  const pill = element("span", run.state, `pill pill-${run.state}`);
  pill.title = `${run.label} · started ${new Date(run.started).toLocaleString()}`; return pill;
}
function lastRun(run) {
  const wrap = element("span", undefined, "last-run");
  wrap.append(...(run ? [runPill(run), element("span", timeAgo(run.started), "row-meta")] : [element("span", "No runs", "muted")]));
  return wrap;
}

// "More options" menus for rows and cards; right-click or the context-menu key opens the same menu.
let openMenuState = null;
function closeMenu(restoreFocus = false) {
  if (!openMenuState) return;
  const {node, trigger} = openMenuState; openMenuState = null; node.remove();
  if (restoreFocus && trigger?.isConnected) trigger.focus();
}
function showMenu(items, anchor, trigger) {
  closeMenu();
  const node = element("div", undefined, "menu"); node.setAttribute("role", "menu");
  for (const item of items) {
    if (item === "separator") { const line = element("div", undefined, "menu-separator"); line.setAttribute("role", "separator"); node.append(line); continue; }
    const entry = element(item.href ? "a" : "button", undefined, "menu-item");
    entry.setAttribute("role", "menuitem"); entry.tabIndex = -1; entry.append(icon(item.icon), element("span", item.label));
    if (item.href) { entry.href = item.href; entry.target = "_blank"; entry.rel = "noopener noreferrer"; } else entry.type = "button";
    if (item.disabled) { entry.disabled = true; entry.setAttribute("aria-disabled", "true"); }
    entry.onclick = () => { closeMenu(); item.action?.(); };
    node.append(entry);
  }
  document.body.append(node);
  const box = anchor instanceof Element ? anchor.getBoundingClientRect() : {left: anchor.x, right: anchor.x, top: anchor.y, bottom: anchor.y};
  const left = anchor instanceof Element ? box.right - node.offsetWidth : box.left;
  const top = box.bottom + 4 + node.offsetHeight > innerHeight - 8 ? Math.max(8, box.top - node.offsetHeight - 4) : box.bottom + 4;
  node.style.left = `${Math.max(8, Math.min(left, innerWidth - node.offsetWidth - 8))}px`; node.style.top = `${top}px`;
  openMenuState = {node, trigger};
  const entries = () => [...node.querySelectorAll(".menu-item:not([aria-disabled='true'])")];
  node.onkeydown = event => {
    const list = entries(), index = list.indexOf(document.activeElement), down = event.key === "ArrowDown";
    if (down || event.key === "ArrowUp") {
      event.preventDefault();
      list[index < 0 ? (down ? 0 : list.length - 1) : (index + (down ? 1 : list.length - 1)) % list.length]?.focus();
    } else if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); closeMenu(true); }
    else if (event.key === "Tab") closeMenu();
  };
  entries()[0]?.focus({preventScroll: true});
}
document.addEventListener("pointerdown", event => {
  if (openMenuState && !openMenuState.node.contains(event.target) && !openMenuState.trigger?.contains(event.target)) closeMenu();
}, true);
document.addEventListener("scroll", event => { if (openMenuState && !openMenuState.node.contains(event.target)) closeMenu(); }, true);
window.addEventListener("resize", () => closeMenu());
async function reviewAndRun(projectId, number) {
  await selectExperiment(projectId, number);
  if (project?.id === projectId && experiment?.number === number) $("review-run").click();
}
const boxFolderLinks = row => (row.box_folders || []).map(folder => ({label: `Open ${folder.name.toLowerCase()} Box folder`, icon: "i-external", href: `https://app.box.com/folder/${folder.id}`}));
function experimentMenu(item, row) {
  const links = boxFolderLinks(row);
  return [
    {label: "Open", icon: "i-chevron-right", action: () => selectExperiment(item.id, row.number)},
    {label: row.has_parameters ? "Edit analysis settings" : "Add analysis settings", icon: "i-sliders", action: () => selectExperiment(item.id, row.number, "parameters")},
    {label: "Review & run", icon: "i-play", action: () => reviewAndRun(item.id, row.number)},
    "separator",
    ...(links.length ? links : [{label: "No Box folder set", icon: "i-cloud", disabled: true}]),
  ];
}
function projectMenu(item) {
  return [
    {label: "Open", icon: "i-chevron-right", action: () => showHome(item.id)},
    {label: "New experiment", icon: "i-plus", action: () => showNewExperiment(item.id)},
    {label: "Reload CSV files", icon: "i-refresh", action: () => reloadProject(item.id)},
  ];
}
function moreButton(label, menu, select) {
  const button = element("button", undefined, "icon-button row-action"); button.type = "button";
  button.setAttribute("aria-label", label); button.setAttribute("aria-haspopup", "menu"); button.title = "More options"; button.append(icon("i-more"));
  // Kept from the row's click handler, which would otherwise close the menu it opens.
  button.onclick = event => { event.stopPropagation(); select(); if (openMenuState?.trigger === button) closeMenu(); else showMenu(menu(), button, button); };
  return button;
}
// Box-style rows and cards: a click selects the item for the details sidebar; double-click,
// Enter, or the name opens it. Arrow keys move the selection.
function bindRow(node, open, select, menu) {
  node.tabIndex = 0;
  const ignore = event => event.target.closest("button, a, input, select") && event.target !== node;
  node.onclick = event => { closeMenu(); if (!ignore(event)) select(); };
  node.ondblclick = event => { if (!ignore(event)) open(); };
  node.oncontextmenu = event => { if (ignore(event)) return; event.preventDefault(); select(); showMenu(menu(), {x: event.clientX, y: event.clientY}, node); };
  node.onkeydown = event => {
    if (event.target !== node) return;
    const steps = node.classList.contains("grid-card") ? {ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1} : {ArrowDown: 1, ArrowUp: -1};
    if (event.key === "Enter") { event.preventDefault(); open(); }
    else if (event.key === " ") { event.preventDefault(); select(); }
    else if (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10")) { event.preventDefault(); select(); showMenu(menu(), node, node); }
    else if (steps[event.key]) {
      const next = steps[event.key] > 0 ? node.nextElementSibling : node.previousElementSibling;
      if (next) { event.preventDefault(); next.focus(); next.click(); }
    }
  };
}
function selectItem(projectId, number = null) {
  selectedItem = {project: projectId, number};
  for (const node of $("projects").querySelectorAll("[data-project]")) {
    const match = node.dataset.project === projectId && (node.dataset.number || null) === number;
    node.classList.toggle("is-selected", match); node.setAttribute("aria-selected", match ? "true" : "false");
  }
  renderHomeSidebar();
}
function sortHeader(label, key, className) {
  const th = element("th", undefined, className), button = element("button", label, "sort-button"), active = sortState.key === key;
  button.type = "button";
  if (active) { button.append(icon("i-sort", `icon sort-icon${sortState.dir < 0 ? " is-desc" : ""}`)); th.setAttribute("aria-sort", sortState.dir > 0 ? "ascending" : "descending"); }
  // Third click returns to the CSV order.
  button.onclick = () => { sortState = !active ? {key, dir: 1} : sortState.dir > 0 ? {key, dir: -1} : {key: "number", dir: 1}; renderProjects(); };
  th.append(button); return th;
}
function sortEntries(entries) {
  if (sortState.key === "number") return entries;
  const value = ({row}) => sortState.key === "name" ? rowName(row).toLowerCase() : isoDate(row.date);
  return [...entries].sort((a, b) => {
    const left = value(a), right = value(b);
    if (!left || !right) return left ? -1 : right ? 1 : 0;
    return sortState.dir * left.localeCompare(right, undefined, {numeric: true});
  });
}
function selectedRowClass(node, projectId, number = null) {
  if (selectedItem?.project === projectId && (selectedItem.number || null) === number) { node.classList.add("is-selected"); node.setAttribute("aria-selected", "true"); }
}
function setViewMode(mode) {
  viewMode = mode;
  try { localStorage.setItem("ace-gui-view", mode); } catch { /* storage unavailable */ }
  renderProjects();
}
function renderProjects() {
  const term = $("search").value.trim().toLowerCase(), missingOnly = $("missing-only").checked;
  $("start-message").hidden = projects.length !== 0;
  $("projects").replaceChildren(...projects.map(item => {
    const group = element("details", undefined, "project-folder");
    group.open = expanded.has(item.id) || Boolean(term) || missingOnly;
    group.ontoggle = () => { if (group.open) expanded.add(item.id); else expanded.delete(item.id); };
    const heading = element("summary", undefined, "project-heading");
    heading.append(element("span", item.name), element("span", `${item.count} experiments`, "folder-count"));
    const location = element("div", undefined, "project-location"), reload = element("button", "Reload project", "text-action");
    reload.onclick = () => reloadProject(item.id); location.append(element("span", item.path), reload);
    group.append(heading, location);
    const actions = element("div", undefined, "project-actions");
    const defaultLabel = element("label", "Default parameters from");
    const defaultSelect = element("select"); defaultSelect.setAttribute("aria-label", `Default experiment for ${item.name}`);
    const empty = element("option", "Choose an experiment"); empty.value = ""; defaultSelect.append(empty);
    for (const row of item.experiments.filter(row => row.has_parameters)) {
      const option = element("option", `${rowName(row)} · #${row.number}`); option.value = row.number; defaultSelect.append(option);
    }
    defaultSelect.value = item.default_experiment || "";
    defaultSelect.onchange = async () => {
      const previous = item.default_experiment || ""; defaultSelect.disabled = true; clearError();
      try {
        const result = await post("/api/projects/default", {project: item.id, number: defaultSelect.value || null, versions: item.versions});
        replaceProject(result.project);
        if (project?.id === item.id) { project = result.project; if (experiment) experiment.versions = result.project.versions; }
        if (newProject?.id === item.id) newProject = result.project;
        renderProjects();
      }
      catch (error) { defaultSelect.value = previous; defaultSelect.disabled = false; showError(error); }
    };
    defaultLabel.append(defaultSelect);
    const add = element("button", "New experiment"); add.type = "button"; add.onclick = () => showNewExperiment(item.id);
    actions.append(defaultLabel, add); group.append(actions);
    if (item.parameter_error) {
      const notice = element("div", undefined, "project-notice");
      notice.append(element("strong", "Analysis settings could not be read."), element("p", item.parameter_error)); group.append(notice);
    } else if (item.missing_parameters.length) {
      const notice = element("div", undefined, "project-notice"), links = element("div", undefined, "missing-links");
      notice.append(element("strong", `${item.missing_parameters.length} experiments have no analysis settings:`));
      for (const number of item.missing_parameters) {
        const row = item.experiments.find(record => record.number === number);
        const button = element("button", `${rowName(row)} · #${number}`, "text-action");
        button.onclick = () => selectExperiment(item.id, number, "parameters"); links.append(button);
      }
      notice.append(links); group.append(notice);
    }
    if (item.orphan_parameters.length) {
      const note = element("details", undefined, "orphan-note"); note.append(element("summary", `${item.orphan_parameters.length} unlinked settings ${item.orphan_parameters.length === 1 ? "record" : "records"}`), element("p", `Experiment numbers in the settings file: ${item.orphan_parameters.join(", ")}`)); group.append(note);
    }
    const matches = item.experiments.filter(row => {
      const search = `${row.search} ${rowName(row)} ${friendlyDate(row.date)} ${isoDate(row.date)} experiment ${row.number}`.toLowerCase();
      return term.split(/\s+/).every(word => search.includes(word)) && (!missingOnly || !row.has_parameters);
    });
    const table = element("table"), head = element("thead"), hr = element("tr");
    for (const [label, cls] of [["Experiment", ""], ["Recorded", ""], ["Recordings", "recording-column"], ["Analysis settings", ""]]) hr.append(element("th", label, cls));
    head.append(hr); table.append(head);
    const body = element("tbody");
    for (const row of matches) {
      const tr = element("tr", undefined, `experiment-row${!row.has_parameters ? " missing" : ""}`);
      tr.dataset.number = row.number; tr.dataset.project = item.id;
      actionableRow(tr, () => selectExperiment(item.id, row.number));
      const name = element("td"), button = element("button", rowName(row), "row-open");
      button.tabIndex = -1; name.append(button, element("span", `Experiment ${row.number}${row.title && row.subject ? ` · ${row.subject}` : ""}`, "experiment-number"));
      tr.append(name, element("td", friendlyDate(row.date)), element("td", [row.miniscope && "Calcium", row.ephys && "Ephys"].filter(Boolean).join(" + ") || "Not set", "recording-column"), element("td", row.parameter_error ? "File needs attention" : row.has_parameters ? "Available" : "No settings"));
      body.append(tr);
    }
    table.append(body); group.append(table);
    if (!matches.length) group.append(element("p", item.count ? "No experiments match this search." : "This project has no experiment records."));
    return group;
  }));
}
async function openProject(path) {
  if (!canLeave()) return;
  clearError(); busy = true; $("use-folder").disabled = true;
  try {
    const next = await post("/api/projects/open", {path}); replaceProject(next); expanded.add(next.id);
    resetEditor(); $("new-experiment").hidden = true; newProject = null; $("folders").hidden = true; $("detail").hidden = true; $("home").hidden = false; renderProjects();
    $("search").focus();
  } catch (error) { showError(error); }
  finally { busy = false; if (folder) $("use-folder").disabled = !folder.has_experiments; }
}
async function reloadProject(id) {
  if (!canLeave()) return;
  clearError(); const target = projects.find(item => item.id === id), number = project?.id === id ? experiment?.number : null;
  busy = true;
  try {
    const next = await post("/api/projects/open", {path: target.path}); replaceProject(next); resetEditor(); renderProjects();
    busy = false;
    if (number && next.experiments.some(row => row.number === number)) await selectExperiment(id, number, activeTab);
    else { $("detail").hidden = true; $("home").hidden = false; }
  } catch (error) { showError(error); }
  finally { busy = false; }
}
function resetEditor() { if (typeof resetAnalysisDrafts === "function") resetAnalysisDrafts(); selectionRequest++; experiment = null; drafts = {metadata: {}, parameters: {}}; creating = false; savedMessage = ""; lastBackup = ""; }
function sourceOptions(select, destinationId) {
  const previous = select.value;
  select.replaceChildren();
  const blank = element("option", "Blank settings"); blank.value = ""; select.append(blank);
  for (const item of projects.filter(item => item.default_experiment && !item.parameter_error)) {
    const option = element("option", `${item.name} · experiment ${item.default_experiment}${item.id === destinationId ? " (this project)" : ""}`);
    option.value = item.id; select.append(option);
  }
  select.value = [...select.options].some(option => option.value === previous) ? previous : (projects.find(item => item.id === destinationId)?.default_experiment ? destinationId : "");
}
async function sourceSettings(sourceId, destinationColumns) {
  if (!sourceId) return {};
  const source = projects.find(item => item.id === sourceId);
  if (!source?.default_experiment) throw new Error("Choose a project with a default experiment.");
  const detail = await request(`/api/experiment?project=${encodeURIComponent(sourceId)}&number=${encodeURIComponent(source.default_experiment)}`);
  return Object.fromEntries(Object.entries(detail.parameters || {}).filter(([key]) =>
    key !== "line number" && destinationColumns.includes(key) &&
    !["Recording details in settings", "Experiment"].includes(detail.fields.parameters.find(field => field.key === key)?.group)
  ));
}
function showNewExperiment(id) {
  newProject = projects.find(item => item.id === id); $("new-experiment").hidden = false;
  $("new-experiment-form").reset(); sourceOptions($("new-source"), id);
  $("new-experiment").scrollIntoView({block: "start"}); $("new-number").focus();
}
async function selectExperiment(projectId, number, tab = null) {
  if (!canLeave()) return;
  clearError(); $("new-experiment").hidden = true; newProject = null; resetEditor(); const revision = ++selectionRequest;
  project = projects.find(item => item.id === projectId); activeTab = tab || "metadata"; workspaceView = tab ? "editor" : "overview"; $("field-search").value = "";
  $("home").hidden = true; $("detail").hidden = false; $("detail-loading").hidden = false; $("detail-content").hidden = true;
  const row = project.experiments.find(item => item.number === number);
  $("detail-project").textContent = project.name; $("detail-title").textContent = rowName(row);
  $("detail-subtitle").textContent = `Experiment ${number} · ${friendlyDate(row.date)}`;
  $("detail-title").scrollIntoView({block: "start"});
  try {
    const result = await request(`/api/experiment?project=${encodeURIComponent(projectId)}&number=${encodeURIComponent(number)}`);
    if (revision !== selectionRequest) return;
    experiment = result; $("detail-content").hidden = false; renderEditor(); renderWorkspace();
  } catch (error) { if (revision === selectionRequest) showError(error); }
  finally { if (revision === selectionRequest) $("detail-loading").hidden = true; }
}
function originalValues(section) { return experiment[section] || Object.fromEntries(experiment.fields[section].map(field => [field.key, ""])); }
function fieldValue(field) { return Object.hasOwn(drafts[activeTab], field.key) ? drafts[activeTab][field.key] : originalValues(activeTab)[field.key]; }
function updateValue(field, value, section = activeTab) {
  const original = originalValues(section)[field.key];
  if (value === original) delete drafts[section][field.key]; else drafts[section][field.key] = value;
  savedMessage = ""; updateSaveBar();
}
function updateSaveBar() {
  const changed = dirty(activeTab), count = Object.keys(drafts[activeTab]).length;
  $("save").disabled = busy || !changed; $("discard").disabled = busy || !changed;
  $("save").textContent = busy ? "Saving…" : activeTab === "metadata" ? "Save experiment details" : "Save analysis settings";
  $("save-status").textContent = savedMessage || (changed ? creating && activeTab === "parameters" ? "New settings · not saved yet" : `${count} unsaved ${count === 1 ? "change" : "changes"}` : dirty(activeTab === "metadata" ? "parameters" : "metadata") ? "Unsaved changes in the other section" : "");
}
function makeField(field) {
  const value = fieldValue(field), container = element("div", undefined, `field${field.kind === "notes" ? " wide" : ""}`);
  const id = `field-${activeTab}-${experiment.fields[activeTab].indexOf(field)}`;
  const label = element("label", field.label); label.htmlFor = id; container.append(label);
  let control;
  if (field.kind === "notes") control = element("textarea");
  else if (field.kind === "boolean") {
    control = element("select");
    const options = [["", "Not set"], [value.toLowerCase() === "true" ? value : "TRUE", "Yes"], [value.toLowerCase() === "false" ? value : "FALSE", "No"]];
    if (value && !["true", "false"].includes(value.toLowerCase())) options.push([value, ["none", "na", "nan", "null"].includes(value.toLowerCase()) ? `Not set (${value})` : value]);
    for (const [raw, text] of options) { const option = element("option", text); option.value = raw; control.append(option); }
  } else {
    control = element("input"); control.type = "text";
    if (field.kind === "number" || field.kind === "box") control.inputMode = "decimal";
    if (field.kind === "date" && (!value || isoDate(value))) { control.type = "date"; control.min = "1969-01-01"; control.max = "2068-12-31"; }
  }
  control.id = id; control.dataset.key = field.key; control.title = field.key;
  control.value = control.type === "date" ? isoDate(value) : value;
  const controls = element("div", undefined, "field-controls"); controls.append(control); container.append(controls);
  if (field.kind === "folder" || field.kind === "file") {
    const browseButton = element("button", field.kind === "file" ? "Choose file" : "Choose folder"); browseButton.type = "button";
    browseButton.onclick = () => browse(project.path, {field, section: activeTab}); controls.append(browseButton);
  }
  let boxLink;
  if (field.kind === "box") {
    boxLink = element("a", "Open Box folder", "box-link"); boxLink.target = "_blank"; boxLink.rel = "noopener noreferrer";
    const updateLink = raw => { boxLink.hidden = !/^[0-9]+$/.test(raw.trim()); boxLink.href = boxLink.hidden ? "#" : `https://app.box.com/folder/${raw.trim()}`; };
    updateLink(value); container.append(boxLink);
    if (activeTab === "metadata") {
      const chooseBox = element("button", "Choose Box folder"); chooseBox.type = "button";
      chooseBox.onclick = () => openBoxFolderPicker(field.key); controls.append(chooseBox);
    }
    control.addEventListener("input", () => updateLink(control.value));
  }
  const help = field.help || (field.kind === "date" && control.type !== "date" ? "Recording date as YYMMDD, e.g. 240101." : "");
  if (help) { const hint = element("small", help); hint.id = `${id}-help`; control.setAttribute("aria-describedby", hint.id); container.append(hint); }
  control.addEventListener("input", () => updateValue(field, control.type === "date" && control.value ? control.value.slice(2).replaceAll("-", "") : control.value));
  return container;
}
function renderEditor() {
  if (!experiment) return;
  const settings = activeTab === "parameters", missing = settings && experiment.parameters === null;
  $("metadata-tab").setAttribute("aria-current", settings ? "false" : "page"); $("parameters-tab").setAttribute("aria-current", settings ? "page" : "false");
  $("settings-message").hidden = !missing;
  $("copy-settings").hidden = !settings || Boolean(experiment.parameter_error);
  if (settings) sourceOptions($("copy-source"), project.id);
  $("settings-text").textContent = experiment.parameter_error || (creating ? "Add the settings you want to store for this experiment. Blank fields stay blank." : `Experiment ${experiment.number} has no saved analysis settings.`);
  $("add-settings").hidden = creating || Boolean(experiment.parameter_error);
  $("editor-form").hidden = missing && !creating; $("editor-toolbar").hidden = missing && !creating;
  const term = $("field-search").value.trim().toLowerCase(), groups = new Map();
  for (const field of experiment.fields[activeTab]) {
    if (field.kind === "identity") continue;
    if (term && !`${field.label} ${field.key} ${fieldValue(field)}`.toLowerCase().includes(term)) continue;
    if (!groups.has(field.group)) groups.set(field.group, []); groups.get(field.group).push(field);
  }
  $("no-fields").hidden = groups.size !== 0;
  $("field-groups").replaceChildren(...Array.from(groups, ([name, fields]) => {
    const advanced = ["Neuron detection", "Motion correction", "Other fields", "Recording details in settings"].includes(name);
    const group = element(advanced ? "details" : "section", undefined, "field-group");
    if (advanced) {
      const key = `${activeTab}/${name}`;
      group.open = Boolean(term) || editorExpanded.has(key);
      group.ontoggle = () => { if (!term) { if (group.open) editorExpanded.add(key); else editorExpanded.delete(key); } };
    }
    group.append(element(advanced ? "summary" : "h3", name));
    const grid = element("div", undefined, "fields-grid"); grid.append(...fields.map(makeField)); group.append(grid); return group;
  }));
  $("file-info").textContent = `${project.path}\nExperiment details: experiments.csv\nAnalysis settings: analysis_parameters.csv\nExperiment number: ${experiment.number}${lastBackup ? `\nPrevious file copy: ${lastBackup}` : ""}`;
  $("reader-errors").replaceChildren(...experiment.reader_errors.map(message => element("p", message)));
  $("interpreted").textContent = JSON.stringify(experiment.interpreted, null, 2); updateSaveBar();
}
async function saveChanges(event) {
  event.preventDefault(); if (busy || !dirty(activeTab)) return;
  clearError(); const section = activeTab; busy = true; updateSaveBar(); $("editor-form").inert = true;
  try {
    const result = await post("/api/experiment/save", {project: project.id, number: experiment.number, section, changes: drafts[section], versions: experiment.versions, create: section === "parameters" && creating});
    replaceProject(result.project); project = result.project; experiment = result.experiment; drafts[section] = {};
    if (section === "parameters") creating = false;
    lastBackup = result.backup || ""; savedMessage = "Saved.";
    const row = project.experiments.find(item => item.number === experiment.number);
    $("detail-title").textContent = rowName(row); $("detail-subtitle").textContent = `Experiment ${experiment.number} · ${friendlyDate(row.date)}`;
    renderProjects(); renderEditor(); renderWorkspace();
  } catch (error) { showError(error); }
  finally { busy = false; $("editor-form").inert = false; updateSaveBar(); }
}
let pickerBusy = false;
function applyPickedPath(path, target) {
  if (target?.onpick) { target.onpick(path); return; }
  if (target?.kind === "box-cache") { $("box-download-path").value = path; $("box-finish").focus(); }
  else if (target?.kind === "neuron-estimates") { chooseNeuronSource(path); $("neuron-load").focus(); }
  else if (target?.kind === "neuron-output") { $("neuron-output-path").value = path; if (neuronSession && !$("neuron-finish").hidden) finishNeurons(); }
  else if (target?.kind === "data-base") { dataBases.set(project.id, path); renderAnalysis(); }
  else if (target?.field) {
    const {field, section} = target;
    updateValue(field, field.kind === "file" ? path.split(/[\\/]/).pop() : path, section); renderEditor();
  } else openProject(path);
}
async function browse(path, target = null) {
  if (busy || pickerBusy) return;
  pickerBusy = true; clearError();
  let initial = target?.field ? fieldValue(target.field) : path;
  if (!initial || initial.includes("\\")) initial = path || project?.path;
  if (initial && !initial.startsWith("/")) initial = (path || project?.path || "") + "/" + initial;
  $("picker-status").hidden = false; $("picker-status").textContent = "Choose a location in the system file picker, or cancel to return.";
  $("main-content").inert = true;
  try {
    const result = await post("/api/system/pick", {kind: target?.kind === "neuron-estimates" ? "estimates" : target?.field?.kind === "file" ? "file" : "folder", initial});
    $("main-content").inert = false;
    if (!result.available) { await browseFolders(path, target); $("folder-description").textContent += " · System picker unavailable; choose a location here."; }
    else if (result.paths.length) applyPickedPath(result.paths[0], target);
  } catch (error) { showError(error); }
  finally { pickerBusy = false; $("main-content").inert = false; $("picker-status").hidden = true; }
}
async function openSystemFolder(path) {
  try { await post("/api/system/open-folder", {path}); }
  catch (error) { showError(error); }
}
async function browseFolders(path, target = null) {
  if (busy) return; clearError();
  try {
    const query = new URLSearchParams(); if (path) query.set("path", path); if (target?.kind === "neuron-estimates") query.set("files", "estimates"); else if (target?.field?.kind === "file" || target?.onpick) query.set("files", "all");
    const result = await request(`/api/folders?${query}`);
    folder = result; folderTarget = target; $("folders").hidden = false; $("folder-title").textContent = target ? target.kind === "data-base" ? "Choose the base folder containing recordings" : target.kind === "box-cache" ? "Choose a local download folder" : target.kind === "neuron-estimates" ? "Choose a CNMF-E estimates file" : target.kind === "neuron-output" ? "Choose a curation output folder" : target.kind === "movie-files" ? "Choose a recording movie" : `Choose ${target.field.label.toLowerCase()}` : "Open a project";
    $("folder-path").value = result.path; $("parent-folder").disabled = result.path === result.parent;
    $("use-folder").textContent = target ? "Use this folder" : "Open this project"; $("use-folder").disabled = (target?.kind === "neuron-estimates" || target?.field?.kind === "file" || Boolean(target?.onpick)) || (!target && !result.has_experiments);
    $("breadcrumbs").replaceChildren(...result.breadcrumbs.flatMap((crumb, index) => {
      const button = element("button", crumb.name); button.onclick = () => browseFolders(crumb.path, folderTarget);
      return index ? [element("span", "/"), button] : [button];
    }));
    $("folder-description").textContent = target ? result.path : result.has_experiments ? `Project found${result.has_parameters ? " · analysis settings found" : " · no analysis settings file"}` : "Open a folder to find your project. A project contains experiments.csv.";
    const rows = result.folders.map(item => {
      const tr = element("tr", undefined, "folder-row"); const cell = element("td"), button = element("button", item.name, "row-open"); button.tabIndex = -1; cell.append(button);
      tr.append(cell, element("td", item.project ? "Project folder" : "Folder", "folder-kind")); actionableRow(tr, () => browseFolders(item.path, folderTarget)); return tr;
    });
    for (const file of result.files) {
      const tr = element("tr", undefined, `folder-file${(file.name === "experiments.csv" && !target) || target?.kind === "neuron-estimates" ? " folder-row" : ""}`);
      tr.append(element("td", file.name), element("td", target?.kind === "neuron-estimates" ? "CNMF-E estimates" : target?.field?.kind === "file" || target?.onpick ? "File" : file.name === "experiments.csv" ? "Experiment list" : file.name === "analysis_parameters.csv" ? "Analysis settings" : "CSV file", "folder-kind"));
      if (target?.kind === "neuron-estimates") actionableRow(tr, () => { chooseNeuronSource(file.path); $("folders").hidden = true; $("neuron-load").focus(); });
      if (target?.field?.kind === "file" || target?.onpick) actionableRow(tr, () => { applyPickedPath(file.path, target); $("folders").hidden = true; });
      if (file.name === "experiments.csv" && !target) actionableRow(tr, () => openProject(result.path)); rows.push(tr);
    }
    $("folder-list").replaceChildren(...rows); $("folder-empty").hidden = rows.length !== 0;
    $("folder-empty").textContent = target?.kind === "neuron-estimates" ? "No folders or estimates files in this location." : target?.field?.kind === "file" || target?.onpick ? "No folders or files in this location." : "No folders or CSV files in this location.";
    $("folders").scrollIntoView({block: "start"}); $("use-folder").focus({preventScroll: true});
  } catch (error) { showError(error); }
}
$("open-project").onclick = () => browse(project?.path || projects[0]?.path);
$("close-folders").onclick = () => { $("folders").hidden = true; };
$("home-folder").onclick = () => browseFolders(null, folderTarget); $("root-folder").onclick = () => browseFolders("/", folderTarget);
$("parent-folder").onclick = () => browseFolders(folder.parent, folderTarget);
$("folder-form").onsubmit = event => { event.preventDefault(); browseFolders($("folder-path").value.trim(), folderTarget); };
$("use-folder").onclick = () => {
  if (folderTarget?.kind === "box-cache") { $("box-download-path").value = folder.path; $("folders").hidden = true; $("box-finish").focus(); }
  else if (folderTarget?.kind === "neuron-output") { $("neuron-output-path").value = folder.path; $("folders").hidden = true; }
  else if (folderTarget?.kind === "data-base") { dataBases.set(project.id, folder.path); $("folders").hidden = true; renderAnalysis(); }
  else if (folderTarget) { const {field, section} = folderTarget; updateValue(field, folder.path, section); $("folders").hidden = true; renderEditor(); if (section === activeTab) document.querySelector(`[data-key="${CSS.escape(field.key)}"]`)?.focus(); }
  else openProject(folder.path);
};
$("search").oninput = renderProjects; $("missing-only").onchange = renderProjects;
$("back-projects").onclick = () => { if (!canLeave()) return; resetEditor(); clearError(); $("folders").hidden = true; $("detail").hidden = true; $("home").hidden = false; renderProjects(); };
$("error-reload").onclick = () => reloadProject(project.id);
$("metadata-tab").onclick = () => { if (!busy) { activeTab = "metadata"; $("field-search").value = ""; savedMessage = ""; renderEditor(); } };
$("parameters-tab").onclick = () => { if (!busy) { activeTab = "parameters"; $("field-search").value = ""; savedMessage = ""; renderEditor(); } };
$("add-settings").onclick = () => { creating = true; renderEditor(); };
$("apply-source").onclick = async () => {
  if (!experiment || !$("copy-source").value) return;
  if (dirty("parameters") && !window.confirm("Replace unsaved analysis settings with values from the selected project?")) return;
  clearError(); busy = true; $("apply-source").disabled = true;
  try {
    const values = await sourceSettings($("copy-source").value, experiment.fields.parameters.map(field => field.key));
    drafts.parameters = {};
    for (const [key, value] of Object.entries(values)) if (value !== (experiment.parameters?.[key] || "")) drafts.parameters[key] = value;
    if (experiment.parameters === null) creating = true;
    savedMessage = "Settings populated. Review and save them."; renderEditor();
  } catch (error) { showError(error); }
  finally { busy = false; $("apply-source").disabled = false; updateSaveBar(); }
};
$("cancel-new").onclick = () => { $("new-experiment").hidden = true; newProject = null; };
$("new-experiment-form").onsubmit = async event => {
  event.preventDefault(); if (!newProject || busy) return;
  clearError(); busy = true;
  try {
    const metadata = {};
    if (newProject.metadata_columns.includes("id")) metadata.id = $("new-subject").value;
    if (newProject.metadata_columns.includes("date (YYMMDD)") && $("new-date").value)
      metadata["date (YYMMDD)"] = $("new-date").value.slice(2).replaceAll("-", "");
    const parameters = await sourceSettings($("new-source").value, newProject.parameter_columns);
    const result = await post("/api/experiment/create", {project: newProject.id, number: $("new-number").value.trim(), metadata, parameters, versions: newProject.versions});
    replaceProject(result.project); expanded.add(newProject.id); $("new-experiment").hidden = true;
    const id = newProject.id, number = result.experiment.number; newProject = null; renderProjects();
    busy = false; await selectExperiment(id, number);
  } catch (error) { showError(error); }
  finally { busy = false; }
};
$("field-search").oninput = renderEditor; $("editor-form").onsubmit = saveChanges;
$("discard").onclick = () => { if (!busy && window.confirm("Discard the unsaved changes in this section?")) { drafts[activeTab] = {}; if (activeTab === "parameters") creating = false; savedMessage = ""; renderEditor(); } };
window.addEventListener("beforeunload", event => { if (anyDirty()) { event.preventDefault(); event.returnValue = ""; } });
request("/api/projects").then(result => { projects = result.projects; if (projects.length) expanded.add(projects[0].id); renderProjects(); if (result.startup_error) showError(new Error(result.startup_error)); }).catch(showError);

function setWorkspace(view) {
  if (busy) return;
  workspaceView = view; renderWorkspace();
}
function renderWorkspace() {
  if (!experiment) return;
  for (const button of $("workspace-tabs").querySelectorAll("button")) button.setAttribute("aria-current", button.dataset.view === workspaceView ? "page" : "false");
  $("overview-panel").hidden = workspaceView !== "overview";
  $("editor-panel").hidden = workspaceView !== "editor";
  $("unconnected-panel").hidden = workspaceView !== "history";
  const messages = {
    history: ["History · not connected yet", "Scientific version history and attached Git repositories are not connected yet. CSV saves keep a copy of the previous file; the latest backup location appears in File details after saving."],
  };
  if (messages[workspaceView]) { $("unconnected-title").textContent = messages[workspaceView][0]; $("unconnected-text").textContent = messages[workspaceView][1]; }
  $("unconnected-edit").hidden = workspaceView === "history";
  const row = project.experiments.find(item => item.number === experiment.number);
  const facts = [["Subject", row.subject || "Not set"], ["Recorded", friendlyDate(row.date)], ["Experiment number", experiment.number], ["Analysis settings", experiment.parameter_error ? "File needs attention" : experiment.parameters ? "Available" : "Missing"]];
  $("experiment-overview").replaceChildren(...facts.flatMap(([label, value]) => [element("dt", label), element("dd", value)]));
  $("experiment-attention").replaceChildren(element("p", experiment.parameter_error || (experiment.parameters ? "Experiment details and analysis settings are ready to edit." : `Experiment ${experiment.number} has no analysis settings. Add them in Data & settings.`)));
  if (typeof renderAnalysis === "function") renderAnalysis();
  if (typeof renderJobScripts === "function") renderJobScripts();
  if (typeof renderNeurons === "function") renderNeurons();
  $("recording-overview").replaceChildren(...experiment.recordings.map(recording => {
    const section = element("section", undefined, "recording-summary"); section.append(element("h4", recording.name));
    section.append(element("p", recording.directory || "Local folder not set", "recording-path"));
    if (recording.box_url) { const link = element("a", `Open Box folder ${recording.box_id}`); link.href = recording.box_url; link.target = "_blank"; link.rel = "noopener noreferrer"; section.append(link); }
    else section.append(element("p", "Box folder not set"));
    return section;
  }));
}
for (const button of $("workspace-tabs").querySelectorAll("button")) button.onclick = () => setWorkspace(button.dataset.view);
$("overview-edit").onclick = () => setWorkspace("editor");
$("unconnected-edit").onclick = () => { activeTab = "parameters"; renderEditor(); setWorkspace("editor"); };
$("overview-box").onclick = () => $("box-setup-button").click();
