"use strict";
// Feature registry: lets GUI features add workspace tabs, project-level pages and
// unsaved-work checks without editing app.js or index.html.
//
// A feature is a Python module listed in gui/features.py (see gui/routes.py) plus
// the scripts it names. Those scripts load after the core scripts, in order, and
// register themselves here, for example:
//
//   const panel = aceFeatures.addWorkspaceView({view: "plots", label: "Plots", render: () => drawPlots(experiment)});
//   const page = aceFeatures.addPage({id: "study", label: "Study", icon: "i-book", render: current => drawStudy(current)});
//   aceFeatures.addUnsaved(() => studyDraftChanged, () => { studyDraft = null; });
//
// Workspace views appear as tabs beside Overview/Results and render for the open
// experiment. Pages appear in the left navigation and receive the current project
// (or null when none is selected). Leaving a page or experiment with unsaved
// feature drafts asks for confirmation; if the user leaves anyway, each feature's
// discard callback runs so stale drafts do not block later navigation.
const aceFeatures = (() => {
  const CORE_VIEWS = new Set(["overview", "editor", "crop", "neurons", "results", "history", "review", "run-settings", "unconnected", "job"]);
  const CORE_PAGES = ["home", "detail", "box-setup"];
  const NAME = /^[a-z][a-z0-9-]*$/;
  const views = new Map(), pages = new Map(), unsavedChecks = [];
  let activePage = null;

  function claimIds(...ids) {
    const taken = ids.filter(id => document.getElementById(id));
    if (taken.length) throw new Error(`Feature element ids are already used: ${taken.join(", ")}`);
  }

  function addWorkspaceView({view, label, render = () => {}}) {
    if (!NAME.test(view) || CORE_VIEWS.has(view) || views.has(view)) throw new Error(`Workspace view already exists or is invalid: ${view}`);
    claimIds(`${view}-panel`);
    const button = element("button", label); button.type = "button"; button.dataset.view = view;
    button.onclick = () => setWorkspace(view);
    $("workspace-tabs").append(button);
    const panel = element("section", undefined, "panel"); panel.id = `${view}-panel`; panel.hidden = true;
    $("feature-panels").append(panel);
    views.set(view, {panel, render});
    return panel;
  }

  // Called last by renderWorkspace in app.js for every workspace change.
  function renderWorkspace(current) {
    for (const [view, {panel, render}] of views) {
      panel.hidden = view !== current;
      if (view !== current) continue;
      try { render(experiment); }
      catch (error) { console.error(error); showError(new Error(`This tab could not be shown: ${error.message}`)); }
    }
  }

  function addPage({id, label, icon: iconName = "i-file", render = () => {}}) {
    if (!NAME.test(id) || CORE_PAGES.includes(id) || pages.has(id)) throw new Error(`Page already exists or is invalid: ${id}`);
    claimIds(`nav-${id}`, `${id}-page`);
    const button = element("button", undefined, "nav-item"); button.type = "button"; button.id = `nav-${id}`;
    button.append(icon(iconName), element("span", label));
    button.onclick = () => showPage(id);
    $("nav-features").append(button);
    const page = element("section", undefined, "page"); page.id = `${id}-page`; page.hidden = true; page.setAttribute("aria-label", label);
    $("feature-pages").append(page);
    pages.set(id, {button, page, render});
    return page;
  }

  function currentProject() { return projects.find(item => item.id === currentProjectId) || null; }

  function showPage(id) {
    const entry = pages.get(id);
    if (!entry || busy || (typeof boxBusy !== "undefined" && boxBusy)) return;
    if (id === activePage) return;
    // Always ask: experiment edits and other features' drafts are both covered by canLeave.
    if (!canLeave()) return;
    if (!$("detail").hidden) resetEditor();
    // Leave Box setup through its own exit so it restores buttons and clears secrets.
    if (!$("box-setup").hidden && typeof closeBox === "function") closeBox(true);
    clearError();
    activePage = id;  // Set first: the observer below ignores pages hidden on purpose here.
    for (const core of CORE_PAGES) $(core).hidden = true;
    $("folders").hidden = true;
    for (const [other, {button, page}] of pages) { page.hidden = other !== id; button.setAttribute("aria-current", other === id ? "page" : "false"); }
    $("nav-experiments").setAttribute("aria-current", "false");
    document.body.dataset.view = `feature-${id}`;
    try { entry.render(currentProject()); }
    catch (error) { console.error(error); showError(new Error(`This page could not be shown: ${error.message}`)); }
    window.scrollTo(0, 0);
  }

  function hidePages() {
    if (activePage === null) return;
    activePage = null;
    for (const {button, page} of pages.values()) { page.hidden = true; button.setAttribute("aria-current", "false"); }
  }

  // Showing any core page (from app.js or box.js) closes the feature page. The
  // callback checks the current state, so pages hidden again by showPage are ignored.
  const observer = new MutationObserver(records => {
    if (records.some(record => !record.target.hidden)) { hidePages(); if (typeof syncNavigation === "function") syncNavigation(); }
  });
  for (const core of CORE_PAGES) observer.observe($(core), {attributes: true, attributeFilter: ["hidden"]});

  // check() returns true while the feature has unsaved work; discard() abandons it.
  function addUnsaved(check, discard = () => {}) { unsavedChecks.push({check, discard}); }
  function unsaved() {
    // A failing check counts as unsaved: better an extra question than lost work.
    return unsavedChecks.some(({check}) => { try { return Boolean(check()); } catch (error) { console.error(error); return true; } });
  }
  function discard() {
    for (const {discard: drop} of unsavedChecks) { try { drop(); } catch (error) { console.error(error); } }
  }

  // Load an HTML fragment declared by a feature into a container.
  async function fragment(name, container) {
    const response = await fetch(`/${name}`);
    if (!response.ok) throw new Error(`This screen could not be loaded (${name}). Restart ACE and try again.`);
    const template = document.createElement("template"); template.innerHTML = await response.text();
    container.replaceChildren(template.content.cloneNode(true));
    return container;
  }

  // Feature scripts run after every core script, so they can use app.js state and helpers.
  async function load() {
    let manifest;
    try { manifest = await request("/api/features"); }
    catch (error) { console.error("Feature list unavailable", error); return; }
    for (const feature of manifest.features) {
      for (const name of feature.styles) { const link = document.createElement("link"); link.rel = "stylesheet"; link.href = `/${name}`; document.head.append(link); }
      for (const name of feature.scripts) {
        const script = document.createElement("script"); script.src = `/${name}`; script.async = false;
        script.onerror = () => showError(new Error(`Part of ACE could not load (${feature.name}). Restart ACE and try again.`));
        document.head.append(script);
      }
    }
  }
  document.addEventListener("DOMContentLoaded", load);

  return {addWorkspaceView, renderWorkspace, addPage, showPage, hidePages, activePage: () => activePage, addUnsaved, unsaved, discard, fragment, currentProject};
})();
