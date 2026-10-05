"use strict";
const $ = id => document.getElementById(id);
let projects = [], project = null, experiment = null, activeTab = "metadata";
let drafts = {metadata: {}, parameters: {}}, creating = false, busy = false, selectionRequest = 0;
let folder = null, folderTarget = null, expanded = new Set(), editorExpanded = new Set(), savedMessage = "", lastBackup = "";
const element = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};
const dirty = section => Object.keys(drafts[section]).length > 0 || (section === "parameters" && creating);
const anyDirty = () => dirty("metadata") || dirty("parameters");
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
    resetEditor(); $("folders").hidden = true; $("detail").hidden = true; $("home").hidden = false; renderProjects();
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
function resetEditor() { selectionRequest++; experiment = null; drafts = {metadata: {}, parameters: {}}; creating = false; savedMessage = ""; lastBackup = ""; }
async function selectExperiment(projectId, number, tab = "metadata") {
  if (!canLeave()) return;
  clearError(); resetEditor(); const revision = ++selectionRequest;
  project = projects.find(item => item.id === projectId); activeTab = tab; $("field-search").value = "";
  $("home").hidden = true; $("detail").hidden = false; $("detail-loading").hidden = false; $("detail-content").hidden = true;
  const row = project.experiments.find(item => item.number === number);
  $("detail-project").textContent = project.name; $("detail-title").textContent = rowName(row);
  $("detail-subtitle").textContent = `Experiment ${number} · ${friendlyDate(row.date)}`;
  $("detail-title").scrollIntoView({block: "start"});
  try {
    const result = await request(`/api/experiment?project=${encodeURIComponent(projectId)}&number=${encodeURIComponent(number)}`);
    if (revision !== selectionRequest) return;
    experiment = result; $("detail-content").hidden = false; renderEditor();
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
  if (field.kind === "folder") {
    const browseButton = element("button", "Choose folder"); browseButton.type = "button";
    browseButton.onclick = () => browse(project.path, {field, section: activeTab}); controls.append(browseButton);
  }
  let boxLink;
  if (field.kind === "box") {
    boxLink = element("a", "Open Box folder", "box-link"); boxLink.target = "_blank"; boxLink.rel = "noopener noreferrer";
    const updateLink = raw => { boxLink.hidden = !/^[0-9]+$/.test(raw.trim()); boxLink.href = boxLink.hidden ? "#" : `https://app.box.com/folder/${raw.trim()}`; };
    updateLink(value); container.append(boxLink);
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
    renderProjects(); renderEditor();
  } catch (error) { showError(error); }
  finally { busy = false; $("editor-form").inert = false; updateSaveBar(); }
}
async function browse(path, target = null) {
  if (busy) return; clearError();
  try {
    const result = await request(`/api/folders${path ? `?path=${encodeURIComponent(path)}` : ""}`);
    folder = result; folderTarget = target; $("folders").hidden = false; $("folder-title").textContent = target ? `Choose ${target.field.label.toLowerCase()}` : "Open a project";
    $("folder-path").value = result.path; $("parent-folder").disabled = result.path === result.parent;
    $("use-folder").textContent = target ? "Use this folder" : "Open this project"; $("use-folder").disabled = !target && !result.has_experiments;
    $("breadcrumbs").replaceChildren(...result.breadcrumbs.flatMap((crumb, index) => {
      const button = element("button", crumb.name); button.onclick = () => browse(crumb.path, folderTarget);
      return index ? [element("span", "/"), button] : [button];
    }));
    $("folder-description").textContent = target ? result.path : result.has_experiments ? `Project found${result.has_parameters ? " · analysis settings found" : " · no analysis settings file"}` : "Open a folder to find your project. A project contains experiments.csv.";
    const rows = result.folders.map(item => {
      const tr = element("tr", undefined, "folder-row"); const cell = element("td"), button = element("button", item.name, "row-open"); button.tabIndex = -1; cell.append(button);
      tr.append(cell, element("td", item.project ? "Project folder" : "Folder", "folder-kind")); actionableRow(tr, () => browse(item.path, folderTarget)); return tr;
    });
    for (const file of result.files) {
      const tr = element("tr", undefined, `folder-file${file.name === "experiments.csv" && !target ? " folder-row" : ""}`);
      tr.append(element("td", file.name), element("td", file.name === "experiments.csv" ? "Experiment list" : file.name === "analysis_parameters.csv" ? "Analysis settings" : "CSV file", "folder-kind"));
      if (file.name === "experiments.csv" && !target) actionableRow(tr, () => openProject(result.path)); rows.push(tr);
    }
    $("folder-list").replaceChildren(...rows); $("folder-empty").hidden = rows.length !== 0;
    $("folders").scrollIntoView({block: "start"}); $("use-folder").focus({preventScroll: true});
  } catch (error) { showError(error); }
}
$("open-project").onclick = () => browse(project?.path || projects[0]?.path);
$("close-folders").onclick = () => { $("folders").hidden = true; };
$("home-folder").onclick = () => browse(null, folderTarget); $("root-folder").onclick = () => browse("/", folderTarget);
$("parent-folder").onclick = () => browse(folder.parent, folderTarget);
$("folder-form").onsubmit = event => { event.preventDefault(); browse($("folder-path").value.trim(), folderTarget); };
$("use-folder").onclick = () => {
  if (folderTarget) { const {field, section} = folderTarget; updateValue(field, folder.path, section); $("folders").hidden = true; renderEditor(); if (section === activeTab) document.querySelector(`[data-key="${CSS.escape(field.key)}"]`)?.focus(); }
  else openProject(folder.path);
};
$("search").oninput = renderProjects; $("missing-only").onchange = renderProjects;
$("back-projects").onclick = () => { if (!canLeave()) return; resetEditor(); clearError(); $("folders").hidden = true; $("detail").hidden = true; $("home").hidden = false; renderProjects(); };
$("error-reload").onclick = () => reloadProject(project.id);
$("metadata-tab").onclick = () => { if (!busy) { activeTab = "metadata"; $("field-search").value = ""; savedMessage = ""; renderEditor(); } };
$("parameters-tab").onclick = () => { if (!busy) { activeTab = "parameters"; $("field-search").value = ""; savedMessage = ""; renderEditor(); } };
$("add-settings").onclick = () => { creating = true; renderEditor(); };
$("field-search").oninput = renderEditor; $("editor-form").onsubmit = saveChanges;
$("discard").onclick = () => { if (!busy && window.confirm("Discard the unsaved changes in this section?")) { drafts[activeTab] = {}; if (activeTab === "parameters") creating = false; savedMessage = ""; renderEditor(); } };
window.addEventListener("beforeunload", event => { if (anyDirty()) { event.preventDefault(); event.returnValue = ""; } });
request("/api/projects").then(result => { projects = result.projects; if (projects.length) expanded.add(projects[0].id); renderProjects(); if (result.startup_error) showError(new Error(result.startup_error)); }).catch(showError);
