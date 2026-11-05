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
//   aceFeatures.addUnsaved(() => studyDraftChanged);
//
// Workspace views appear as tabs beside Overview/Results and render for the open
// experiment. Pages appear in the left navigation and receive the current project
// (or null when none is selected).
const aceFeatures = (() => {
  const CORE_VIEWS = new Set(["overview", "editor", "crop", "neurons", "results", "history", "review", "run-settings"]);
  const CORE_PAGES = ["home", "detail", "box-setup"];
  const views = new Map(), pages = new Map(), unsavedChecks = [];
  let activePage = null;

  function addWorkspaceView({view, label, render = () => {}}) {
    if (!/^[a-z][a-z0-9-]*$/.test(view) || CORE_VIEWS.has(view) || views.has(view)) throw new Error(`Workspace view already exists or is invalid: ${view}`);
    const button = element("button", label); button.type = "button"; button.dataset.view = view;
    button.onclick = () => setWorkspace(view);
    $("workspace-tabs").append(button);
    const panel = element("section", undefined, "panel"); panel.id = `${view}-panel`; panel.hidden = true;
    $("feature-panels").append(panel);
    views.set(view, {panel, render});
    return panel;
  }

  // Called by renderWorkspace in app.js for every workspace change.
  function renderWorkspace(current) {
    for (const [view, {panel, render}] of views) {
      panel.hidden = view !== current;
      if (view === current) render(experiment);
    }
  }

  function addPage({id, label, icon: iconName = "i-file", render = () => {}}) {
    if (!/^[a-z][a-z0-9-]*$/.test(id) || CORE_PAGES.includes(id) || pages.has(id)) throw new Error(`Page already exists or is invalid: ${id}`);
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
    if (!entry || busy) return;
    if (!$("detail").hidden) { if (!canLeave()) return; resetEditor(); }
    clearError();
    activePage = id;  // Set first: the observer below ignores pages hidden on purpose here.
    for (const core of CORE_PAGES) $(core).hidden = true;
    $("folders").hidden = true;
    for (const [other, {button, page}] of pages) { page.hidden = other !== id; button.setAttribute("aria-current", other === id ? "page" : "false"); }
    $("nav-experiments").setAttribute("aria-current", "false");
    document.body.dataset.view = id;
    entry.render(currentProject());
    window.scrollTo(0, 0);
  }

  function hidePages() {
    if (activePage === null) return;
    activePage = null;
    for (const {button, page} of pages.values()) { page.hidden = true; button.setAttribute("aria-current", "false"); }
  }

  // Showing any core page (from app.js or box.js) closes the feature page.
  const observer = new MutationObserver(records => {
    if (records.some(record => !record.target.hidden)) { hidePages(); if (typeof syncNavigation === "function") syncNavigation(); }
  });
  for (const core of CORE_PAGES) observer.observe($(core), {attributes: true, attributeFilter: ["hidden"]});

  function addUnsaved(check) { unsavedChecks.push(check); }
  function unsaved() { return unsavedChecks.some(check => { try { return Boolean(check()); } catch { return false; } }); }

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

  return {addWorkspaceView, renderWorkspace, addPage, showPage, hidePages, activePage: () => activePage, addUnsaved, unsaved, fragment, currentProject};
})();
