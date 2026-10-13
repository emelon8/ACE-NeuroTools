"use strict";
let neuronSelection = "", neuronSession = null, neuronDetail = null, neuronIndex = 0, neuronUndo = [], neuronRequest = 0;
let neuronWindowEdited = false, neuronFrameEdited = false;
let neuronExportFolder = null;
let neuronManualSource = false;
function chooseNeuronSource(path) {
  if (neuronSession && neuronSession.source_path !== path) {
    neuronSession = null; neuronDetail = null; neuronUndo = [];
    $("neuron-review").hidden = true; $("neuron-finish").hidden = true;
  }
  neuronManualSource = true; $("neuron-path").value = path;
  $("neuron-source-hint").textContent = "Selected estimates file. Load it to review; the original file is preserved.";
}
const neuronBody = extra => ({project: project.id, number: experiment.number, session: neuronSession?.session, ...extra});
function neuronAction(message, action) {
  return analysisAction(message, async () => {
    await action();
    $("analysis-status").textContent = "Neuron review ready.";
  });
}
function renderNeurons() {
  $("neurons-panel").hidden = workspaceView !== "neurons";
  const selection = `${project.id}/${experiment.number}`;
  if (selection !== neuronSelection) {
    neuronSelection = selection; neuronSession = null; neuronDetail = null; neuronUndo = []; neuronIndex = 0; neuronWindowEdited = false; neuronFrameEdited = false; neuronManualSource = false;
    $("neuron-review").hidden = true; $("neuron-finish").hidden = true; $("neuron-path").value = ""; $("neuron-fr").value = ""; $("neuron-status").textContent = ""; $("neuron-window").value = "30";
    $("neuron-output-path").value = project.path + "/.ace-curations";
    neuronExportFolder = null; $("neuron-open-output").hidden = true;
    $("neuron-output-name").value = "estimates_curated.hdf5";
    $("neuron-detect-events").checked = true;
  }
  if (workspaceView === "neurons" && !neuronSession) refreshNeuronOutputs();
}
async function refreshNeuronOutputs() {
  const selection = neuronSelection, revision = ++neuronRequest;
  try {
    const result = await request(`/api/neuron/sources?project=${encodeURIComponent(project.id)}&number=${encodeURIComponent(experiment.number)}&data_path=${encodeURIComponent(dataBase())}`);
    if (selection !== neuronSelection || revision !== neuronRequest) return;
    const placeholder = element("option", "Choose estimates"); placeholder.value = "";
    $("neuron-run-file").replaceChildren(placeholder, ...result.sources.map(source => { const option = element("option", `${new Date(source.modified / 1e6).toLocaleString()} · ${source.name} · ${source.origin}`); option.value = source.path; return option; }));
    if (!neuronSession && !neuronManualSource) {
      $("neuron-path").value = result.latest || ""; $("neuron-run-file").value = result.latest || "";
      $("neuron-source-hint").textContent = result.latest ? "Most recent estimates selected. Load them, or choose another file." : "No estimates found for this experiment. Run CNMF-E with Save CNMF-E estimates enabled, or choose an existing file.";
    }
  } catch (error) { if (selection === neuronSelection) showError(error); }
}
$("neuron-refresh").onclick = refreshNeuronOutputs;
$("neuron-run-file").onchange = () => { if ($("neuron-run-file").value) chooseNeuronSource($("neuron-run-file").value); };
$("neuron-choose").onclick = () => { if (!busy) browse(project.path, {kind: "neuron-estimates"}); };
$("neuron-output-choose").onclick = () => { if (!busy) browse(project.path, {kind: "neuron-output"}); };
$("neuron-extract").onclick = () => { if (!mustSaveFirst()) return; $("run-kind").value = "miniscope"; $("review-run").click(); };
$("neuron-window").oninput = () => { neuronWindowEdited = true; };
$("neuron-fr").oninput = () => { neuronFrameEdited = true; };
$("neuron-load").onclick = () => neuronAction("Loading CNMF-E estimates…", async () => {
  const previousSource = neuronSession?.source_path;
  neuronSession = await post("/api/neuron/open", neuronBody({path: $("neuron-path").value, fr: neuronFrameEdited ? $("neuron-fr").value : null, window: neuronWindowEdited ? $("neuron-window").value : null}));
  if (previousSource !== neuronSession.source_path) $("neuron-output-name").value = neuronSession.source_path.split(/[\\/]/).pop().replace(/\.(hdf5|h5)$/i, "_curated.hdf5");
  $("neuron-event-derivative").value = neuronSession.event_parameters.derivative;
  $("neuron-event-height").value = neuronSession.event_parameters.event_height;
  neuronWindowEdited = false; neuronFrameEdited = false;
  neuronUndo = []; neuronIndex = neuronSession.current; $("neuron-fr").value = neuronSession.fr; $("neuron-window").value = neuronSession.window; $("neuron-finish").hidden = true;
  await showNeuron(neuronIndex); $("neuron-status").textContent = "Review loaded. Keep, reject, or navigate; decisions save automatically.";
});
function renderNeuronDecisions() {
  const session = neuronSession, status = session.decisions[neuronIndex];
  $("neuron-review").hidden = false; $("neuron-title").textContent = `Neuron ${neuronIndex + 1} / ${session.count} · ${status === null ? "Undecided" : status ? "Kept" : "Rejected"}`;
  $("neuron-source-label").textContent = `${session.source_path} · Original component ID ${neuronIndex}`;
  $("neuron-counts").textContent = `${session.kept} kept · ${session.rejected} rejected · ${session.undecided} undecided · Decisions saved`;
  $("neuron-jump").value = neuronIndex + 1; $("neuron-jump").max = session.count;
  $("neuron-prev").disabled = neuronIndex === 0; $("neuron-next").disabled = neuronIndex === session.count - 1; $("neuron-undo").disabled = !neuronUndo.length;
  $("neuron-map").replaceChildren(...session.decisions.map((value, index) => {
    const button = element("button", String(index + 1), value === null ? "undecided" : value ? "kept" : "rejected");
    button.title = `Neuron ${index+1}: ${value === null ? "undecided" : value ? "kept" : "rejected"}`; button.setAttribute("aria-label", button.title); button.setAttribute("aria-current", index === neuronIndex ? "true" : "false");
    button.onclick = () => navigateNeuron(index); return button;
  }));
  if (!$("neuron-finish").hidden) finishNeurons();
}
async function showNeuron(index, start = null, full = false) {
  if (!neuronSession) return;
  const result = await post("/api/neuron/component", neuronBody({index, revision: neuronSession.revision, fr: $("neuron-fr").value, window: $("neuron-window").value, start, full}));
  neuronWindowEdited = false; neuronFrameEdited = false;
  neuronSession = {...neuronSession, ...result}; neuronDetail = result; neuronIndex = index;
  renderNeuronDecisions(); $("neuron-start").value = result.start.toFixed(3);
  $("neuron-footprint-label").textContent = `Neuron ${index+1} footprint`;
  $("neuron-trace-label").textContent = `Neuron ${index+1} fluorescence trace · raw C values`;
  $("neuron-footprint").src = "data:image/png;base64," + result.footprint;
  const background = new Image(); background.src = "data:image/png;base64," + neuronSession.background; await background.decode();
  const outline = new Image(); outline.src = "data:image/png;base64," + result.outline; await outline.decode();
  const canvas = $("neuron-background"), scale = Math.max(1, Math.min(640 / neuronSession.dims[1], 640 / neuronSession.dims[0]));
  canvas.width = Math.round(neuronSession.dims[1] * scale); canvas.height = Math.round(neuronSession.dims[0] * scale);
  const ctx = canvas.getContext("2d"); ctx.drawImage(background, 0, 0, canvas.width, canvas.height);
  ctx.imageSmoothingEnabled = false; ctx.drawImage(outline, 0, 0, canvas.width, canvas.height);
  const [x,y] = result.peak_pixel.map(value => (value + 0.5) * scale);
  const radius = Math.max(2, canvas.width / 90);
  ctx.strokeStyle = "#ffffff"; ctx.lineWidth = Math.max(2, canvas.width / 200);
  ctx.beginPath(); ctx.arc(x, y, radius, 0, 2*Math.PI); ctx.stroke();
  ctx.strokeStyle = neuronSession.decisions[index] === false ? "#ff4545" : neuronSession.decisions[index] === true ? "#4eff9b" : "#ffffff";
  ctx.lineWidth = Math.max(1, canvas.width / 400); ctx.beginPath(); ctx.arc(x, y, radius, 0, 2*Math.PI); ctx.stroke();
  plotNeuronTrace($("neuron-trace"), result.trace, result.start, result.end, false);
  plotNeuronTrace($("neuron-overview"), result.overview, 0, result.duration, true);
}
function svgNode(tag, attrs, text) { const node = document.createElementNS("http://www.w3.org/2000/svg", tag); for (const [name,value] of Object.entries(attrs)) node.setAttribute(name,value); if (text !== undefined) node.textContent = text; return node; }
function plotNeuronTrace(svg, points, start, end, overview) {
  const width = 900, height = overview ? 100 : 250, left = 65, right = 15, top = 12, bottom = 38;
  const values = points.map(point => point[1]); let lo = Math.min(...values), hi = Math.max(...values); if (lo === hi) { lo -= 1; hi += 1; }
  const span = Math.max(end-start, 1 / neuronSession.fr), x = time => left + (time-start)/span*(width-left-right), y = value => top + (hi-value)/(hi-lo)*(height-top-bottom);
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`); svg.replaceChildren();
  for (let tick = 0; tick <= 4; tick++) {
    const time = start + (end-start)*tick/4;
    svg.append(svgNode("line", {x1:x(time),x2:x(time),y1:top,y2:height-bottom,class:"trace-grid"}), svgNode("text", {x:x(time),y:height-17,"text-anchor":"middle",class:"trace-tick"}, time.toFixed(1)));
  }
  if (!overview) for (const value of [lo,(lo+hi)/2,hi]) svg.append(svgNode("text", {x:left-8,y:y(value)+4,"text-anchor":"end",class:"trace-tick"},value.toPrecision(3)));
  svg.append(svgNode("path", {d:points.map(([time,value],index) => `${index ? "L" : "M"}${x(time).toFixed(2)},${y(value).toFixed(2)}`).join(" "),fill:"none",class:"trace-series","stroke-width":overview ? 1 : 1.5}));
  svg.append(svgNode("text", {x:width/2,y:height-2,"text-anchor":"middle",class:"trace-tick"},"Time (s)"));
  if (overview) svg.append(svgNode("rect",{x:x(neuronDetail.start),y:top,width:Math.max(1,x(neuronDetail.end)-x(neuronDetail.start)),height:height-top-bottom,class:"trace-window","stroke-width":1.5}));
}
function navigateNeuron(index) { if (!busy && neuronSession) neuronAction("Loading neuron…", () => showNeuron(Math.max(0, Math.min(neuronSession.count-1,index)))); }
$("neuron-prev").onclick = () => navigateNeuron(neuronIndex-1); $("neuron-next").onclick = () => navigateNeuron(neuronIndex+1);
$("neuron-go").onclick = () => { const index = Number($("neuron-jump").value)-1; if (Number.isInteger(index)) navigateNeuron(index); };
$("neuron-unreviewed").onclick = () => { const ids = neuronSession?.decisions.map((v,i) => v === null ? i : -1).filter(i=>i>=0) || []; const index = ids.find(i=>i>neuronIndex) ?? ids[0]; if (index !== undefined) navigateNeuron(index); };
async function neuronDecision(value) {
  if (!neuronSession || busy) return;
  const index = neuronIndex, previous = neuronSession.decisions[index];
  await neuronAction("Saving neuron decision…", async () => {
    const result = await post("/api/neuron/decide", neuronBody({revision: neuronSession.revision, index, decision: value, current: value === null ? index : Math.min(index+1,neuronSession.count-1)}));
    neuronUndo.push({index, value: previous}); neuronSession = {...neuronSession, ...result};
    await showNeuron(result.current); $("neuron-status").textContent = "Decision saved.";
  });
}
$("neuron-keep").onclick = () => neuronDecision(true); $("neuron-reject").onclick = () => neuronDecision(false); $("neuron-clear").onclick = () => neuronDecision(null);
$("neuron-undo").onclick = () => { if (!busy && neuronUndo.length) neuronAction("Restoring last decision…", async () => {
  const old = neuronUndo[neuronUndo.length-1]; const result = await post("/api/neuron/decide", neuronBody({revision:neuronSession.revision,index:old.index,decision:old.value,current:old.index}));
  neuronUndo.pop(); neuronSession = {...neuronSession,...result}; await showNeuron(old.index); $("neuron-status").textContent = "Last decision restored and saved.";
}); };
for (const id of ["neuron-apply-window","neuron-peak","neuron-full"]) $(id).onclick = () => { if (!busy && neuronSession) neuronAction("Updating trace view…", () => showNeuron(neuronIndex, id === "neuron-apply-window" ? Number($("neuron-start").value) : null, id === "neuron-full")); };
$("neuron-overview").onclick = event => { if (!busy && neuronDetail) { const bounds = $("neuron-overview").getBoundingClientRect(); const time = Math.max(0, Math.min(neuronDetail.duration, ((event.clientX-bounds.left)/bounds.width*900-65)/820*neuronDetail.duration)); neuronAction("Moving trace window…", () => showNeuron(neuronIndex, time-Number($("neuron-window").value)/2)); } };
function finishNeurons() {
  if (!neuronSession) return;
  $("neuron-finish").hidden = false;
  $("neuron-finish-summary").textContent = `${neuronSession.kept} kept, ${neuronSession.rejected} rejected, ${neuronSession.undecided} undecided.${neuronSession.undecided ? " Choose what to do with the undecided neurons, or continue reviewing." : " These decisions will be exported to a new curation folder."}`;
  $("neuron-undecided-actions").hidden = !neuronSession.undecided; $("neuron-export").disabled = Boolean(neuronSession.undecided);
  const allRejected = !neuronSession.undecided && !neuronSession.kept;
  $("neuron-detect-events").disabled = allRejected;
  const events = $("neuron-detect-events").checked && !allRejected;
  $("neuron-event-settings").hidden = !events;
  $("neuron-export").textContent = events ? "Save curated copies & detect events" : "Save curated copies";
  $("neuron-export-help").textContent = allRejected ? "All neurons are rejected. A new folder will hold the decision record; no curated estimates or events are produced." : `A separate curation folder under ${$("neuron-output-path").value} will hold ${$("neuron-output-name").value}, C_curated.npz, the decision record${events ? ", and calcium-events.json for kept neurons" : ""}.`;
}
$("neuron-done").onclick = finishNeurons; $("neuron-continue").onclick = () => { $("neuron-finish").hidden = true; };
for (const [id,decision] of [["neuron-keep-rest","keep"],["neuron-reject-rest","reject"]]) $(id).onclick = () => neuronAction("Saving remaining decisions…", async () => {
  const result = await post("/api/neuron/decide", neuronBody({revision:neuronSession.revision,bulk:decision})); neuronSession = {...neuronSession,...result}; neuronUndo = []; await showNeuron(neuronIndex);
  finishNeurons();
});
$("neuron-export").onclick = () => neuronAction("Saving curated neuron copies…", async () => {
  const eventAnalysis = $("neuron-detect-events").checked && neuronSession.kept ? {derivative:$("neuron-event-derivative").value,event_height:Number($("neuron-event-height").value)} : null;
  if (eventAnalysis && (!$("neuron-event-height").value.trim() || !Number.isFinite(eventAnalysis.event_height))) throw new Error("Enter a finite event height threshold.");
  let job = await post("/api/neuron/export", neuronBody({revision:neuronSession.revision,confirmed:true,output_path:$("neuron-output-path").value,filename:$("neuron-output-name").value,event_analysis:eventAnalysis}));
  while (job.state === "saving") { $("neuron-status").textContent = job.message; await new Promise(resolve=>setTimeout(resolve,500)); job = await request(`/api/neuron/export?project=${encodeURIComponent(project.id)}&job=${encodeURIComponent(job.id)}`); }
  if (job.state === "failed") throw new Error(job.message);
  neuronExportFolder = job.directory; $("neuron-open-output").hidden = false;
  $("neuron-status").textContent = `${job.message}\n${job.directory}\n${job.files.join(", ")}`; 
});
$("neuron-open-output").onclick = () => openSystemFolder(neuronExportFolder);
$("neuron-output-name").oninput = () => { if (neuronSession && !$("neuron-finish").hidden) finishNeurons(); };
$("neuron-detect-events").onchange = finishNeurons;
document.addEventListener("keydown", event => {
  if (workspaceView !== "neurons" || busy || !neuronSession || event.ctrlKey || event.metaKey || event.altKey || event.target.closest("input,select,textarea,a")) return;
  // Enter on a focused button retains its ordinary activation behavior.
  if (event.key === "Enter" && event.target.closest("button")) return;
  const key = event.key.toLowerCase(), actions = {k:()=>neuronDecision(true),r:()=>neuronDecision(false),arrowleft:()=>navigateNeuron(neuronIndex-1),arrowright:()=>navigateNeuron(neuronIndex+1),d:finishNeurons,enter:finishNeurons};
  if (actions[key]) { event.preventDefault(); actions[key](); }
});
