"use strict";
// Applies the saved colour theme, or the system theme, before the page first paints.
// Loaded without defer; shell.js provides the toggles.
(() => {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const saved = () => { try { return localStorage.getItem("ace-gui-theme"); } catch { return null; } };
  const chosen = () => ["light", "dark"].includes(saved()) ? saved() : null;
  document.documentElement.dataset.theme = chosen() || (media.matches ? "dark" : "light");
  media.addEventListener("change", event => {
    if (chosen()) return;
    document.documentElement.dataset.theme = event.matches ? "dark" : "light";
    document.dispatchEvent(new Event("ace-themechange"));
  });
})();
