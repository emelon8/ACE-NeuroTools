"use strict";
const dataBases = new Map();
let preparedBase = null, preparedSubset = false;
let downloadPlan = null, downloadSelection = new Set(), downloadChoice = null, activeDownload = null;
class RecordingCancelled extends Error {}
let analysisSelection = "", runReview = null, runSettings = null, runSettingDraft = {}, cropPreview = null, cropCoords = null, cropSaved = null, cropDirty = false;
let cropImage = null, cropPixels = null, cropDrag = null, selectedRun = null, runPoll = null, runListRequest = 0;
const runNames = {crop: "Apply crop", crop_coords: "Crop coordinates (x0, y0, x1, y1)", filenames: "Movie filenames ([] = all)", run_CNMFE: "Extract neurons with CNMF-E", parallel: "Use parallel processing", n_processes: "Worker processes", apply_motion_correction: "Apply motion correction", save_estimates: "Save CNMF-E estimates", save_CNMFE_estimates_filename: "Estimates filename", save_CNMFE_params: "Save CaImAn parameters", detrend_method: "Detrending method", df_over_f: "Normalize fluorescence", secs_window: "Baseline window (s)", quantile_min: "Baseline percentile", channel_name: "Channel name", filter_type: "Filter type", filter_range: "Filter frequencies (Hz)", remove_artifacts: "Remove artifacts", compute_phases: "Compute phases"};
const windowFlags = new Set(["inspect_motion_correction", "remove_components_with_gui", "plot_params", "inline", "plot_channel", "plot_spectrogram", "plot_phases"]);
const paramLabel = key => runNames[key] || key.replaceAll("_", " ").replace(/^./, letter => letter.toUpperCase());
const displayParam = value => value === null ? "None" : typeof value === "object" ? JSON.stringify(value) : String(value);
const extraUnsaved = () => cropDirty || Object.keys(runSettingDraft).length > 0;
const dataBase = () => dataBases.get(project.id) || preparedBase || boxStatus.download_path || project.path;
function analysisPayload(extra = {}) { return {project: project.id, number: experiment.number, versions: experiment.versions, ...(dataBases.has(project.id) || preparedBase ? {data_path: dataBases.get(project.id) || preparedBase} : {}), ...extra}; }
function mustSaveFirst() {
  if (anyDirty()) { showError(new Error("Save or discard your pending changes before loading a preview or reviewing a run.")); return false; }
  return !busy;
}
function renderDownloadFiles() {
  const term = $("download-search").value.trim().toLowerCase();
  $("download-files").replaceChildren(...downloadPlan.files.filter(item => item.path.toLowerCase().includes(term)).map(item => {
    const row = element("tr"), cell = element("td"), check = element("input");
    check.type = "checkbox"; check.checked = downloadSelection.has(item.path); check.setAttribute("aria-label", `Select ${item.path}`);
    check.onchange = () => { if (check.checked) downloadSelection.add(item.path); else downloadSelection.delete(item.path); updateDownloadSelection(); };
    cell.append(check); row.append(cell, element("td", item.path), element("td", formatSize(item.size)), element("td", item.local ? "Available" : "Not downloaded"));
    return row;
  }));
  updateDownloadSelection();
}
function updateDownloadSelection() {
  const selected = downloadPlan.files.filter(item => downloadSelection.has(item.path));
  const missing = selected.filter(item => !item.local), bytes = missing.reduce((sum, item) => sum + item.size, 0);
  const enough = bytes === 0 || bytes + 1024 * 1024 <= downloadPlan.free_bytes;
  $("download-selection").textContent = `${selected.length} of ${downloadPlan.files.length} files selected · ${formatSize(selected.reduce((sum, item) => sum + item.size, 0))} total · ${formatSize(bytes)} to download${selected.length && !enough ? " · Not enough free disk space. Select fewer files or choose another local folder." : ""}`;
  $("download-confirm").disabled = !selected.length || !enough;
  $("download-confirm").textContent = !selected.length ? "Confirm & download selected files" : bytes ? `Confirm & download ${missing.length} ${missing.length === 1 ? "file" : "files"} (${formatSize(bytes)})` : "Confirm selected local files";
}
function confirmRecordingDownload(plan) {
  downloadPlan = plan; downloadSelection = new Set(plan.previous_selection.filter(path => plan.files.some(item => item.path === path)));
  $("download-context").textContent = `${project.name} · ${$("detail-title").textContent} · ${$("run-kind").selectedOptions[0].textContent}`;
  const details = [["Box folder", plan.folder_id], ["Full recording", `${plan.files.length} files · ${formatSize(plan.total_bytes)}`], ["Destination", plan.recording_path], ["Free disk space", formatSize(plan.free_bytes)]];
  $("download-details").replaceChildren(...details.flatMap(([label, value]) => [element("dt", label), element("dd", value)]));
  $("download-search").value = ""; $("download-review").hidden = false;
  renderDownloadFiles(); $("download-review").scrollIntoView({block: "start"}); $("download-one").focus();
  return new Promise(resolve => { downloadChoice = resolve; });
}
$("download-one").onclick = () => {
  const candidates = downloadPlan.files.filter(item => item.path.toLowerCase().endsWith(".avi"));
  const calcium = candidates.filter(item => item.path.split("/").some(part => /miniscope|calcium/i.test(part)));
  const movie = (calcium.length ? calcium : candidates).sort((a,b) => a.size - b.size || a.path.localeCompare(b.path, undefined, {numeric:true}))[0];
  if (!movie) { $("download-selection").textContent = "No AVI movie is present. Select individual recording files below."; return; }
  const parent = movie.path.split("/").slice(0,-1).join("/");
  downloadSelection = new Set([movie.path, ...downloadPlan.files.filter(item => {
    const folder = item.path.split("/").slice(0,-1).join("/");
    return (!folder || parent === folder || parent.startsWith(folder + "/")) && /^(metadata.*\.json|timestamps.*\.csv)$/i.test(item.path.split("/").pop());
  }).map(item => item.path)]);
  renderDownloadFiles();
};
$("download-all").onclick = () => { downloadSelection = new Set(downloadPlan.files.map(item => item.path)); renderDownloadFiles(); };
$("download-none").onclick = () => { downloadSelection.clear(); renderDownloadFiles(); };
$("download-search").oninput = renderDownloadFiles;
$("download-confirm").onclick = () => { if (downloadChoice && !$("download-confirm").disabled) { const resolve = downloadChoice; downloadChoice = null; $("download-review").hidden = true; resolve([...downloadSelection]); } };
$("download-dismiss").onclick = () => { if (downloadChoice) { const resolve = downloadChoice; downloadChoice = null; $("download-review").hidden = true; resolve(null); } };
$("download-cancel").onclick = async () => {
  if (!activeDownload) return;
  $("download-cancel").disabled = true; $("download-progress-text").textContent = "Cancelling download and removing temporary files…";
  try { await post("/api/recording/cancel", analysisPayload({job: activeDownload.id})); }
  catch (error) { showError(error); $("download-cancel").disabled = false; }
};
async function prepareRecording(kind, choose = false) {
  let result = await post(choose ? "/api/recording/plan" : "/api/recording/prepare", analysisPayload({kind, data_path: dataBases.get(project.id)}));
  if (result.state === "selection_required") {
    $("analysis-status").textContent = "Review the file selection before downloading.";
    const selected = await confirmRecordingDownload(result);
    if (!selected) throw new RecordingCancelled("Download cancelled. No files were downloaded.");
    result = await post("/api/recording/start", analysisPayload({plan: result.plan, files: selected, confirmed: true}));
  }
  while (["queued", "downloading", "cancelling", "finalizing"].includes(result.state)) {
    activeDownload = result; $("download-progress").hidden = false;
    $("download-cancel").disabled = ["cancelling", "finalizing"].includes(result.state);
    $("download-progress-text").textContent = `${result.message} ${result.total_files ? `${result.files_done}/${result.total_files} files · ${formatSize(result.bytes)} / ${formatSize(result.total_bytes)}` : ""}\nLocal folder: ${result.recording_path}`;
    $("download-meter").max = result.total_bytes || 1; $("download-meter").value = Math.min(result.bytes, result.total_bytes || 1);
    await new Promise(resolve => setTimeout(resolve, 500));
    result = await request(`/api/recording?project=${encodeURIComponent(project.id)}&job=${encodeURIComponent(result.id)}`);
  }
  activeDownload = null; $("download-progress").hidden = true;
  if (result.state === "cancelled") throw new RecordingCancelled(result.message);
  if (result.state === "failed") throw new Error(result.error);
  preparedBase = result.data_path; preparedSubset = Boolean(result.subset);
  $("data-base-label").textContent = `Data base: ${result.data_path}${preparedSubset ? " · Selected files only" : ""}`;
  boxStatus = await request("/api/box/status"); renderBoxStatus();
  return result;
}
$("choose-recording-files").onclick = () => { if (mustSaveFirst()) analysisAction("Reading the Box file list…", async () => { await prepareRecording($("run-kind").value, true); runReview = null; cropPreview = null; $("crop-workspace").hidden = true; $("analysis-status").textContent = preparedSubset ? "Selected files are ready. Crop and analysis use only this selection; the remaining Box files will not download automatically." : "Recording files are ready."; }); };
function renderAnalysis() {
  const selection = `${project.id}/${experiment.number}`;
  if (analysisSelection !== selection) {
    $("crop-workspace").hidden = true; $("crop-status").textContent = "Load the calcium recording to draw a crop. Missing files require a file selection and download confirmation.";
    preparedBase = null; preparedSubset = false; analysisSelection = selection; runReview = null; runSettingDraft = {}; cropPreview = null; cropDirty = false; selectedRun = null;
    clearTimeout(runPoll); runPoll = null;
    const row = project.experiments.find(item => item.number === experiment.number);
    $("run-kind").value = row.miniscope ? "compute" : row.ephys ? "ephys" : "compute";
    $("analysis-status").textContent = "";
  }
  for (const [id, view] of [["run-settings-panel", "run-settings"], ["review-panel", "review"], ["crop-panel", "crop"], ["results-panel", "results"]]) $(id).hidden = workspaceView !== view;
  $("data-base-label").textContent = `Data base: ${dataBase()}${preparedSubset ? " · Selected files only" : ""}`;
  $("overview-output-path").textContent = project.path + "/.ace-runs/";
  if (workspaceView === "results") refreshRuns();
}
async function analysisAction(message, action) {
  if (busy) return;
  busy = true; clearError(); $("analysis-status").textContent = message; $("detail-content").inert = true;
  $("review-run").disabled = true;
  try { await action(); }
  catch (error) { if (error instanceof RecordingCancelled) $("analysis-status").textContent = error.message; else { showError(error); $("analysis-status").textContent = "Action failed. Your saved settings and previous results were retained."; } }
  finally { activeDownload = null; $("download-progress").hidden = true; $("download-review").hidden = true; busy = false; $("detail-content").inert = false; $("review-run").disabled = false; if (experiment) updateSaveBar(); }
}
function acceptSaved(result) {
  replaceProject(result.project); project = result.project; experiment = result.experiment;
  lastBackup = result.backup || ""; runReview = null; renderProjects(); renderEditor(); renderWorkspace();
}
async function openRunSettings() {
  if (!mustSaveFirst()) return;
  await analysisAction("Loading run settings…", async () => {
    const result = await request(`/api/run/settings?project=${encodeURIComponent(project.id)}&number=${encodeURIComponent(experiment.number)}&kind=${$("run-kind").value}`);
    runSettings = {...result, kind: $("run-kind").value}; runSettingDraft = {};
    $("run-settings-fields").replaceChildren(...Object.entries(result.parameters).filter(([key]) => key !== "crop_coords").map(([key, value], index) => {
      const field = element("div", undefined, "field"), label = element("label", paramLabel(key)); label.htmlFor = `run-field-${index}`;
      const control = element(typeof value === "boolean" ? "select" : "input"); control.id = label.htmlFor; control.dataset.key = key;
      if (typeof value === "boolean") {
        for (const [raw, text] of [["True", "Yes"], ["False", "No"]]) { const option = element("option", text); option.value = raw; control.append(option); }
        control.value = value ? "True" : "False";
      } else { control.value = displayParam(value); control.type = "text"; }
      const initial = control.value;
      control.disabled = windowFlags.has(key);
      control.oninput = () => { if (control.value === initial) delete runSettingDraft[key]; else runSettingDraft[key] = control.value; $("save-run-settings").disabled = Object.keys(runSettingDraft).length === 0; };
      field.append(label, control, element("small", windowFlags.has(key) ? "Disabled: separate-window actions use the embedded Crop/Neurons workflows." : key === "save_CNMFE_estimates_filename" ? "Filename only. The review shows its full output location." : result.sources[key]));
      if (key === "filenames") { const choose = element("button", "Choose movies"); choose.type = "button"; choose.onclick = () => chooseRunMovies(control); field.append(choose); }
      return field;
    }));
    $("save-run-settings").disabled = true; $("run-settings-help").hidden = runSettings.kind !== "miniscope"; workspaceView = "run-settings"; renderWorkspace(); $("analysis-status").textContent = "";
  });
}
$("run-settings-button").onclick = openRunSettings;
$("overview-cnmfe").onclick = () => { if (mustSaveFirst()) { $("run-kind").value = "miniscope"; openRunSettings(); } };
$("review-settings-run").onclick = () => $("review-run").click();
async function chooseRunMovies(control) {
  let fallback = null;
  await analysisAction("Choose recording movies in the system file picker…", async () => {
    const recording = await prepareRecording(runSettings.kind);
    const apply = paths => {
      if (paths.some(path => !path.startsWith(recording.recording_path + "/") || !/\.avi$/i.test(path))) throw new Error("Choose AVI files within this experiment's recording folder. Change the recording folder in Data & settings to use other data.");
      control.value = JSON.stringify(paths.map(path => path.split("/").pop())); control.dispatchEvent(new Event("input", {bubbles:true}));
    };
    const result = await post("/api/system/pick", {kind:"movies", initial:recording.recording_path});
    if (!result.available) fallback = () => browseFolders(recording.recording_path, {kind:"movie-files", onpick:path => apply([path])});
    else if (result.paths.length) apply(result.paths);
    $("analysis-status").textContent = "Save any filename changes before reviewing the run.";
  });
  if (fallback) await fallback();
}
$("run-kind").onchange = () => { if (Object.keys(runSettingDraft).length) { showError(new Error("Save or discard the run settings before changing analysis.")); $("run-kind").value = runSettings.kind; return; } runReview = null; if (workspaceView === "review" || workspaceView === "run-settings") setWorkspace("overview"); };
$("run-settings-form").onsubmit = event => {
  event.preventDefault();
  analysisAction("Saving run settings…", async () => {
    const result = await post("/api/run/settings/save", analysisPayload({kind: $("run-kind").value, changes: runSettingDraft, create: experiment.parameters === null}));
    runSettingDraft = {}; acceptSaved(result); $("save-run-settings").disabled = true; $("analysis-status").textContent = "Run settings saved to analysis_parameters.csv.";
  });
};
$("cancel-run-settings").onclick = () => { if (Object.keys(runSettingDraft).length && !window.confirm("Discard these unsaved run settings?")) return; runSettingDraft = {}; setWorkspace("overview"); };
$("choose-data-base").onclick = () => { if (mustSaveFirst()) browse(dataBase(), {kind: "data-base"}); };
$("review-run").onclick = () => {
  if (!mustSaveFirst()) return;
  analysisAction("Preparing experiment review…", async () => {
    await prepareRecording($("run-kind").value);
    runReview = await post("/api/run/review", analysisPayload({kind: $("run-kind").value}));
    $("review-file-list").replaceChildren(...runReview.files.map(item => element("li", `${item.path} · ${formatSize(item.size)}`)));
    const facts = [["Recording scope", preparedSubset ? "Selected files only (test subset)" : "Local recording files"], ["Project", project.name], ["Subject", runReview.metadata.id || "Not set"], ["Experiment", experiment.number], ["Recorded", friendlyDate(runReview.metadata["date (YYMMDD)"])], ["Analysis", runReview.label], ["Recording folder", runReview.recording_path || runReview.metadata[runReview.recording_column]], ["Input copy", `${runReview.files.length} files · ${formatSize(runReview.input_bytes)}`]];
    $("review-details").replaceChildren(...facts.flatMap(([label, value]) => [element("dt", label), element("dd", value)]));
    $("review-outputs").replaceChildren(...Object.entries(runReview.destinations).flatMap(([label,value]) => [element("dt",label),element("dd",value)]));
    const noExtraction = runReview.kind === "miniscope" && !runReview.parameters.run_CNMFE, noEstimates = runReview.kind === "miniscope" && !runReview.parameters.save_estimates;
    $("review-cnmfe-warning").hidden = !noExtraction && !noEstimates;
    $("review-cnmfe-warning").textContent = noExtraction ? "CNMF-E extraction is turned off. This run will not extract neurons. Enable Extract neurons with CNMF-E in Run settings to extract them." : noEstimates ? "Save CNMF-E estimates is turned off. This run will not save an estimates file for neuron review. Enable it in Run settings to save one." : "";
    $("review-blockers").hidden = !runReview.blockers.length;
    $("review-blockers").replaceChildren(element("strong", "Resolve these before starting:"), ...runReview.blockers.map(message => element("p", message)));
    $("review-parameters").replaceChildren(...Object.entries(runReview.parameters).map(([key, value]) => { const row = element("tr"); row.append(element("td", paramLabel(key)), element("td", displayParam(value)), element("td", runReview.parameter_sources[key])); return row; }));
    $("review-csv").textContent = JSON.stringify({metadata: runReview.metadata, settings: runReview.settings}, null, 2);
    $("run-confirm").checked = false; $("start-run").disabled = true; workspaceView = "review"; renderWorkspace(); $("analysis-status").textContent = "Review the experiment before starting.";
  });
};
$("run-confirm").onchange = () => { $("start-run").disabled = !$("run-confirm").checked || !runReview || runReview.blockers.length > 0; };
$("cancel-review").onclick = () => setWorkspace("overview");
$("start-run").onclick = () => analysisAction("Starting analysis…", async () => {
  const result = await post("/api/run/start", analysisPayload({review: runReview.review, confirmed: $("run-confirm").checked}));
  selectedRun = result.id; runReview = null; workspaceView = "results"; renderWorkspace(); showRun(result);
  $("analysis-status").textContent = "Analysis running. You can browse experiments while it works.";
});
function formatSize(bytes) { return bytes < 1024 ? `${bytes} B` : bytes < 1024 ** 2 ? `${(bytes / 1024).toFixed(1)} KB` : bytes < 1024 ** 3 ? `${(bytes / 1024 ** 2).toFixed(1)} MB` : `${(bytes / 1024 ** 3).toFixed(1)} GB`; }
async function refreshRuns() {
  const revision = ++runListRequest, selection = analysisSelection;
  try {
    const result = await request(`/api/runs?project=${encodeURIComponent(project.id)}&number=${encodeURIComponent(experiment.number)}`);
    if (selection !== analysisSelection || revision !== runListRequest) return;
    const table = element("table"), head = element("thead"), headerRow = element("tr");
    for (const name of ["Started", "Analysis", "State"]) headerRow.append(element("th", name)); head.append(headerRow); table.append(head);
    const body = element("tbody");
    for (const run of result.runs) {
      const row = element("tr", undefined, "experiment-row"); row.append(element("td", new Date(run.started).toLocaleString()), element("td", run.label), element("td", run.state));
      actionableRow(row, () => { selectedRun = run.id; showRun(run); }); body.append(row);
    }
    table.append(body); $("run-list").replaceChildren(result.runs.length ? table : element("p", "No GUI runs have been saved for this experiment. Choose Review & run to start one."));
    if (selectedRun) { const run = result.runs.find(item => item.id === selectedRun); if (run) showRun(run); }
    else if (result.runs.length) { selectedRun = result.runs[0].id; showRun(result.runs[0]); }
    else $("run-output").hidden = true;
  } catch (error) { if (selection === analysisSelection) showError(error); }
}
function showRun(run) {
  $("run-output").hidden = false; $("run-output-title").textContent = run.label;
  $("run-output-state").textContent = `${run.state}${run.error ? ` · ${run.error}` : ""}${run.state === "untracked" ? " · The GUI server restarted. Use Refresh runs to check completion; the log and outputs are retained." : ""}`;
  $("run-output-location").textContent = run.directory; $("run-output-location").dataset.path = run.directory; $("stop-run").hidden = run.state !== "running";
  const estimates = run.files.find(file => /\.(hdf5|h5)$/i.test(file.name));
  $("review-run-neurons").hidden = run.kind !== "miniscope" || run.state !== "completed" || !estimates;
  $("review-run-neurons").onclick = () => { setWorkspace("neurons"); chooseNeuronSource(run.directory + "/" + estimates.name); $("neuron-load").click(); };
  $("run-log").textContent = run.log; $("run-used-parameters").textContent = JSON.stringify(run.parameters, null, 2);
  const inventory = run.output_inventory;
  if (inventory) {
    const table = element("table"), head = element("tr");
    for (const label of ["Result", "Status", "Location / reason"]) head.append(element("th", label));
    table.append(head);
    for (const output of inventory.outputs) {
      const row = element("tr");
      const location = output.status === "exported" ? output.file + (output.key ? ` · ${output.key}` : "") : output.reason;
      row.append(element("td", output.name), element("td", output.status === "exported" ? "Exported" : "Not computed / unavailable"), element("td", location));
      table.append(row);
    }
    $("run-output-inventory").replaceChildren(table);
  } else $("run-output-inventory").replaceChildren(element("p", run.state === "running" ? "The output inventory will be saved when analysis finishes." : "No output inventory was saved for this run."));
  $("run-output-files").replaceChildren(...run.files.map(file => {
    const line = element("div", undefined, "output-link"), link = element("a", file.name);
    link.href = `/api/run/file?project=${encodeURIComponent(project.id)}&run=${encodeURIComponent(run.id)}&name=${encodeURIComponent(file.name)}`; link.download = file.name.split("/").pop();
    line.append(link, element("span", formatSize(file.size))); return line;
  }));
  clearTimeout(runPoll);
  if (run.state === "running" && workspaceView === "results") runPoll = setTimeout(refreshRuns, 2000);
}
$("refresh-runs").onclick = refreshRuns;
$("open-run-folder").onclick = () => openSystemFolder($("run-output-location").dataset.path);
$("stop-run").onclick = () => { if (window.confirm("Stop this analysis? Partial outputs will remain in its run folder.")) analysisAction("Stopping analysis…", async () => { const run = await post("/api/run/stop", analysisPayload({run: selectedRun})); showRun(run); $("analysis-status").textContent = "Run stopped. Its inputs, log, and partial outputs were retained."; refreshRuns(); }); };

