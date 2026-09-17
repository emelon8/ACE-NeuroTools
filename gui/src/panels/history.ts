import { context, request } from '../api';
import type { Revision } from '../types';
import { button, el, empty, heading, Panel, report, short, timestamp } from '../ui';

export class HistoryPanel extends Panel {
  private list = el('div', 'history-list');
  private details = el('div', 'revision-detail');
  private generation = 0;
  constructor(compare: (a: string, b: string) => void, restore: (revision: string) => Promise<void>) {
    super('Experiment history', 'history');
    this.node.append(heading('Experiment history', 'Revisions of parameters and result manifests. Newest first.'));
    this.node.append(this.list, this.details);
    const load = async () => {
      const generation = ++this.generation;
      const revisions = await request<Revision[]>(context.path('/history'));
      if (this.isDisposed || generation !== this.generation) return;
      this.list.replaceChildren(); this.details.replaceChildren();
      if (!revisions.length) this.list.append(empty('No revisions yet', 'Open Experiment changes and record your first revision.'));
      for (const [index, revision] of revisions.entries()) {
        const row = el('div', 'history-row');
        const graph = el('div', 'history-graph'); graph.append(el('span', 'revision-dot'));
        const description = el('div', 'history-description');
        description.append(button(revision.message.split('\n')[0], () => this.show(revision), undefined, 'text-button'), el('span', 'muted', `${revision.author} · ${timestamp(revision.author_time)}`));
        row.append(graph, description, el('code', 'revision-id', short(revision.oid)));
        if (index === 0) row.append(el('span', 'badge', 'HEAD'));
        row.append(button('Compare to HEAD', () => compare(revision.oid, 'HEAD'), 'diff', 'icon-only'), button('Restore revision', () => restore(revision.oid), 'discard', 'icon-only'));
        this.list.append(row);
      }
      if (revisions.length === 200) this.list.append(el('p', 'muted', 'Showing the newest 200 revisions. Full history remains available through the CLI.'));
    };
    void load().catch(report); this.listen(context, 'change', () => { void load().catch(report); });
  }
  private async show(revision: Revision): Promise<void> {
    const generation = ++this.generation;
    const comments = await request<{ text: string }>(context.path(`/revision/${revision.oid}/comments`));
    if (this.isDisposed || generation !== this.generation) return;
    const text = el('textarea'); text.rows = 3; text.maxLength = 16000; text.setAttribute('aria-label', 'Revision comment'); text.placeholder = 'Add a research note…';
    const notes = el('pre', 'comment-thread', comments.text || 'No comments on this revision.');
    this.details.replaceChildren(el('h2', '', revision.message), el('code', '', revision.oid), notes, text, button('Add comment', async () => {
      await request(context.path(`/revision/${revision.oid}/comments`), 'POST', { text: text.value });
      context.log(`Added comment to ${short(revision.oid)}`); await this.show(revision);
    }, 'comment'));
    this.details.scrollIntoView({ block: 'nearest' });
  }
}
