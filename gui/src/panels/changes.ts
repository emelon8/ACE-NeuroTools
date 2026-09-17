import { context, request } from '../api';
import { button, code, el, empty, heading, Panel, short, table } from '../ui';

export class ChangesPanel extends Panel {
  private changes = el('div');
  private message = el('textarea');
  constructor(hasUnsaved: () => boolean) {
    super('Experiment changes', 'source-control');
    this.node.append(heading('Experiment changes', 'Review saved parameter changes before recording a revision.'));
    this.message.placeholder = 'Describe the experiment changes…'; this.message.rows = 3;
    this.message.setAttribute('aria-label', 'Revision message'); this.message.maxLength = 4000;
    const form = el('div', 'record-form');
    form.append(this.message, button('Record revision', async () => {
      if (hasUnsaved()) throw new Error('Save or close unsaved editor buffers before recording a revision.');
      if (!this.message.value.trim()) throw new Error('Enter a revision message.');
      const result = await request<{ revision: string }>(context.path('/record'), 'POST', { message: this.message.value, version: context.state.status.version });
      this.message.value = ''; context.log(`Recorded revision ${short(result.revision)}`); await context.refresh();
    }, 'check', 'primary'));
    this.node.append(form, this.changes);
    const render = () => {
      const status = context.state.status;
      this.changes.replaceChildren();
      if (!status.changes.length) { this.changes.append(empty(status.clean ? 'No saved changes' : 'No initial revision', status.clean ? 'The working state matches the latest revision. Unsaved editor changes are kept separately.' : 'Record the current workspace to begin its history.')); return; }
      for (const diff of status.changes) {
        const group = el('section', 'change-group'); group.append(el('h3', 'mono', `${diff.status.toUpperCase()}  ${diff.path}`));
        if (diff.param_changes.length) group.append(table(['Parameter', 'Previous', 'Working state'], diff.param_changes.map(c => [c.key, code(c.old), code(c.new)])));
        else group.append(el('p', 'muted', 'File contents changed. Open the document to inspect it.'));
        this.changes.append(group);
      }
    };
    render(); this.listen(context, 'change', render);
  }
}
