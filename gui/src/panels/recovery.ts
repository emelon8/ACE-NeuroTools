import { context, request } from '../api';
import type { JournalEntry } from '../types';
import { button, el, empty, heading, Panel, report, short, table, timestamp } from '../ui';

export class RecoveryPanel extends Panel {
  constructor(restore: (revision: string) => Promise<void>) {
    super('Recovery journal', 'history');
    this.node.append(heading('Recovery journal', 'Safety snapshots, restores, revisions and failed-run events from the EVC journal.'));
    const body = el('div'); this.node.append(body);
    const load = async () => {
      const entries = await request<JournalEntry[]>(context.path('/recovery'));
      if (this.isDisposed) return;
      body.replaceChildren(entries.length ? table(['Time', 'Operation', 'Message', 'State', ''], entries.map(entry => [
        timestamp(entry.timestamp), entry.op, entry.message, short(entry.new),
        entry.new && entry.op !== 'run-failed' && !entry.ref.includes('notes') ? button('Restore state', () => restore(entry.new), 'discard') : el('span', 'muted', 'Event only'),
      ])) : empty('Journal is empty', 'EVC events will appear here as you work.'));
    };
    void load().catch(report); this.listen(context, 'change', () => { void load().catch(report); });
  }
}
