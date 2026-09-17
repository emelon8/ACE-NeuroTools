import { context, request } from '../api';
import type { Document, Revision } from '../types';
import { button, el, heading, Panel, report, short, table, timestamp } from '../ui';

export class OverviewPanel extends Panel {
  constructor(view: (name: string) => void) {
    super('Workspace', 'beaker');
    this.node.append(heading('Research workspace', 'ACENeuroTools · Analysis of Calcium Imaging and Electrophysiology'));
    const body = el('div'); this.node.append(body);
    const load = async () => {
      const workspace = context.workspace;
      const revisions = await request<Revision[]>(context.path('/history?limit=5'));
      if (this.isDisposed) return;
      body.replaceChildren(el('h2', '', workspace.name), el('p', 'mono muted', workspace.path));
      if (context.state.documents.includes('parameters/experiment.json')) {
        const doc = await request<Document>(context.path('/document?path=parameters%2Fexperiment.json'));
        if (this.isDisposed) return;
        const value = JSON.parse(doc.text);
        if (value.comments) body.append(el('p', 'workspace-note', String(value.comments)));
      }
      body.append(table(['Workspace property', 'Current state'], [
        ['EVC branch', context.state.status.branch], ['Latest revision', short(context.state.status.head)],
        ['Saved parameter documents', String(context.state.documents.length)],
        ['Working state', context.state.status.clean ? 'Matches latest revision' : 'Unrecorded changes'],
        ['Storage', 'Local · tracking follows .evc/ignore'],
      ]));
      const bar = el('div', 'toolbar section-toolbar'); bar.append(button('Import & Run', () => view('workflow'), 'run-all'), button('Review changes', () => view('changes'), 'source-control'), button('Browse results', () => view('results'), 'graph-line'), button('Recovery journal', () => view('recovery'), 'history')); body.append(bar);
      body.append(el('h2', '', 'Recent revisions'), table(['Revision', 'Message', 'Recorded'], revisions.map(r => [short(r.oid), r.message, timestamp(r.author_time)])));
      body.append(el('h2', 'section-title', 'Working with this experiment'), el('p', 'muted', 'Open a parameter document from the explorer. Edit with the Parameters form or JSON editor, save to disk, then record a revision in Experiment changes. Use history to compare or restore settings.'));
      body.append(el('p', 'muted', 'Use Import & Run to attach recordings, answer the questions required by the selected operation, review a preflight plan and launch a local worker. Each run preserves its configuration, input hashes, logs and outputs.'));
    };
    void load().catch(report); this.listen(context, 'change', () => { void load().catch(report); });
  }
}
