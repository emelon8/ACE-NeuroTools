import { Widget } from '@lumino/widgets';
import { context } from './api';

export function el<K extends keyof HTMLElementTagNameMap>(tag: K, className = '', text = ''): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag); node.className = className; node.textContent = text; return node;
}
export function icon(name: string): HTMLElement {
  const node = el('span', `codicon codicon-${name}`); node.setAttribute('aria-hidden', 'true'); return node;
}
export function button(label: string, action: () => void | Promise<void>, glyph?: string, className = ''): HTMLButtonElement {
  const node = el('button', className); node.type = 'button'; node.title = label;
  node.setAttribute('aria-label', label);
  if (glyph) node.append(icon(glyph));
  node.append(el('span', '', label));
  node.addEventListener('click', async () => {
    node.disabled = true;
    try { await action(); } catch (error) { report(error); }
    finally { node.disabled = false; }
  });
  return node;
}
export function report(error: unknown): void {
  const message = error instanceof Error ? error.message : String(error);
  context.log(message, true);
  const node = el('div', 'notification error', message); node.setAttribute('role', 'alert');
  node.append(button('Dismiss', () => node.remove(), 'close', 'icon-only'));
  document.getElementById('notifications')?.append(node);
}
export function empty(title: string, detail: string): HTMLElement {
  const node = el('div', 'empty'); node.append(el('h2', '', title), el('p', '', detail)); return node;
}
export function heading(title: string, detail?: string): HTMLElement {
  const node = el('header', 'panel-heading'); node.append(el('h1', '', title));
  if (detail) node.append(el('p', 'muted', detail)); return node;
}
export function table(headers: string[], rows: (string | HTMLElement)[][]): HTMLTableElement {
  const node = el('table'); const head = el('thead'); const tr = el('tr');
  for (const header of headers) { const th = el('th', '', header); th.scope = 'col'; tr.append(th); }
  head.append(tr); node.append(head); const body = el('tbody');
  for (const row of rows) { const line = el('tr'); for (const value of row) { const cell = el('td'); cell.append(value); line.append(cell); } body.append(line); }
  node.append(body); return node;
}
export function labelInput(label: string, value = '', placeholder = ''): { wrapper: HTMLLabelElement; input: HTMLInputElement } {
  const wrapper = el('label', 'field'); wrapper.append(el('span', '', label));
  const input = el('input'); input.value = value; input.placeholder = placeholder; wrapper.append(input); return { wrapper, input };
}
export function code(value: unknown): string { return value === undefined ? '—' : JSON.stringify(value); }
export function short(oid: string | null): string { return oid?.slice(0, 8) || 'No revision'; }
export function timestamp(epoch: number): string { return new Date(epoch * 1000).toLocaleString(); }
export class Panel extends Widget {
  private cleanup: (() => void)[] = [];
  constructor(label: string, glyph = 'file') {
    super(); this.title.label = label; this.title.closable = true;
    this.title.iconClass = `codicon codicon-${glyph}`; this.addClass('content-panel');
  }
  listen(target: EventTarget, event: string, fn: EventListener): void {
    target.addEventListener(event, fn); this.cleanup.push(() => target.removeEventListener(event, fn));
  }
  dispose(): void { if (this.isDisposed) return; this.cleanup.forEach(fn => fn()); super.dispose(); }
}
