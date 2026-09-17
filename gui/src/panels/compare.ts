import { context, request } from '../api';
import { monaco, options } from '../monaco';
import type { Document, FileDiff } from '../types';
import { button, code, el, empty, heading, Panel, report, short, table } from '../ui';

export class ComparePanel extends Panel {
  private editor?: monaco.editor.IStandaloneDiffEditor;
  private models: monaco.editor.ITextModel[] = [];
  private host = el('div', 'diff-host');
  private selection = 0;
  constructor(private a: string, private b: string) {
    super(`${short(a)} ↔ ${short(b)}`, 'diff'); this.addClass('compare-panel');
    this.node.append(heading('Compare revisions', `${a} → ${b}`));
    const files = el('div', 'diff-files'); this.node.append(files, this.host);
    void request<FileDiff[]>(context.path(`/diff?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`)).then(diffs => {
      if (this.isDisposed) return;
      if (!diffs.length) { files.append(empty('Identical parameter state', 'These revisions contain the same tracked files.')); return; }
      for (const diff of diffs) {
        files.append(button(`${diff.status}  ${diff.path}`, () => this.show(diff), 'diff'));
      }
      return this.show(diffs.find(d => d.path.startsWith('parameters/') && d.path.endsWith('.json')) ?? diffs[0]);
    }).catch(report);
  }
  private async show(diff: FileDiff): Promise<void> {
    const selection = ++this.selection;
    if (!diff.path.startsWith('parameters/') || !diff.path.endsWith('.json')) {
      this.release(); this.host.replaceChildren(table(['Key', 'Previous', 'Selected'], diff.param_changes.map(c => [c.key, code(c.old), code(c.new)]))); return;
    }
    const read = async (revision: string, absent: boolean) => absent ? '' : (await request<Document>(context.path(`/document?path=${encodeURIComponent(diff.path)}&revision=${encodeURIComponent(revision)}`))).text;
    const [original, modified] = await Promise.all([read(this.a, diff.status === 'added'), read(this.b, diff.status === 'removed')]);
    if (this.isDisposed || selection !== this.selection) return;
    this.release(); this.host.replaceChildren();
    this.models = [monaco.editor.createModel(original, 'json'), monaco.editor.createModel(modified, 'json')];
    this.editor = monaco.editor.createDiffEditor(this.host, { ...options, readOnly: true, originalEditable: false, renderSideBySide: true });
    this.editor.setModel({ original: this.models[0], modified: this.models[1] });
  }
  private release(): void { this.editor?.dispose(); this.models.forEach(model => model.dispose()); this.models = []; }
  dispose(): void { if (this.isDisposed) return; this.release(); super.dispose(); }
}
