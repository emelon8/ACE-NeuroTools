"use strict";
let generatedJob = null, jobSelection = "";
function clearJobScripts() {
  generatedJob = null; $("job-preview").hidden = true;
}
function renderJobScripts() {
  const selection = `${project.id}/${experiment.number}`;
  if (selection !== jobSelection) { $("job-recording").value = ""; $("job-ephys-recording").value = ""; jobSelection = selection; }
  const multimodal = $("run-kind").value === "multimodal";
  $("job-ephys-field").hidden = !multimodal;
  $("job-ephys-recording").required = multimodal;
  $("job-panel").hidden = workspaceView !== "job";
  clearJobScripts();
}
$("output-script").onclick = () => {
  if (!mustSaveFirst()) return;
  $("job-context").textContent = `${$("detail-title").textContent} · ${$("run-kind").selectedOptions[0].textContent}`;
  workspaceView = "job"; renderWorkspace(); $("job-recording").focus();
};
$("job-back").onclick = () => setWorkspace("overview");
$("job-form").oninput = clearJobScripts;
$("job-form").onsubmit = async event => {
  event.preventDefault();
  if (!mustSaveFirst()) return;
  clearJobScripts();
  await analysisAction("Generating job scripts from saved settings…", async () => {
    const cluster = Object.fromEntries(new FormData($("job-form")));
    generatedJob = await post("/api/job/scripts", analysisPayload({kind: $("run-kind").value, data_path: dataBase(), cluster}));
    $("job-python-preview").textContent = generatedJob.script;
    $("job-slurm-preview").textContent = generatedJob.slurm;
    $("job-parameters-preview").textContent = JSON.stringify(generatedJob.config, null, 2);
    $("job-preview").hidden = false;
    $("analysis-status").textContent = "Scripts are ready to review and download. Submit them from the extracted folder on the cluster.";
  });
};
$("job-download").onclick = () => {
  if (!generatedJob || !mustSaveFirst()) return;
  const bytes = Uint8Array.from(atob(generatedJob.archive), char => char.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], {type: "application/zip"}));
  const link = element("a"); link.href = url; link.download = generatedJob.filename;
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
