"use strict";
let boxStatus = {}, boxProof = null, boxPage = null, boxBusy = false, boxReturn = "home", boxMethod = "ccg";
let boxSuggestedFolder = "0", boxStep = 1, boxRecordingColumn = null;
function boxError(error) {
  $("box-error-text").textContent = error.message; $("box-error").hidden = false; $("box-error").focus();
}
function boxStepTo(step) {
  boxStep = step;
  $("box-steps").hidden = step === 2 || boxStatus.connected;
  for (let i = 1; i <= 3; i++) { $("box-step-" + i).hidden = step !== i; $("box-step-label-" + i).setAttribute("aria-current", step === i ? "step" : "false"); }
}
function renderBoxStatus() {
  $("box-indicator").textContent = boxStatus.connected ? `Box: ${boxStatus.account.name}` : boxStatus.saved ? "Box connection saved" : "Box not connected";
  const initials = boxStatus.connected ? boxStatus.account.name.split(/\s+/).filter(Boolean).map(word => word[0]).join("").slice(0, 2).toUpperCase() : "";
  $("box-dot").className = `status-dot${boxStatus.connected ? " is-on" : boxStatus.saved ? " is-saved" : ""}`;
  $("box-avatar").textContent = initials; $("box-avatar").title = $("box-indicator").textContent; $("box-avatar").hidden = !initials; $("box-avatar").classList.toggle("is-connected", Boolean(initials));
  $("box-saved-actions").hidden = !boxStatus.saved;
  $("box-reconnect").hidden = boxStatus.connected;
  $("box-disconnect").hidden = !boxStatus.connected;
  $("box-change-account").hidden = !boxStatus.connected;
  $("box-status").textContent = boxStatus.connected ? `Connected as ${boxStatus.account.name} (${boxStatus.account.login}).\nShared by all projects · Local download folder: ${boxStatus.download_path}` : boxStatus.saved ? `Your lab connection is saved and is reused automatically.\nLocal download folder: ${boxStatus.download_path || "Not set"}` : "Connect your lab's Box account once. Each experiment uses its own saved Box folder ID.";
  if (boxStatus.sdk_available === false) $("box-status").textContent += "\nBox support is missing from this Python environment. Use the ACE analysis environment with box-sdk-gen installed.";
}
async function boxAction(action) {
  if (boxBusy) return;
  boxBusy = true; $("box-error").hidden = true;
  $("box-setup").setAttribute("aria-busy", "true"); $("box-setup").inert = true;
  $("box-check").textContent = "Checking…";
  try { await action(); }
  catch (error) { boxError(error); }
  finally { boxBusy = false; $("box-setup").inert = false; $("box-setup").removeAttribute("aria-busy"); $("box-check").textContent = "Check connection"; if (!$("box-error").hidden) $("box-error").focus(); }
}
function invalidateBoxCheck() { boxProof = null; boxPage = null; $("box-next-1").disabled = true; $("box-account").textContent = ""; }
function boxCredentials() {
  return {method: $("box-method").value, client_id: $("box-client-id").value, client_secret: $("box-client-secret").value, subject_type: $("box-subject-type").value, subject_id: $("box-subject-id").value, token: $("box-token").value};
}
function updateBoxMethod() {
  const token = $("box-method").value === "token";
  $("box-ccg-fields").hidden = token; $("box-token-field").hidden = !token;
  for (const id of ["box-client-id", "box-client-secret", "box-subject-id"]) { $(id).required = !token; $(id).disabled = token; }
  $("box-token").required = token; $("box-token").disabled = !token; invalidateBoxCheck();
}
async function checkBox() {
  invalidateBoxCheck();
  const result = await post("/api/box/check", boxCredentials());
  boxProof = result.proof; boxMethod = result.method;
  $("box-account").textContent = `Verified: ${result.account.name} (${result.account.login})`;
  $("box-next-1").disabled = false;
  $("box-remember").checked = boxMethod === "ccg";
  $("box-remember-label").hidden = boxMethod === "token";
  $("box-storage-note").textContent = boxMethod === "token" ? "This temporary token is kept for this server session only." : "Saved credentials are stored in your private user settings, outside projects and CSV files.";
}
async function loadBoxFolder(number, marker = null) {
  $("box-next-2").disabled = true;
  const result = await post("/api/box/folders", {folder: number, marker});
  const append = marker && boxPage?.id === result.id;
  boxPage = result; $("box-folder-link").value = `https://app.box.com/folder/${result.id}`;
  const crumbs = [...result.breadcrumbs, {id: result.id, name: result.name}];
  if (!crumbs.some(crumb => crumb.id === "0")) crumbs.unshift({id: "0", name: "All files"});
  $("box-breadcrumbs").replaceChildren(...crumbs.map(crumb => { const button = element("button", crumb.name); button.onclick = () => boxAction(() => loadBoxFolder(crumb.id)); return button; }));
  const rows = result.entries.map(item => {
    const tr = element("tr", undefined, item.type === "folder" ? "folder-row" : "folder-file");
    tr.append(element("td", item.name), element("td", item.type === "folder" ? "Folder" : "File"));
    if (item.type === "folder") actionableRow(tr, () => boxAction(() => loadBoxFolder(item.id)));
    return tr;
  });
  if (append) $("box-folder-list").append(...rows); else $("box-folder-list").replaceChildren(...rows);
  $("box-folder-empty").hidden = $("box-folder-list").children.length > 0;
  $("box-more").hidden = !result.next_marker;
  $("box-folder-name").textContent = `Selected: ${result.name}`; $("box-next-2").disabled = false;
}
function closeBox(force = false) {
  if (boxBusy && !force) return;
  $("box-setup").hidden = true; $("folders").hidden = true;
  $(boxReturn).hidden = false; $("open-project").disabled = false;
  for (const id of ["box-client-secret", "box-token"]) $(id).value = "";
  invalidateBoxCheck(); boxRecordingColumn = null; $("box-setup-button").focus();
}
async function showBoxFolderPicker() {
  boxStepTo(2); $("box-next-2").disabled = true; $("box-folder-list").replaceChildren(); $("box-breadcrumbs").replaceChildren(); $("box-more").hidden = true; $("box-folder-name").textContent = "";
  $("box-folder-link").value = boxSuggestedFolder;
  await loadBoxFolder(boxSuggestedFolder);
}
async function openBox(column = null) {
  if (busy || boxBusy) return;
  boxRecordingColumn = column;
  boxReturn = $("detail").hidden ? "home" : "detail";
  $("open-project").disabled = true;
  $("home").hidden = true; $("detail").hidden = true; $("folders").hidden = true; $("box-setup").hidden = false;
  clearError(); $("box-error").hidden = true; invalidateBoxCheck(); boxStepTo(1);
  boxSuggestedFolder = column ? experiment.metadata[column] || "0" : "0";
  await boxAction(async () => {
    boxStatus = await request("/api/box/status");
    renderBoxStatus();
    if (boxStatus.saved && !boxStatus.connected) boxStatus = await post("/api/box/connect", {});
    renderBoxStatus();
    $("box-download-path").value = boxStatus.download_path || "";
    if (boxStatus.connected) {
      if (column) await showBoxFolderPicker();
      else { boxStepTo(3); $("box-finish").textContent = "Save download location"; $("box-summary").textContent = "Your connection is shared by every experiment. Folder IDs come from experiments.csv."; $("box-remember-label").hidden = true; }
    }
  });
}
function openBoxFolderPicker(column) {
  if (!mustSaveFirst()) return;
  openBox(column);
}
$("box-setup-button").onclick = () => openBox();
$("close-box").onclick = () => closeBox();
$("box-change-account").onclick = () => { invalidateBoxCheck(); boxStepTo(1); $("box-finish").textContent = "Finish setup"; };
$("box-method").onchange = updateBoxMethod;
$("box-subject-type").onchange = () => { $("box-subject-label").textContent = $("box-subject-type").value === "user" ? "Box user ID" : "Box enterprise ID"; invalidateBoxCheck(); };
for (const id of ["box-client-id", "box-client-secret", "box-subject-id", "box-token"]) $(id).oninput = invalidateBoxCheck;
$("box-connect-form").onsubmit = event => { event.preventDefault(); boxAction(checkBox); };
$("box-reconnect").onclick = () => boxAction(async () => { boxStatus = await post("/api/box/connect", {}); renderBoxStatus(); $("box-download-path").value = boxStatus.download_path; if (boxRecordingColumn) await showBoxFolderPicker(); else { boxStepTo(3); $("box-remember-label").hidden = true; $("box-finish").textContent = "Save download location"; } });
$("box-next-1").onclick = () => { $("box-summary").textContent = $("box-account").textContent; $("box-finish").textContent = "Finish setup"; boxStepTo(3); };
$("box-folder-form").onsubmit = event => { event.preventDefault(); boxAction(() => loadBoxFolder($("box-folder-link").value)); };
$("box-more").onclick = () => boxAction(() => loadBoxFolder(boxPage.id, boxPage.next_marker));
$("box-back-2").onclick = () => closeBox();
$("box-next-2").onclick = () => boxAction(async () => {
  const result = await post("/api/experiment/save", {project: project.id, number: experiment.number, versions: experiment.versions, section: "metadata", changes: {[boxRecordingColumn]: boxPage.id}});
  acceptSaved(result); closeBox(true);
});
$("box-back-3").onclick = () => { if (boxStatus.connected && !boxProof) closeBox(); else boxStepTo(1); };
$("box-choose-local").onclick = () => browse($("box-download-path").value || project?.path, {kind: "box-cache"});
$("box-finish").onclick = () => boxAction(async () => {
  boxStatus = await post(boxProof ? "/api/box/finish" : "/api/box/location", {proof: boxProof, download_path: $("box-download-path").value, remember: boxMethod === "ccg" && $("box-remember").checked});
  for (const id of ["box-client-secret", "box-token"]) $(id).value = "";
  invalidateBoxCheck(); renderBoxStatus(); $("box-remember-label").hidden = true; $("box-finish").textContent = "Save download location";
  $("box-summary").textContent = boxStatus.saved ? "Connection saved for all projects, including after restarting the GUI." : "Connected for all projects during this session. Temporary tokens are not saved.";
  if (boxRecordingColumn) await showBoxFolderPicker(); else boxStepTo(3);
});
$("box-disconnect").onclick = () => boxAction(async () => { boxStatus = await post("/api/box/disconnect", {}); invalidateBoxCheck(); renderBoxStatus(); boxStepTo(1); });
$("box-forget").onclick = () => { if (window.confirm("Remove the saved Box connection from this computer and disconnect this session?")) boxAction(async () => { boxStatus = await post("/api/box/disconnect", {forget: true}); invalidateBoxCheck(); renderBoxStatus(); boxStepTo(1); }); };
updateBoxMethod();
request("/api/box/status").then(async result => {
  boxStatus = result; renderBoxStatus();
  if (result.saved && !result.connected && result.auto_reconnect) {
    $("box-indicator").textContent = "Connecting to saved Box account…";
    try { boxStatus = await post("/api/box/connect", {}); renderBoxStatus(); }
    catch (error) { $("box-indicator").textContent = "Box needs attention"; $("box-status").textContent = error.message; }
  }
}).catch(error => { $("box-indicator").textContent = "Box status unavailable"; $("box-status").textContent = error.message; });
