"""Run the browser's actual editor functions with deferred save responses."""

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "src/aceneurotools/gui/loaders.js"


@pytest.mark.parametrize("scenario", ["unchanged", "edit", "edit-newline", "editor", "project", "closed", "stale-error", "active-error", "bom"])
def test_save_snapshot_and_stale_responses(scenario):
    source = SCRIPT.read_text()
    save = source[source.index("  function save() {"):source.index("  function discard()")]
    normalize = source[source.index("  const normalizeText"):source.index("  const lines")]
    harness = r'''
const assert = require("node:assert/strict");
const scenario = process.argv[1];
const original = {name: "rig", digest: "old", saved: "old\n", text: scenario === "bom" ? "\uFEFFsent" : "sent"};
const state = {projectId: "p", open: original};
const nodes = {};
const $ = id => nodes[id] ||= {value: "", textContent: ""};
let resolve, reject, task, payload, reopened = 0, listed = 0;
const post = (url, body) => { payload = body; return new Promise((yes, no) => {resolve = yes; reject = no;}); };
const working = action => { task = action(); };
const parsed = () => ({name: "rig"});
const openEditor = open => { assert.equal(open, original); state.open = open; reopened++; $("loaders-json").value = open.text; };
const loadList = async () => { listed++; };
'''
    harness += normalize + save + r'''
(async () => {
  save();
  assert.deepEqual(payload, {project: "p", name: "rig", text: original.text, digest: "old"});
  const stale = ["editor", "project", "closed", "stale-error"].includes(scenario);
  if (scenario === "edit") original.text = "later unsaved edit";
  if (scenario === "edit-newline") original.text = "sent\n\n";
  if (scenario === "editor" || scenario === "stale-error") state.open = {name: "other", text: "other draft", saved: null};
  if (scenario === "project") state.projectId = "q";
  if (scenario === "closed") state.open = null;
  const before = JSON.stringify(state);
  if (scenario.endsWith("error")) reject(new Error("save failed"));
  else resolve({name: "rig", digest: "new"});
  if (scenario === "active-error") {
    await assert.rejects(task, /save failed/);
    assert.equal(JSON.stringify(state), before);
    return;
  }
  await task;
  if (stale) {
    assert.equal(JSON.stringify(state), before);
    assert.equal(reopened, 0); assert.equal(listed, 0);
    assert.deepEqual(nodes, {});
  } else {
    assert.equal(original.saved, "sent\n"); assert.equal(original.digest, "new");
    const edited = scenario.startsWith("edit");
    assert.equal(original.text, edited ? (scenario === "edit" ? "later unsaved edit" : "sent\n\n") : "sent\n");
    assert.equal(original.text !== original.saved, edited);
    assert.equal(reopened, 1); assert.equal(listed, 1);
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
'''
    subprocess.run(["node", "-e", harness, scenario], check=True, capture_output=True, text=True)


def test_browser_parses_bom_prefixed_json():
    source = SCRIPT.read_text()
    normalize = source[source.index("  const normalizeText"):source.index("  const lines")]
    parsed = source[source.index("  function parsed()"):source.index("  const at =")]
    harness = 'const assert = require("node:assert/strict"); const state = {open: {text: "\\uFEFF{\\"label\\":\\"\\uFEFFinside\\"}"}};\n'
    harness += normalize + parsed + '\nassert.deepEqual(parsed(), {label: "\\uFEFFinside"});'
    subprocess.run(["node", "-e", harness], check=True, capture_output=True, text=True)


def test_project_refresh_after_pending_work():
    source = SCRIPT.read_text()
    working = source[source.index("  async function working("):source.index("  // ── Page and project")]
    harness = r'''
const assert = require("node:assert/strict");
const state = {working: false, projectId: "p"};
const $ = () => ({});
const clearFail = () => {};
const fail = error => {throw error;};
const syncState = () => {};
let release, refreshed = 0;
const refresh = () => { assert.equal(state.working, false); assert.equal(state.projectId, "q"); refreshed++; };
''' + working + r'''
(async () => {
  const pending = working(() => new Promise(resolve => {release = resolve;}));
  state.projectId = "q";
  await working(() => {throw new Error("busy actions must wait");});
  release(); await pending;
  assert.equal(refreshed, 1);
})().catch(error => { console.error(error); process.exitCode = 1; });
'''
    subprocess.run(["node", "-e", harness], check=True, capture_output=True, text=True)


def test_stale_list_failure_does_not_affect_another_project():
    source = SCRIPT.read_text()
    save = source[source.index("  function save() {"):source.index("  function discard()")]
    working = source[source.index("  async function working("):source.index("  // ── Page and project")]
    normalize = source[source.index("  const normalizeText"):source.index("  const lines")]
    harness = r'''
const assert = require("node:assert/strict");
const state = {projectId: "p", open: {name: "rig", digest: "old", saved: "old", text: "sent"}};
const $ = () => ({});
const clearFail = () => {};
const syncState = () => {};
const parsed = () => ({name: "rig"});
const post = async () => ({name: "rig", digest: "new"});
const openEditor = () => {};
let rejectList, errors = [], refreshes = 0;
const fail = error => errors.push(error);
const refresh = () => {refreshes++;};
const loadList = () => new Promise((resolve, reject) => {rejectList = reject;});
''' + normalize + working + save + r'''
(async () => {
  save();
  await Promise.resolve();
  assert.equal(typeof rejectList, "function");
  state.projectId = "q"; state.open = {text: "new draft", saved: null};
  rejectList(new Error("stale list failed"));
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(errors, []); assert.equal(refreshes, 1);
  assert.deepEqual(state.open, {text: "new draft", saved: null});
  assert.equal(state.working, false);
})().catch(error => {console.error(error); process.exitCode = 1;});
'''
    subprocess.run(["node", "-e", harness], check=True, capture_output=True, text=True)