$("load-crop").onclick = () => {
  if (busy || Object.keys(drafts.metadata).length || dirty("parameters") || Object.keys(runSettingDraft).length) { showError(new Error("Save or discard your settings before loading a crop preview.")); return; }
  if (cropDirty && !window.confirm("Replace the unsaved crop with a fresh preview?")) return;
  analysisAction("Loading sampled recording images…", async () => {
    await prepareRecording("crop");
    $("analysis-status").textContent = "Loading sampled recording images…";
    const result = await post("/api/crop/preview", analysisPayload());
    cropPreview = result; cropSaved = result.coords || [0, 0, result.width, result.height]; cropCoords = [...cropSaved]; cropDirty = false;
    $("crop-status").textContent = `${preparedSubset ? "Selected files only · " : ""}${result.width} × ${result.height} pixels · ${result.sample_frames} preview frames from ${result.sample_files} of ${result.total_files} movies. The saved crop applies to all frames during analysis.${result.legacy ? " Loaded the legacy crop; saving writes canonical crop_coords." : ""}${result.warning ? " " + result.warning : ""}`;
    $("crop-workspace").hidden = false;
    for (const name of ["x0", "x1"]) $("crop-" + name).max = result.width;
    for (const name of ["y0", "y1"]) $("crop-" + name).max = result.height;
    await changeCropImage(); updateCropControls(); $("analysis-status").textContent = "Draw or adjust the crop, then save it to this experiment's settings.";
  });
};
async function changeCropImage() {
  if (!cropPreview) return;
  const image = new Image(); image.src = "data:image/png;base64," + cropPreview.images[$("crop-projection").value];
  await image.decode(); cropImage = image;
  const temp = document.createElement("canvas"); temp.width = image.width; temp.height = image.height;
  const context = temp.getContext("2d"); context.drawImage(image, 0, 0); cropPixels = context.getImageData(0, 0, image.width, image.height);
  drawCrop();
}
function updateCropControls() {
  if (!cropCoords) return;
  ["x0", "y0", "x1", "y1"].forEach((key, index) => { $("crop-" + key).value = cropCoords[index]; }); drawCrop();
}
function cropValid() { return cropCoords && cropPreview && cropCoords.every(Number.isInteger) && cropCoords[0] >= 0 && cropCoords[1] >= 0 && cropCoords[2] <= cropPreview.width && cropCoords[3] <= cropPreview.height && cropCoords[2] > cropCoords[0] && cropCoords[3] > cropCoords[1]; }
function drawCrop() {
  if (!cropImage || !cropCoords || !cropPreview) return;
  const canvas = $("crop-canvas"), w = cropPreview.width, h = cropPreview.height;
  canvas.width = w; canvas.height = h;
  const zoom = $("crop-zoom").value;
  const displayWidth = zoom === "fit" ? Math.min($("crop-image").parentElement.clientWidth - 4, 900, 560 * w / h) : w * (zoom === "double" ? 2 : 1);
  $("crop-image").style.width = `${displayWidth}px`;
  const context = canvas.getContext("2d"), pixels = new ImageData(new Uint8ClampedArray(cropPixels.data), w, h);
  const dark = Number($("crop-dark").value), light = Math.max(dark + 1, Number($("crop-light").value));
  for (let i = 0; i < pixels.data.length; i += 4) { const value = Math.max(0, Math.min(255, (pixels.data[i] - dark) * 255 / (light - dark))); pixels.data[i] = pixels.data[i + 1] = pixels.data[i + 2] = value; }
  context.putImageData(pixels, 0, 0);
  $("crop-overlay").replaceChildren();
  if (cropValid()) {
    const [x0, y0, x1, y1] = cropCoords, top = h - y1, bottom = h - y0;
    context.fillStyle = "rgba(0,0,0,0.4)"; context.fillRect(0, 0, w, top); context.fillRect(0, bottom, w, h - bottom); context.fillRect(0, top, x0, bottom - top); context.fillRect(x1, top, w - x1, bottom - top);
    const overlay = $("crop-overlay"); overlay.setAttribute("viewBox", `0 0 ${w} ${h}`);
    const svgRect = (x, y, width, height, fill, stroke) => {
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      for (const [key, value] of Object.entries({x, y, width, height, fill, stroke: stroke || "none", "stroke-width": 2, "vector-effect": "non-scaling-stroke"})) rect.setAttribute(key, value);
      return rect;
    };
    const size = w / displayWidth * 7;
    overlay.replaceChildren(svgRect(x0, top, x1-x0, bottom-top, "none", "#fff34f"), ...[[x0,top],[x1,top],[x0,bottom],[x1,bottom]].map(([x,y]) => svgRect(x-size/2,y-size/2,size,size,"#fff34f", "#253027")));

  }
  $("crop-size").textContent = cropValid() ? `Selected: ${cropCoords[2]-cropCoords[0]} × ${cropCoords[3]-cropCoords[1]} pixels${cropDirty ? " · Unsaved crop" : ""}` : "The crop must fit inside the image and have a positive width and height.";
  $("crop-save").disabled = !cropValid();
}
function cropPoint(event) {
  const rect = $("crop-canvas").getBoundingClientRect();
  return [Math.round(Math.max(0, Math.min(cropPreview.width, (event.clientX - rect.left) * cropPreview.width / rect.width))), Math.round(Math.max(0, Math.min(cropPreview.height, cropPreview.height - (event.clientY - rect.top) * cropPreview.height / rect.height)))];
}
$("crop-canvas").onpointerdown = event => {
  if (!cropPreview || event.button !== 0) return;
  const point = cropPoint(event), tolerance = cropPreview.width / $("crop-canvas").getBoundingClientRect().width * 10;
  const corners = [[cropCoords[0],cropCoords[1]], [cropCoords[0],cropCoords[3]], [cropCoords[2],cropCoords[1]], [cropCoords[2],cropCoords[3]]];
  const corner = corners.findIndex(([x,y]) => Math.hypot(x-point[0], y-point[1]) < tolerance);
  cropDrag = {start: point, original: [...cropCoords], corner, mode: corner >= 0 ? "resize" : cropValid() && point[0] > cropCoords[0] && point[0] < cropCoords[2] && point[1] > cropCoords[1] && point[1] < cropCoords[3] ? "move" : "draw"};
  $("crop-canvas").setPointerCapture(event.pointerId); event.preventDefault();
};
$("crop-canvas").onpointermove = event => {
  if (!cropDrag) return;
  const point = cropPoint(event), original = cropDrag.original;
  if (cropDrag.mode === "move") {
    const dx = Math.max(-original[0], Math.min(cropPreview.width-original[2], point[0]-cropDrag.start[0])), dy = Math.max(-original[1], Math.min(cropPreview.height-original[3], point[1]-cropDrag.start[1]));
    cropCoords = [original[0]+dx, original[1]+dy, original[2]+dx, original[3]+dy];
  } else {
    const fixed = cropDrag.mode === "draw" ? cropDrag.start : [[original[2],original[3]], [original[2],original[1]], [original[0],original[3]], [original[0],original[1]]][cropDrag.corner];
    cropCoords = [Math.min(fixed[0],point[0]), Math.min(fixed[1],point[1]), Math.max(fixed[0],point[0]), Math.max(fixed[1],point[1])];
  }
  cropDirty = true; updateCropControls();
};
$("crop-canvas").onpointerup = $("crop-canvas").onpointercancel = () => { cropDrag = null; };
for (const key of ["x0", "y0", "x1", "y1"]) $("crop-" + key).oninput = () => { cropCoords = ["x0","y0","x1","y1"].map(name => $("crop-" + name).value === "" ? NaN : Number($("crop-" + name).value)); cropDirty = true; drawCrop(); };
$("crop-full").onclick = () => { cropCoords = [0,0,cropPreview.width,cropPreview.height]; cropDirty = true; updateCropControls(); };
$("crop-reset").onclick = () => { cropCoords = [...cropSaved]; cropDirty = false; updateCropControls(); };
$("crop-projection").onchange = () => changeCropImage().catch(showError);
for (const id of ["crop-zoom", "crop-dark", "crop-light"]) $(id).oninput = drawCrop;
$("crop-save").onclick = () => analysisAction("Saving crop coordinates…", async () => {
  if (dirty("metadata") || dirty("parameters") || Object.keys(runSettingDraft).length) throw new Error("Save or discard pending settings before saving this crop.");
  const result = await post("/api/crop/save", analysisPayload({preview: cropPreview.preview, coords: cropCoords}));
  cropDirty = false; cropSaved = [...cropCoords]; acceptSaved(result);
  // Renewed file versions require a new preview for any further crop write.
  cropPreview = null; $("crop-workspace").hidden = true;
  $("crop-status").textContent = `Saved crop ${cropSaved.join(", ")} to analysis_parameters.csv. Load the preview again to adjust it.`;
  $("analysis-status").textContent = "Crop saved. Review the experiment before running.";
});

window.addEventListener("resize", drawCrop);

function resetAnalysisDrafts() {
  analysisSelection = ""; runReview = null; runSettingDraft = {}; cropPreview = null; cropDirty = false; selectedRun = null;
  clearTimeout(runPoll); runPoll = null;
}

$("crop-export").onclick = () => {
  if (!mustSaveFirst()) return;
  $("run-kind").value = "preprocess"; $("review-run").click();
};
