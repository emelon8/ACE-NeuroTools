import { context } from './api';
import { button, el, icon } from './ui';

export function renderExplorer(host: HTMLElement, open: (path: string) => void, view: (name: string) => void, switchWorkspace: (id: string) => Promise<void>): void {
  const top = el('div', 'sidebar-heading'); top.append(el('span', '', 'EXPLORER'), el('span', 'spacer'), button('Refresh workspace', () => context.refresh(), 'refresh', 'icon-only'));
  const picker = el('select', 'workspace-picker'); picker.setAttribute('aria-label', 'Selected experiment');
  for (const workspace of context.session.workspaces) { const option = el('option', '', workspace.name); option.value = workspace.id; picker.append(option); }
  picker.value = context.workspace.id;
  picker.addEventListener('change', () => { void switchWorkspace(picker.value).catch(error => context.log(String(error), true)); });
  const project = el('div', 'tree-section'); project.append(icon('chevron-down'), icon('root-folder'), el('span', '', context.workspace.name.toUpperCase()));
  const files = el('div', 'file-tree');
  const group = el('details'); group.open = true; const summary = el('summary'); summary.append(icon('folder-opened'), 'parameters'); group.append(summary);
  for (const path of context.state.documents) {
    const changed = context.state.status.changes.some(diff => diff.path === path);
    const node = button(path.replace('parameters/', ''), () => open(path), 'json', 'file-row');
    node.title = path; if (changed) node.append(el('span', 'file-modified', 'M'));
    group.append(node);
  }
  if (!context.state.documents.length) group.append(el('p', 'muted tree-note', 'No parameter JSON documents'));
  files.append(group);
  const results = button('results', () => view('results'), 'folder', 'file-row folder-row'); files.append(results);
  files.append(el('div', 'tree-note muted', 'artifacts / untracked'));
  const evc = el('div', 'tree-section'); evc.append(icon('chevron-down'), 'EXPERIMENT VERSION CONTROL');
  const state = el('div', 'explorer-state');
  state.append(button('Changes', () => view('changes'), 'source-control', 'file-row'), button('History', () => view('history'), 'history', 'file-row'), button('Recovery journal', () => view('recovery'), 'archive', 'file-row'));
  const info = el('div', 'workspace-info');
  info.append(el('span', 'badge', 'EVC WORKSPACE'), el('p', 'muted', context.workspace.path), el('p', 'muted', 'Tracking follows .evc/ignore. Keep recordings outside tracked paths.'));
  host.replaceChildren(top, picker, project, files, evc, state, info);
}
