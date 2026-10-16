"use strict";
// Each browser tab retains only this launch's capability. It is never placed in an API URL.
const launchToken = new URLSearchParams(location.hash.slice(1)).get("token");
if (launchToken) {
  sessionStorage.setItem("ace-launch-token", launchToken);
  history.replaceState(null, "", location.pathname + location.search);
}
const apiToken = launchToken || sessionStorage.getItem("ace-launch-token") || "";
function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${apiToken}`);
  return fetch(url, {...options, headers});
}
async function authenticatedImage(image, url) {
  const response = await apiFetch(url);
  if (!response.ok) { image.hidden = true; return; }
  const object = URL.createObjectURL(await response.blob());
  image.onload = image.onerror = () => URL.revokeObjectURL(object);
  image.src = object;
}
async function authenticatedDownload(event, url, name) {
  event.preventDefault();
  const response = await apiFetch(url);
  if (!response.ok) { showError(new Error("This output could not be downloaded. Reopen ACE and try again.")); return; }
  const object = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = object; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(object), 1000);
}
