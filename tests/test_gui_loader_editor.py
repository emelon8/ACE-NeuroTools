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


@pytest.mark.parametrize("operation", ["open", "delete"])
@pytest.mark.parametrize("scenario", ["normal", "project", "editor", "closed", "edit", "error", "stale-error", "stale-list-error"])
def test_open_delete_preserve_current_editor(operation, scenario):
    source = SCRIPT.read_text()
    if operation == "open":
        function = source[source.index("  async function openDefinition("):source.index("  function openEditor(")]
    else:
        function = source[source.index("  function remove()"):source.index("  // ── Check against an experiment")]
    harness = r'''
const assert = require("node:assert/strict");
const [operation, scenario] = process.argv.slice(1);
const original = {name: "rig", text: "old", saved: "old", digest: "digest"};
const state = {projectId: "p", open: original, editorSeq: 0};
let task, resolve, reject, opened = 0, shown = 0, messages = 0, listed = 0;
const window = {confirm: () => true};
const confirmDiscard = () => true;
const working = action => {task = action(); return task;};
const query = extra => new URLSearchParams({project: state.projectId, ...extra}).toString();
const request = () => new Promise((yes, no) => {resolve = yes; reject = no;});
const post = (route, body) => {assert.equal(body.project, "p"); return request();};
const openEditor = open => {state.open = open; opened++; state.editorSeq++;};
const showProblems = () => {};
const closeEditor = () => {state.open = null; state.editorSeq++;};
const showStart = () => shown++;
const $ = () => ({replaceChildren: () => messages++});
const element = () => ({});
const loadList = async () => {
  listed++;
  if (scenario === "stale-list-error") {
    state.projectId = "q"; state.open = {text: "new project draft"};
    throw new Error("stale list failed");
  }
};
''' + function + r'''
(async () => {
  if (operation === "open") task = openDefinition("rig", true); else remove();
  if (scenario === "project") state.projectId = "q";
  if (["editor", "stale-error"].includes(scenario)) {state.open = {text: "new draft"}; state.editorSeq++;}
  if (scenario === "closed") closeEditor();
  if (scenario === "edit") original.text = "later edit";
  const before = JSON.stringify(state);
  if (scenario === "error" || scenario === "stale-error") reject(new Error("request failed"));
  else resolve({name: "rig", text: "loaded", digest: "new", problems: [], backup: "backup"});
  if (scenario === "error") {await assert.rejects(task, /request failed/); return;}
  await task;
  if (["project", "editor", "closed", "stale-error"].includes(scenario) || (operation === "open" && scenario === "edit")) {
    assert.equal(JSON.stringify(state), before); assert.equal(opened, 0); assert.equal(shown, 0); assert.equal(messages, 0);
  } else if (operation === "delete" && scenario === "edit") {
    assert.equal(state.open.text, "later edit"); assert.equal(state.open.name, null);
    assert.equal(state.open.digest, null); assert.equal(state.open.saved, null); assert.equal(shown, 0);
  } else if (scenario === "stale-list-error" && operation === "delete") {
    assert.equal(state.projectId, "q"); assert.equal(state.open.text, "new project draft");
  } else if (operation === "open") {
    assert.equal(state.open.text, "loaded"); assert.equal(opened, 1);
  } else {
    assert.equal(state.open, null); assert.equal(shown, 1); assert.equal(listed, 1);
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
'''
    subprocess.run(["node", "-e", harness, operation, scenario], check=True, capture_output=True, text=True)


def test_experiment_selector_disabled_while_detection_pending():
    source = SCRIPT.read_text()
    function = source[source.index("  async function working("):source.index("  // ── Page and project")]
    harness = r'''
const assert = require("node:assert/strict");
const state = {working: false, projectId: "p"}, nodes = {};
const $ = id => nodes[id] ||= {};
const clearFail = () => {}, syncState = () => {}, refresh = () => {};
const fail = error => {throw error;};
let resolve;
''' + function + r'''
(async () => {
  const task = working(() => new Promise(yes => {resolve = yes;}));
  assert.equal($("loaders-experiment").disabled, true);
  resolve(); await task;
  assert.equal($("loaders-experiment").disabled, false);
})().catch(error => {console.error(error); process.exitCode = 1;});
'''
    subprocess.run(["node", "-e", harness], check=True, capture_output=True, text=True)


@pytest.mark.parametrize("scenario", ["empty", "single", "multiple"])
def test_suggestion_dropdown_selection_and_actions(scenario):
    source = SCRIPT.read_text()
    function = source[source.index("  function suggestionCards("):source.index("  async function detect()")]
    harness = r'''
const assert = require("node:assert/strict");
const scenario = process.argv[1];
const nodes = [];
const element = (tag, text, cls) => {
  const node = {tag, textContent: text || "", className: cls || "", children: [], value: "",
    append(...children) {this.children.push(...children);},
    setAttribute(key, value) {this[key] = value;}};
  nodes.push(node); return node;
};
const actions = [];
const suggestionAction = item => actions.push(item.name);
const builtin = {kind: "builtin", name: "known", label: "Known system", reason: "Recognised"};
const saved = {kind: "project", name: "saved", label: "Saved rig", reason: "Configured"};
const neo = {kind: "neo", name: "IntanIO", label: "Create with IntanIO", reason: "File extension hint"};
''' + function + r'''
const options = scenario === "empty" ? [] : scenario === "single" ? [builtin] : [builtin, saved, neo];
suggestionCards(options);
const select = nodes.find(node => node.tag === "select");
const button = nodes.find(node => node.tag === "button");
if (scenario === "empty") {
  assert.equal(select, undefined); assert.equal(button, undefined);
} else {
  const reason = nodes.find(node => node.id === "loaders-suggestion-reason");
  assert.equal(select["aria-describedby"], reason.id);
  if (scenario === "single") {
    assert.equal(select.value, "0"); assert.equal(button.disabled, false);
    assert.equal(button.textContent, "View configured loader"); button.onclick();
    assert.deepEqual(actions, ["known"]);
  } else {
    assert.equal(select.value, ""); assert.equal(button.disabled, true);
    button.onclick(); assert.deepEqual(actions, []);
    for (const [index, label] of [[0, "View configured loader"], [1, "Open saved loader"], [2, "Create loader"]]) {
      select.value = String(index); select.onchange();
      assert.equal(button.disabled, false); assert.equal(button.textContent, label);
      assert.ok(reason.textContent.includes(options[index].reason)); button.onclick();
    }
    assert.deepEqual(actions, ["known", "saved", "IntanIO"]);
    assert.equal(nodes.filter(node => node.tag === "button").length, 1);
  }
}
'''
    subprocess.run(["node", "-e", harness, scenario], check=True, capture_output=True, text=True)
