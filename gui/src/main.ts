import '@lumino/widgets/style/index.css';
import '@vscode/codicons/dist/codicon.css';
import './theme.css';
import './shell.css';
import './panels.css';
import { context, request } from './api';
import { renderExplorer } from './explorer';
import { configureSchemas } from './monaco';
import { mountOutput } from './output';
import { installPalette } from './palette';
import { ChangesPanel } from './panels/changes';
import { ComparePanel } from './panels/compare';
import { DocumentPanel } from './panels/document';
import { HistoryPanel } from './panels/history';
import { OverviewPanel } from './panels/overview';
import { RecoveryPanel } from './panels/recovery';
import { ResultsPanel } from './panels/results';
import { Shell } from './shell';
import { WorkflowPanel } from './workflow/panel';
import type { Document, Session, WorkspaceState } from './types';
import { button, el, icon, Panel, report, short } from './ui';

async function start(): Promise<void> {
  context.session = await request<Session>('/session');
  context.workspace = context.session.workspaces[0];
  await context.refresh(); await configureSchemas();
  const shell = new Shell(); mountOutput(shell.output.node);
  const docs = new Map<string, DocumentPanel>(); const views = new Map<string, Panel>();
  const hasUnsaved = () => [...docs.values()].some(doc => !doc.isDisposed && doc.dirty);
  const openDoc = async (path: string) => {
    let panel = docs.get(path);
    if (!panel || panel.isDisposed) {
      const workspace = context.workspace.id;
      const document = await request<Document>(context.path(`/document?path=${encodeURIComponent(path)}`));
      if (workspace !== context.workspace.id) return;
      panel = docs.get(path);
      if (!panel || panel.isDisposed) { panel = new DocumentPanel(document); docs.set(path, panel); }
    }
    shell.open(panel);
  };
  const compare = (a: string, b: string) => shell.open(new ComparePanel(a, b));
  const restore = async (revision: string) => {
    if (hasUnsaved()) throw new Error('Save or close unsaved editors before restoring. Their buffers are not yet in EVC.');
    if (!window.confirm(`Restore parameters and tracked manifests from ${short(revision)}?\n\nEVC preserves dirty disk state in a safety snapshot. History will not rewind. Record a new revision afterwards to keep the restored state.`)) return;
    const result = await request<{ restored: string; safety_snapshot: string | null }>(context.path('/restore'), 'POST', { revision, version: context.state.status.version });
    context.log(`Restored ${short(result.restored)}${result.safety_snapshot ? ` · safety snapshot ${short(result.safety_snapshot)}` : ''}. Record the restored state when ready.`);
    await context.refresh();
    for (const doc of docs.values()) {
      if (doc.isDisposed) continue;
      if (context.state.documents.includes(doc.path)) await doc.reload(); else doc.dispose();
    }
    view('changes');
  };
  const view = (name: string): Panel => {
    if (!context.workspace) name = 'workflow';
    let panel = views.get(name);
    if (!panel || panel.isDisposed) {
      if (name === 'workflow') panel = new WorkflowPanel(async result => {
        views.get('workflow')?.dispose(); views.delete('workflow');
        await switchWorkspace(result.workspace.id);
        const workflow = view('workflow') as WorkflowPanel;
        await workflow.selectConfiguration(result.configuration);
        await context.refresh();
      }, hasUnsaved, () => { view('results'); });
      else if (name === 'changes') panel = new ChangesPanel(hasUnsaved);
      else if (name === 'history') panel = new HistoryPanel(compare, restore);
      else if (name === 'recovery') panel = new RecoveryPanel(restore);
      else if (name === 'results') panel = new ResultsPanel();
      else panel = new OverviewPanel(view);
      views.set(name, panel);
    }
    shell.open(panel);
    return panel;
  };
  const switchWorkspace = async (id: string) => {
    const selected = context.session.workspaces.find(workspace => workspace.id === id)!;
    if (id === context.workspace?.id) return;
    if (hasUnsaved() && !window.confirm('Discard unsaved editor buffers and switch experiments? Saved disk state remains in its workspace.')) { render(); return; }
    const state = await request<WorkspaceState>(`/workspaces/${encodeURIComponent(id)}/state`);
    shell.closeAll(); docs.clear(); views.clear();
    context.workspace = selected; context.state = state;
    context.dispatchEvent(new Event('change')); view('overview');
    context.log(`Opened ${selected.name}`);
  };
  const render = () => {
    if (!context.workspace) {
      shell.sidebar.node.replaceChildren(el('div', 'sidebar-heading', 'EXPLORER'), el('p', 'workspace-info', 'No experiments yet. Drop a recording to create your first experiment.'), button('Import & Run', () => { view('workflow'); }, 'run-all'));
      shell.title.textContent = 'ACENeuroTools';
      shell.status.replaceChildren(el('span', 'status-local', 'LOCAL'), el('span', '', context.session.project), el('span', 'spacer'), el('span', 'viridis-strip'));
      return;
    }
    renderExplorer(shell.sidebar.node, path => { void openDoc(path).catch(report); }, view, switchWorkspace);
    const status = context.state.status;
    shell.title.textContent = `${context.workspace.name} — ACENeuroTools`;
    shell.status.replaceChildren(icon('remote'), el('span', 'status-local', 'LOCAL'), button(status.branch, () => { view('history'); }, 'git-branch', 'status-button'), button(`${status.changes.length} changed`, () => { view('changes'); }, 'source-control', 'status-button'), el('span', 'muted', short(status.head)), el('span', 'spacer'), el('span', '', hasUnsaved() ? 'Unsaved editor changes' : status.clean ? 'EVC up to date' : 'Unrecorded working state'), el('span', 'viridis-strip'), el('span', '', 'Viridis'));
  };
  context.addEventListener('change', render); context.addEventListener('buffers', render);
  shell.activityButton('Explorer', 'files', () => { shell.sidebar.show(); shell.vertical.update(); }).classList.add('selected');
  shell.activityButton('Experiment changes', 'source-control', () => { view('changes'); });
  shell.activityButton('History', 'history', () => { view('history'); });
  shell.activityButton('Import & Run', 'run-all', () => { view('workflow'); });
  shell.activityButton('Results', 'graph-line', () => { view('results'); });
  shell.activityButton('Recovery journal', 'archive', () => { view('recovery'); });
  const showPalette = installPalette(shell);
  const commands = shell.commands;
  const command = (id: string, label: string, execute: () => void | Promise<void>, keys?: string[]) => {
    commands.addCommand(id, { label, execute: () => Promise.resolve().then(execute).catch(report) });
    if (keys) commands.addKeyBinding({ command: id, keys, selector: 'body' });
  };
  command('palette', 'Show command palette', showPalette, ['Accel Shift P']);
  command('save', 'Save active parameter document', async () => {
    const current = shell.focus.currentWidget;
    if (current instanceof DocumentPanel) await current.save();
  }, ['Accel S']);
  command('save-all', 'Save all parameter documents', async () => { for (const doc of docs.values()) if (!doc.isDisposed && doc.dirty) await doc.save(); });
  command('reload', 'Reload active parameter document', async () => {
    const current = shell.focus.currentWidget;
    if (current instanceof DocumentPanel && (!current.dirty || window.confirm('Discard unsaved changes and reload this document?'))) await current.reload();
  });
  command('refresh', 'Refresh workspace', () => context.refresh(), ['Accel Shift R']);
  command('workflow', 'Import recordings and run experiments', () => { view('workflow'); });
  command('overview', 'Open workspace overview', () => { view('overview'); });
  command('changes', 'Review experiment changes', () => { view('changes'); }, ['Accel Shift G']);
  command('history', 'Browse experiment history', () => { view('history'); });
  command('results', 'Browse result artifacts', () => { view('results'); });
  command('recovery', 'Open recovery journal', () => { view('recovery'); });
  command('sidebar', 'Toggle explorer', () => { shell.sidebar.setHidden(!shell.sidebar.isHidden); shell.vertical.update(); }, ['Accel B']);
  command('output', 'Toggle output panel', () => { shell.output.setHidden(!shell.output.isHidden); shell.vertical.update(); }, ['Accel J']);
  command('about', 'About ACENeuroTools workbench', () => {
    const panel = new Panel('About', 'info'); panel.node.append(el('h1', '', 'ACENeuroTools Workbench'), el('p', '', `Local research workspace · ${context.session.version}`), el('p', '', 'Built with Lumino (JupyterLab), Monaco Editor and VS Code Codicons. GPL-3.0-or-later.'), el('p', 'muted', 'Codicons artwork © Microsoft Corporation, CC-BY-4.0. Supporting code and Monaco: MIT. Lumino: BSD-3-Clause. Full attribution and license texts are available in the bundled notices.'), el('p', 'muted', 'No telemetry, AI features or external runtime assets. Import & Run configures local scientific workers over the existing ACENeuroTools modules.')); const notices = el('a', '', 'Third-party license notices'); notices.href = '/THIRD_PARTY_NOTICES.txt'; notices.target = '_blank'; notices.rel = 'noopener'; panel.node.append(notices); shell.open(panel);
  });
  shell.addMenu('File', ['save', 'save-all', 'reload', 'refresh']);
  shell.addMenu('View', ['palette', 'overview', 'sidebar', 'output']);
  shell.addMenu('Experiment', ['workflow', 'changes', 'history', 'results', 'recovery']);
  shell.addMenu('Help', ['about']);
  window.addEventListener('beforeunload', event => { if (hasUnsaved()) { event.preventDefault(); event.returnValue = ''; } });
  window.addEventListener('dragover', event => { if (event.dataTransfer?.types.includes('Files')) event.preventDefault(); });
  window.addEventListener('drop', event => {
    if (!event.dataTransfer?.types.includes('Files')) return;
    event.preventDefault(); const workflow = view('workflow') as WorkflowPanel;
    void workflow.acceptDrop(event.dataTransfer);
  });
  render(); view(context.workspace ? 'overview' : 'workflow');
  if (context.workspace && context.state.documents.includes('parameters/analysis.cnmfe.json')) await openDoc('parameters/analysis.cnmfe.json');
  if (!context.workspace) { context.log('Drop a recording or choose files to create an experiment.'); return; }
  context.log(`Connected to local EVC workspace: ${context.workspace.name}`);
  context.log(`${context.state.documents.length} parameter documents · ${statusText()} · Import & Run available for recording setup and local execution`);
  function statusText() { return context.state.status.clean ? 'working state clean' : 'unrecorded changes'; }
}
void start().catch(error => {
  const host = document.getElementById('app')!; const node = el('div', 'startup-error');
  node.append(el('h1', '', 'Unable to open the workbench'), el('p', '', String(error)), el('p', 'muted', 'Start ace-workbench and open its local session URL. The session token stays in this browser tab.'), button('Retry connection', () => location.reload())); host.replaceChildren(node);
});
