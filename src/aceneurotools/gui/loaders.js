"use strict";
// Loaders page: ephys loader definitions in <project>/loaders/<name>.json.
// The server (gui/loaders.py) validates, saves and checks definitions with
// aceneurotools.shared.loader_definitions; this page only edits text and shows results.
(() => {
  const state = {
    ready: null,          // Promise for the loaded fragment and schema.
    schema: null,         // Choices and templates from /api/loaders/schema.
    projectId: null,
    list: null,           // Result of GET /api/loaders.
    open: null,           // {name: saved name or null, digest, saved: saved text or null, text}
    problems: [],
    validateTimer: 0, validateSeq: 0, editorSeq: 0, working: false,
  };
  const page = aceFeatures.addPage({id: "loaders", label: "Ephys loaders", icon: "i-sliders", render: current => show(current)});
  const changed = () => Boolean(state.open) && state.open.text !== state.open.saved;
  aceFeatures.addUnsaved(changed, closeEditor);

  // Leaving the page was confirmed (aceFeatures checks unsaved work), so drop the draft.
  new MutationObserver(() => { if (page.hidden) closeEditor(); }).observe(page, {attributes: true, attributeFilter: ["hidden"]});

  const project = () => projects.find(item => item.id === state.projectId) || null;
  const query = extra => new URLSearchParams({project: state.projectId, ...extra}).toString();
  const normalizeText = text => text.replace(/^\uFEFF/, "");
  const lines = text => text.split("\n").map(item => item.trim()).filter(Boolean);
  const SYNC_DEFAULTS = {
    event_labels: sync => ({strategy: "event_labels", labels: Array.isArray(sync.labels) ? sync.labels : []}),
    digital_threshold: sync => ({strategy: "digital_threshold", channel: typeof sync.channel === "string" ? sync.channel : "", threshold: typeof sync.threshold === "number" ? sync.threshold : 0.5, edge: sync.edge || "rising"}),
    shared_clock: () => ({strategy: "shared_clock"}),
  };

  // ── Messages ──────────────────────────────────────────────────────────────
  function fail(error, heading = "Could not complete this action") {
    $("loaders-error-heading").textContent = heading;
    $("loaders-error-text").textContent = error.message;
    $("loaders-error-reload").hidden = !(error.reload && state.open?.name);
    $("loaders-error").hidden = false; $("loaders-error").focus();
  }
  const clearFail = () => { $("loaders-error").hidden = true; };
  async function working(action) {
    if (state.working) return;
    const projectId = state.projectId;
    state.working = true; clearFail();
    for (const id of ["loaders-save", "loaders-discard", "loaders-delete", "loaders-refresh", "loaders-new", "loaders-detect", "loaders-experiment"]) $(id).disabled = true;
    try { await action(); }
    catch (error) { fail(error); }
    finally {
      state.working = false;
      for (const id of ["loaders-delete", "loaders-refresh", "loaders-new", "loaders-detect", "loaders-experiment"]) $(id).disabled = false;
      syncState();
      if (projectId !== state.projectId) refresh();
    }
  }

  // ── Page and project ──────────────────────────────────────────────────────
  async function prepare() {
    await aceFeatures.fragment("loaders.html", page);
    $("loaders-refresh").onclick = () => working(async () => { await loadList(); await detect(); });
    $("loaders-experiment").onchange = () => working(detect);
    $("loaders-new").onclick = backToTemplates;
    $("loaders-back").onclick = backToTemplates;
    $("loaders-project").onchange = () => {
      if (!confirmDiscard()) { $("loaders-project").value = state.projectId; return; }
      closeEditor(); state.projectId = $("loaders-project").value; refresh();
    };
    $("loaders-error-reload").onclick = () => { clearFail(); if (state.open?.name) openDefinition(state.open.name, true); };
    $("loaders-json").oninput = () => { state.open.text = $("loaders-json").value; fillForm(); syncState(); scheduleValidate(); };
    for (const field of page.querySelectorAll(".loaders-form [data-path]")) field.addEventListener(field.tagName === "SELECT" ? "change" : "input", () => formChanged(field));
    $("loaders-editor").onsubmit = event => { event.preventDefault(); save(); };
    $("loaders-discard").onclick = discard;
    $("loaders-delete").onclick = remove;
    $("loaders-detect").onclick = () => working(detect);
    try { state.schema = await request("/api/loaders/schema"); }
    catch (error) { fail(error, "The loader editor could not load"); return; }
    const {choices, templates, preview} = state.schema;
    const options = (select, values, label = value => value) => select.replaceChildren(...values.map(value => { const option = element("option", label(value)); option.value = value; return option; }));
    options($("loaders-f-io"), choices.neo_ios);
    options($("loaders-f-dtype"), choices.sample_dtypes);
    $("loaders-preview-note").textContent = preview.note;
    $("loaders-preview").title = preview.note;
    $("loaders-templates").replaceChildren(...templates.map(template => {
      const button = element("button", undefined, "loaders-template"); button.type = "button";
      button.append(element("strong", template.label), element("span", template.description));
      button.onclick = () => startFrom(template);
      return button;
    }));
  }

  async function show(current) {
    state.ready ||= prepare();
    try { await state.ready; }
    catch (error) { state.ready = null; showError(error); return; }
    const available = projects.map(item => item.id);
    if (current) state.projectId = current.id;
    else if (!available.includes(state.projectId)) state.projectId = available.length === 1 ? available[0] : (available[0] || null);
    $("loaders-empty").hidden = Boolean(state.projectId);
    $("loaders-layout").hidden = !state.projectId;
    $("loaders-project").hidden = projects.length < 2;
    $("loaders-project").replaceChildren(...projects.map(item => { const option = element("option", item.name); option.value = item.id; return option; }));
    if (!state.projectId) { $("loaders-project-name").textContent = "No project open"; return; }
    $("loaders-project").value = state.projectId;
    refresh();
  }

  function refresh() {
    const current = project();
    $("loaders-project-name").textContent = current ? current.name : "Project";
    $("loaders-experiment").replaceChildren(...(current?.experiments || []).map(item => {
      const option = element("option", `${item.number} · ${item.subject || "No subject"}${item.ephys ? "" : " · no ephys folder"}`); option.value = item.number; return option;
    }));
    $("loaders-detect-result").replaceChildren();
    if (!state.open) showStart();
    working(async () => { await loadList(); if ($("loaders-experiment").value) await detect(); });
  }

  // ── List ──────────────────────────────────────────────────────────────────
  async function loadList() {
    const projectId = state.projectId;
    const result = await request(`/api/loaders?${query({})}`);
    if (projectId !== state.projectId) return;
    state.list = result;
    renderList();
  }

  function item(name, label, status, current, action) {
    const li = element("li"), button = element("button", undefined, "loaders-item"); button.type = "button";
    button.append(element("span", name, "loaders-item-name"), status, element("span", label || "", "loaders-item-label"));
    button.setAttribute("aria-current", current ? "true" : "false");
    button.onclick = action; li.append(button); return li;
  }

  function renderList() {
    const {definitions, builtins, folder_exists: exists} = state.list;
    const openName = state.open?.name;
    const own = definitions.map(entry => {
      const [text, kind] = !entry.editable ? ["Rename file", "warn"] : entry.valid ? ["Valid", "ok"] : [`${entry.problems.length || 1} problem${entry.problems.length === 1 ? "" : "s"}`, "bad"];
      const row = item(entry.name, entry.label || entry.file, element("span", text, `status status-${kind}`), entry.name === openName, () => {
        if (state.working) return;  // a pending save or delete finishes first
        if (!entry.editable) { fail(new Error(`${entry.file} cannot be opened here because its name is not a valid loader name. Rename the file using lowercase letters, digits and hyphens.`), "This file needs a new name"); return; }
        if (entry.name !== openName && confirmDiscard()) openDefinition(entry.name, true);
      });
      return row;
    });
    $("loaders-project-list").replaceChildren(...(own.length ? own : [element("li", exists ? "No loader definitions yet." : "No loaders folder yet. Saving a loader creates it.", "loaders-empty")]));
    $("loaders-builtin-list").replaceChildren(...builtins.map(entry => item(entry.name, entry.description, element("span", "Built in", "tag"), false, () => {
      if (state.working) return;  // closing the editor now would hide the pending result
      if (confirmDiscard()) { closeEditor(); showBuiltin(entry); }
    })));
  }

  function showStart() {
    $("loaders-start").hidden = false; $("loaders-builtin").hidden = true; $("loaders-editor").hidden = true;
    $("loaders-include-label").hidden = true;
  }

  function showBuiltin(entry) {
    $("loaders-start").hidden = true; $("loaders-editor").hidden = true; $("loaders-builtin").hidden = false;
    $("loaders-builtin-name").textContent = entry.name;
    $("loaders-builtin-class").textContent = entry.class;
    const props = [["What it reads", entry.description], ["Recognises", entry.recognises], ["Reserved names", entry.reserved.join(", ")]];
    $("loaders-builtin-props").replaceChildren(...props.filter(([, value]) => value).flatMap(([label, value]) => [element("dt", label), element("dd", value)]));
  }

  // ── Editor ────────────────────────────────────────────────────────────────
  function confirmDiscard() {
    return !changed() || window.confirm("Discard your unsaved changes to this loader?");
  }

  function backToTemplates() {
    if (state.working || !confirmDiscard()) return;
    closeEditor(); clearFail(); showStart();
    $("loaders-templates").querySelector("button")?.focus();
  }

  function closeEditor() {
    state.editorSeq++;
    window.clearTimeout(state.validateTimer); state.validateSeq++;
    state.open = null; state.problems = [];
    if ($("loaders-editor")) { $("loaders-editor").hidden = true; $("loaders-saved").textContent = ""; }
  }

  function startFrom(template) {
    openEditor({name: null, digest: null, saved: null, text: template.text});
    $("loaders-f-name").focus(); $("loaders-f-name").select();
  }

  async function openDefinition(name, force = false) {
    if (!force && !confirmDiscard()) return;
    const open = state.open, text = open?.text, projectId = state.projectId, editorSeq = state.editorSeq;
    const current = () => state.projectId === projectId && state.open === open &&
      state.editorSeq === editorSeq && state.open?.text === text;
    await working(async () => {
      let result;
      try { result = await request(`/api/loaders/definition?${new URLSearchParams({project: projectId, name})}`); }
      catch (error) { if (current()) throw error; return; }
      if (!current()) return;
      openEditor({name: result.name, digest: result.digest, saved: result.text, text: result.text});
      showProblems(result.problems);
    });
  }

  function openEditor(open) {
    closeEditor(); clearFail();
    state.open = open;
    $("loaders-start").hidden = true; $("loaders-builtin").hidden = true; $("loaders-editor").hidden = false;
    $("loaders-include-label").hidden = false;
    $("loaders-json").value = open.text;
    $("loaders-f-name").readOnly = Boolean(open.name);
    $("loaders-f-name-hint").textContent = open.name ? "Saved loaders keep their name. To rename one, start a new loader with the new name and delete this one." : "Lowercase letters and digits separated by hyphens. The file is saved as loaders/<name>.json.";
    $("loaders-delete").hidden = !open.name;
    $("loaders-discard").hidden = !open.name;
    fillForm(); syncState();
    if (state.list) renderList();
    scheduleValidate(0);
  }

  function parsed() {
    try { const value = JSON.parse(normalizeText(state.open.text)); return value && typeof value === "object" && !Array.isArray(value) ? value : null; }
    catch { return null; }
  }
  const at = (object, path) => path.split(".").reduce((value, key) => (value && typeof value === "object" ? value[key] : undefined), object);

  // JSON -> form. Fields keep their text when the JSON cannot be read.
  function fillForm() {
    const data = parsed();
    $("loaders-form-blocked").hidden = Boolean(data);
    for (const fieldset of page.querySelectorAll("fieldset.loaders-form")) fieldset.disabled = !data;
    if (!data) return;
    for (const field of page.querySelectorAll(".loaders-form [data-path]")) {
      if (field === document.activeElement) continue;
      const value = at(data, field.dataset.path);
      if (field.tagName === "TEXTAREA" && field.dataset.path !== "description") field.value = Array.isArray(value) ? value.join("\n") : "";
      else if (field.tagName === "SELECT") {
        if (value !== undefined && ![...field.options].some(option => option.value === String(value))) { const option = element("option", String(value)); option.value = String(value); field.append(option); }
        field.value = value === undefined ? "" : String(value);
      } else field.value = value === undefined || value === null ? "" : String(value);
    }
    const backend = at(data, "reader.backend"), strategy = at(data, "sync.strategy");
    $("loaders-io-field").hidden = backend !== "neo";
    $("loaders-dtype-field").hidden = $("loaders-count-field").hidden = backend !== "raw_binary";
    $("loaders-labels-field").hidden = strategy !== "event_labels";
    for (const id of ["loaders-channel-field", "loaders-threshold-field", "loaders-edge-field"]) $(id).hidden = strategy !== "digital_threshold";
    $("loaders-editor-title").textContent = data.label || data.name || "New loader";
  }

  function templateFor(backend) {
    const template = state.schema.templates.find(item => JSON.parse(item.text).reader?.backend === backend);
    return template ? JSON.parse(template.text) : null;
  }

  // Form -> JSON. The JSON stays the single draft; the form edits one key of it.
  function formChanged(field) {
    const data = parsed();
    if (!data) return;
    const path = field.dataset.path, raw = field.value;
    const [section, key] = path.includes(".") ? path.split(".") : [null, path];
    const parent = section ? (data[section] && typeof data[section] === "object" && !Array.isArray(data[section]) ? data[section] : (data[section] = {})) : data;
    if (path === "reader.backend") {
      const start = templateFor(raw);
      if (start) {
        data.reader = start.reader; data.time = start.time; data.channels = start.channels;
        if (raw === "raw_binary" && data.sync?.strategy === "event_labels") data.sync = start.sync;
      }
    } else if (path === "sync.strategy") {
      data.sync = SYNC_DEFAULTS[raw] ? SYNC_DEFAULTS[raw](data.sync || {}) : {strategy: raw};
    } else if (["detect.all_of", "detect.any_of", "detect.none_of", "sync.labels"].includes(path)) {
      const values = lines(raw);
      if (values.length || path === "sync.labels") parent[key] = values; else delete parent[key];
    } else if (["reader.channel_count", "sync.threshold"].includes(path)) {
      const number = Number(raw);
      parent[key] = raw.trim() !== "" && Number.isFinite(number) ? number : raw;
    } else if (path === "description" && raw === "") delete data.description;
    else parent[key] = raw;
    state.open.text = JSON.stringify(data, null, 2) + "\n";
    $("loaders-json").value = state.open.text;
    if (["reader.backend", "sync.strategy"].includes(path)) fillForm();
    else if (path === "label" || path === "name") $("loaders-editor-title").textContent = data.label || data.name || "New loader";
    syncState(); scheduleValidate();
  }

  function syncState() {
    if (!state.open || !$("loaders-editor")) return;
    const dirty = changed(), problems = state.problems.length;
    const [text, kind] = !state.open.name ? ["Not saved yet", "warn"] : dirty ? ["Unsaved changes", "warn"] : ["Saved", "ok"];
    $("loaders-editor-state").textContent = text; $("loaders-editor-state").className = `status status-${kind}`;
    $("loaders-editor-file").textContent = state.open.name ? `loaders/${state.open.name}.json` : "Not saved yet";
    $("loaders-save").disabled = state.working || problems > 0 || (Boolean(state.open.name) && !dirty);
    $("loaders-discard").disabled = state.working || !dirty;
    $("loaders-delete").disabled = state.working;
  }

  // ── Validation (debounced; the server is the only validator) ──────────────
  function scheduleValidate(delay = 400) {
    window.clearTimeout(state.validateTimer);
    state.validateSeq++;  // A check still in flight is for text that has since changed.
    $("loaders-check-state").textContent = "Checking…"; $("loaders-check-state").className = "loaders-check-state";
    state.validateTimer = window.setTimeout(validate, delay);
  }

  async function validate() {
    if (!state.open) return;
    const seq = ++state.validateSeq, open = state.open;
    try {
      const result = await post("/api/loaders/validate", {project: state.projectId, text: open.text, ...(open.name ? {name: open.name} : {})});
      if (seq === state.validateSeq && open === state.open) showProblems(result.problems);
    } catch (error) {
      if (seq === state.validateSeq) { $("loaders-check-state").textContent = `Could not check this loader: ${error.message}`; $("loaders-check-state").className = "loaders-check-state is-bad"; }
    }
  }

  function fieldFor(path) {
    const fields = [...page.querySelectorAll(".loaders-form [data-path]")];
    const match = fields.filter(field => !field.closest("[hidden]") && (path === field.dataset.path || path.startsWith(`${field.dataset.path}.`) || path.startsWith(`${field.dataset.path}[`)));
    if (match.length) return match[0];
    return path === "detect" ? $("loaders-f-any") : null;
  }

  function showProblems(problems) {
    state.problems = problems;
    for (const node of page.querySelectorAll(".loaders-field-problem")) node.remove();
    for (const field of page.querySelectorAll(".loaders-form [aria-invalid]")) field.removeAttribute("aria-invalid");
    const list = problems.map(problem => {
      const li = element("li");
      li.append(element("code", problem.path || "definition"), document.createTextNode(problem.message));
      const field = fieldFor(problem.path);
      if (field) {
        field.setAttribute("aria-invalid", "true");
        field.closest(".field").append(element("p", problem.path === field.dataset.path ? problem.message : `${problem.path}: ${problem.message}`, "loaders-field-problem"));
      }
      return li;
    });
    $("loaders-problems").replaceChildren(...list);
    $("loaders-check-state").textContent = problems.length ? `${problems.length} problem${problems.length === 1 ? "" : "s"} to fix before saving.` : "No problems found.";
    $("loaders-check-state").className = `loaders-check-state ${problems.length ? "is-bad" : "is-ok"}`;
    syncState();
  }

  // ── Save, discard, delete ─────────────────────────────────────────────────
  function save() {
    if (!state.open) return;
    const open = state.open, projectId = state.projectId;
    const submitted = open.text, digest = open.digest;
    const data = parsed(), name = open.name || (data && typeof data.name === "string" ? data.name : "");
    const current = () => state.open === open && state.projectId === projectId;
    working(async () => {
      let result;
      try {
        result = await post("/api/loaders/save", {project: projectId, name, text: submitted, digest});
      } catch (error) {
        if (current()) throw error;
        return;
      }
      if (!current()) return;
      const normalized = normalizeText(submitted);
      const saved = normalized.endsWith("\n") ? normalized : normalized + "\n";
      // Only the submitted snapshot reached disk. Keep edits made during POST dirty.
      if (open.text === submitted) open.text = saved;
      Object.assign(open, {name: result.name, digest: result.digest, saved});
      openEditor(open);
      $("loaders-saved").textContent = result.backup ? `Saved. The previous version was kept in ${result.backup}.` : `Saved as loaders/${result.name}.json.`;
      try { await loadList(); }
      catch (error) { if (current()) throw error; }
    });
  }

  function discard() {
    // While a save or delete is pending, the file may already have changed; discarding then would hide it.
    if (state.working || !state.open?.name || !confirmDiscard()) return;
    openEditor({...state.open, text: state.open.saved});
  }

  function remove() {
    const open = state.open, projectId = state.projectId;
    if (!open?.name) return;
    if (!window.confirm(`Delete the loader "${open.name}"? A copy is kept in the project's .ace-gui-backups folder.`)) return;
    const text = open.text;
    const current = () => state.open === open && state.projectId === projectId;
    working(async () => {
      let result;
      try { result = await post("/api/loaders/delete", {project: projectId, name: open.name, digest: open.digest}); }
      catch (error) { if (current()) throw error; return; }
      if (!current()) return;
      let editorSeq;
      if (open.text !== text) {
        // Deletion succeeded, but never discard edits typed while it was pending.
        Object.assign(open, {name: null, digest: null, saved: null});
        openEditor(open);
      } else { closeEditor(); showStart(); }
      editorSeq = state.editorSeq;
      $("loaders-detect-result").replaceChildren(element("p", `Deleted ${result.name}. A copy was kept in ${result.backup}.`, "muted"));
      try { await loadList(); }
      catch (error) { if (state.projectId === projectId && state.editorSeq === editorSeq) throw error; }
    });
  }

  // ── Check against an experiment ───────────────────────────────────────────
  function matchLine(name, matches, extra = []) {
    const li = element("li");
    li.append(element("code", name), element("span", matches ? "Recognises this folder" : "No match", `status status-${matches ? "ok" : "warn"}`), ...extra);
    return li;
  }
  function hits(patterns) {
    const text = patterns.map(item => `${item.pattern}: ${item.count} found${item.examples.length ? ` (${item.examples.join(", ")}${item.count > item.examples.length ? ", …" : ""})` : ""}`).join(" · ");
    return text ? [element("span", text, "loaders-hits")] : [];
  }

  function suggestionAction(suggestion) {
    if (state.working || !confirmDiscard()) return;
    if (suggestion.kind === "builtin") {
      const entry = state.list?.builtins.find(item => item.name === suggestion.name);
      if (entry) { closeEditor(); showBuiltin(entry); }
    } else if (suggestion.kind === "project") {
      openDefinition(suggestion.name, true);
    } else {
      const backend = suggestion.kind === "neo" ? "neo" : "raw_binary";
      const data = templateFor(backend);
      if (!data) return;
      data.detect = {any_of: suggestion.patterns};
      if (backend === "neo") {
        data.reader.io = suggestion.name;
        data.reader.path_argument = suggestion.path_argument;
        data.reader.args = suggestion.args || {};
        if (suggestion.path_argument === "dirname") {
          data.reader.path_from = {source: "recording_folder"}; data.reader.files = [];
        }
      }
      if (data.reader.files.length) data.reader.files[0].pattern = suggestion.patterns[0];
      startFrom({text: JSON.stringify(data, null, 2) + "\n"});
    }
  }

  function suggestionCards(suggestions) {
    const box = element("div");
    box.append(element("h3", suggestions.length ? "Suggested next step" : "No recognised loader or file type"));
    if (!suggestions.length) {
      box.append(element("p", "Choose Neo reader or Raw binary file below using your acquisition system documentation. No settings have been guessed.", "muted"));
      return box;
    }
    const label = element("label", "Loader option"); label.htmlFor = "loaders-suggestion";
    const select = element("select"); select.id = "loaders-suggestion";
    select.setAttribute("aria-describedby", "loaders-suggestion-reason");
    if (suggestions.length > 1) {
      const placeholder = element("option", "Choose a loader…");
      placeholder.value = ""; placeholder.disabled = true; select.append(placeholder);
    }
    suggestions.forEach((suggestion, index) => {
      const suffix = suggestion.kind === "builtin" ? " (built in)" : suggestion.kind === "project" ? " (saved)" : "";
      const option = element("option", suggestion.label + suffix); option.value = String(index); select.append(option);
    });
    select.value = suggestions.length === 1 ? "0" : "";
    const button = element("button"); button.type = "button";
    const reason = element("p", undefined, "muted"); reason.id = "loaders-suggestion-reason";
    reason.setAttribute("aria-live", "polite");
    let selected = null;
    const update = () => {
      selected = select.value === "" ? null : suggestions[Number(select.value)];
      button.disabled = !selected;
      button.textContent = selected?.kind === "builtin" ? "View configured loader" : selected?.kind === "project" ? "Open saved loader" : "Create loader";
      reason.textContent = selected ? selected.reason + (selected.kind === "project" ? " This definition is configured, but using it in analyses still requires the pending loader integration." : "") : "Several options match. Choose one to see its details; ACE has not selected a loader.";
    };
    select.onchange = update;
    button.onclick = () => { if (selected) suggestionAction(selected); };
    const controls = element("div", undefined, "input-row loaders-suggestion");
    controls.append(select, button); box.append(label, controls, reason);
    update();
    return box;
  }

  async function detect() {
    const number = $("loaders-experiment").value;
    if (!number) { fail(new Error("This project has no experiments to check.")); return; }
    const include = state.open && !$("loaders-include-label").hidden && $("loaders-include").checked;
    const projectId = state.projectId;
    const result = await post("/api/loaders/detect", {project: projectId, number, ...(include ? {text: state.open.text} : {})});
    if (projectId !== state.projectId || number !== $("loaders-experiment").value) return;
    const out = $("loaders-detect-result");
    if (result.status !== "ok") {
      const notice = element("div", undefined, "notice");
      notice.append(element("strong", result.status === "no-directory" ? "No ephys directory" : "Folder not available"), element("p", result.message));
      if (result.checked?.length) notice.append(element("p", `Looked in: ${result.checked.join("; ")}`));
      out.replaceChildren(notice); return;
    }
    const nodes = [suggestionCards(result.suggestions || []), element("p", `Folder: ${result.folder}`, "muted")];
    nodes.push(element("h3", "Built-in loaders"));
    const builtins = element("ul");
    builtins.append(...result.builtins.map(item => matchLine(item.name, item.matches, item.error ? [element("span", `Check failed: ${item.error}`, "loaders-hits")] : [])));
    nodes.push(builtins, element("p", result.builtin_used ? `Analyses use ${result.builtin_used} for this folder today.` : "No built-in loader recognises this folder, so ephys analyses cannot read it yet.", "muted"));
    nodes.push(element("h3", "This project's loaders"));
    const own = element("ul");
    own.append(...result.definitions.map(item => matchLine(item.name, item.matches, hits(item.patterns))));
    if (!result.definitions.length) own.append(element("li", "No valid saved loaders.", "muted"));
    nodes.push(own);
    if (result.skipped.length) nodes.push(element("p", `Skipped because they have problems: ${result.skipped.join(", ")}`, "muted"));
    if (result.draft) {
      nodes.push(element("h3", "The loader you are editing"));
      const draft = element("ul");
      draft.append(result.draft.valid ? matchLine(result.draft.name, result.draft.matches, hits(result.draft.patterns)) : element("li", "Fix its problems first to check it.", "muted"));
      nodes.push(draft);
    }
    out.replaceChildren(...nodes);
  }
})();
