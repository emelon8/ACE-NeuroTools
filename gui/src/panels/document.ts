import type { Message } from '@lumino/messaging';
import { context, request } from '../api';
import { monaco, options } from '../monaco';
import type { Document } from '../types';
import { button, el, Panel } from '../ui';
import { parameterForm } from './parameters';

export class DocumentPanel extends Panel {
  private editor: monaco.editor.IStandaloneCodeEditor;
  private model: monaco.editor.ITextModel;
  private document: Document;
  private base: string;
  private form = el('div', 'form-host');
  private editorHost = el('div', 'monaco-host');
  private mode: 'json' | 'form' = 'json';
  private saved: string;
  private status = el('span', 'muted', 'Saved');
  private saving = false;
  constructor(document: Document) {
    super(document.path.split('/').pop()!, 'json'); this.addClass('document-panel');
    this.document = document; this.saved = document.text; this.base = context.path('/document');
    const bar = el('div', 'document-toolbar');
    bar.append(el('span', 'breadcrumb', `${context.workspace.name}  ›  ${document.path}`), el('span', 'spacer'));
    bar.append(button('Parameters', () => this.switchMode('form'), 'settings-gear'), button('JSON', () => this.switchMode('json'), 'code'), button('Save', () => this.save(), 'save', 'primary'));
    const foot = el('div', 'document-footer'); foot.append(this.status, el('span', 'spacer'), el('span', 'muted', 'JSON · UTF-8 · 2 spaces'));
    this.node.append(bar, this.editorHost, this.form, foot); this.form.hidden = true;
    this.model = monaco.editor.createModel(document.text, 'json', monaco.Uri.parse(`ace://${context.workspace.id}/${document.path}`));
    this.editor = monaco.editor.create(this.editorHost, { ...options, model: this.model, ariaLabel: `JSON editor for ${document.path}` });
    this.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => { void this.save().catch(error => context.log(String(error), true)); });
    this.model.onDidChangeContent(() => {
      this.title.label = `${document.path.split('/').pop()}${this.dirty ? ' ●' : ''}`;
      this.status.textContent = this.dirty ? 'Unsaved changes' : 'Saved';
      context.dispatchEvent(new Event('buffers'));
    });
  }
  get dirty(): boolean { return this.model.getValue() !== this.saved; }
  get path(): string { return this.document.path; }
  switchMode(mode: 'json' | 'form'): void {
    this.mode = mode; this.form.hidden = mode !== 'form'; this.editorHost.hidden = mode !== 'json';
    if (mode === 'form') this.form.replaceChildren(parameterForm(this.model.getValue(), text => {
      this.model.pushEditOperations([], [{ range: this.model.getFullModelRange(), text }], () => null);
    }));
    else { this.editor.layout(); this.editor.focus(); }
  }
  async save(): Promise<void> {
    if (this.saving) return;
    this.saving = true;
    const text = this.model.getValue();
    try {
      const saved = await request<Document>(this.base, 'PUT', { path: this.path, text, etag: this.document.etag });
      this.document = saved; this.saved = text;
      this.title.label = `${this.path.split('/').pop()}${this.dirty ? ' ●' : ''}`;
      this.status.textContent = this.dirty ? 'Unsaved changes' : 'Saved to disk · revision not yet recorded';
      context.log(`Saved ${this.path}`); context.dispatchEvent(new Event('buffers')); await context.refresh();
    } finally { this.saving = false; }
  }
  async reload(): Promise<void> {
    const value = await request<Document>(`${this.base}?path=${encodeURIComponent(this.path)}`);
    this.document = value; this.saved = value.text; this.model.setValue(value.text);
    this.switchMode(this.mode);
  }
  protected onCloseRequest(message: Message): void {
    if (this.dirty && !window.confirm(`Discard unsaved edits to ${this.path}? Saved disk state and EVC revisions are retained.`)) return;
    super.onCloseRequest(message); this.dispose(); context.dispatchEvent(new Event('buffers'));
  }
  dispose(): void { if (this.isDisposed) return; this.editor.dispose(); this.model.dispose(); super.dispose(); }
}
