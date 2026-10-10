"use strict";
// Layout behaviour for the file-browser shell: navigation, sidebar, tabs, and modals.
// Application state lives in app.js; this file only reacts to the visible views.
const wideLayout = window.matchMedia("(min-width: 1025px)");
const remember = (key, value) => { try { localStorage.setItem(`ace-gui-${key}`, value); } catch { /* storage unavailable */ } };
const recall = key => { try { return localStorage.getItem(`ace-gui-${key}`); } catch { return null; } };

if (recall("nav-collapsed") === "true") document.body.classList.add("nav-collapsed");
if (recall("sidebar-collapsed") === "true") document.body.classList.add("sidebar-collapsed");
function syncNavToggle() {
  const collapsed = document.body.classList.contains("nav-collapsed");
  $("nav-collapse").setAttribute("aria-expanded", collapsed ? "false" : "true");
  $("nav-collapse").setAttribute("aria-label", collapsed ? "Expand navigation" : "Collapse navigation");
}
syncNavToggle();
$("nav-collapse").onclick = () => {
  remember("nav-collapsed", String(document.body.classList.toggle("nav-collapsed"))); syncNavToggle();
};
$("nav-toggle").onclick = () => document.body.classList.toggle("nav-open");
document.querySelector(".leftnav").addEventListener("click", event => {
  if (event.target.closest(".nav-item")) document.body.classList.remove("nav-open");
});
// A click outside the open navigation drawer (on its backdrop) closes it.
document.addEventListener("click", event => {
  if (document.body.classList.contains("nav-open") && !event.target.closest(".leftnav, #nav-toggle")) document.body.classList.remove("nav-open");
});

// Wide screens keep the details sidebar docked and collapsible; narrow screens show it as an overlay.
for (const button of document.querySelectorAll("[data-sidebar-toggle]")) {
  button.onclick = () => {
    if (wideLayout.matches) remember("sidebar-collapsed", String(document.body.classList.toggle("sidebar-collapsed")));
    else document.body.classList.toggle("sidebar-open");
  };
}

// Sidebar tabs, including those rendered later by app.js.
document.addEventListener("click", event => {
  const tab = event.target.closest(".sidebar-tabs [role='tab']");
  if (!tab) return;
  const aside = tab.closest(".sidebar");
  aside.dataset.activeTab = tab.dataset.tab;
  for (const other of aside.querySelectorAll(".sidebar-tabs [role='tab']")) other.setAttribute("aria-selected", other === tab ? "true" : "false");
  for (const view of aside.querySelectorAll("[data-panel]")) view.hidden = view.dataset.panel !== tab.dataset.tab;
});

// Workflow shortcuts on the experiment overview.
document.addEventListener("click", event => {
  const goto = event.target.closest("[data-goto]"), click = event.target.closest("[data-click]");
  if (goto) setWorkspace(goto.dataset.goto);
  else if (click) $(click.dataset.click).click();
});

// Highlight the navigation entry for the visible page.
function syncNavigation() {
  const boxOpen = !$("box-setup").hidden;
  $("nav-experiments").setAttribute("aria-current", boxOpen ? "false" : "page");
  $("box-setup-button").setAttribute("aria-current", boxOpen ? "page" : "false");
  document.body.dataset.view = boxOpen ? "box" : !$("detail").hidden ? "experiment" : "projects";
}
const viewObserver = new MutationObserver(syncNavigation);
for (const id of ["home", "detail", "box-setup"]) viewObserver.observe($(id), {attributes: true, attributeFilter: ["hidden"]});
syncNavigation();

$("error-close").onclick = () => { $("error").hidden = true; };

// Dark mode: theme.js applies the saved or system theme; these toggles save a choice.
function syncTheme() {
  const dark = document.documentElement.dataset.theme === "dark";
  $("theme-toggle").setAttribute("aria-pressed", dark ? "true" : "false");
  $("theme-toggle").title = dark ? "Switch to light mode" : "Switch to dark mode";
  $("theme-switch").setAttribute("aria-checked", dark ? "true" : "false");
}
function toggleTheme() {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next; remember("theme", next); syncTheme();
}
$("theme-toggle").onclick = toggleTheme;
$("theme-switch").onclick = toggleTheme;
document.addEventListener("ace-themechange", syncTheme);
syncTheme();

document.addEventListener("keydown", event => {
  if (event.key === "Escape") {
    for (const [dialog, close] of [["folders", "close-folders"], ["new-experiment", "cancel-new"], ["download-review", "download-dismiss"]]) {
      if (!$(dialog).hidden) { event.preventDefault(); $(close).click(); return; }
    }
    if (document.body.classList.contains("sidebar-open")) document.body.classList.remove("sidebar-open");
    else if (document.body.classList.contains("nav-open")) document.body.classList.remove("nav-open");
    else if (!$("error").hidden) $("error").hidden = true;
    return;
  }
  // "/" focuses the experiment search, as in most file browsers.
  if (event.key === "/" && !event.ctrlKey && !event.metaKey && !event.altKey && !event.target.closest("input, select, textarea, [contenteditable]")) {
    event.preventDefault(); $("search").focus(); $("search").select();
  }
});

// Clicking a modal's backdrop cancels it, like its close button.
for (const [dialog, close] of [["folders", "close-folders"], ["new-experiment", "cancel-new"]]) {
  $(dialog).addEventListener("click", event => { if (event.target === $(dialog)) $(close).click(); });
}
