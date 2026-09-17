import { context } from './api';
import { button, el } from './ui';

export function mountOutput(host: HTMLElement): void {
  const bar = el('div', 'output-tabs'); const title = el('span', 'active', 'OUTPUT');
  const filter = el('select'); filter.setAttribute('aria-label', 'Output filter');
  for (const text of ['All operations', 'Errors only']) { const option = el('option', '', text); filter.append(option); }
  const lines = el('div', 'output-lines'); lines.setAttribute('role', 'log'); lines.setAttribute('aria-label', 'Workbench operation log'); lines.setAttribute('aria-live', 'polite');
  const applyFilter = () => { for (const child of Array.from(lines.children) as HTMLElement[]) child.hidden = filter.value === 'Errors only' && child.dataset.error !== 'true'; };
  filter.addEventListener('change', applyFilter);
  bar.append(title, el('span', 'muted', 'ACENeuroTools'), el('span', 'spacer'), filter, button('Clear output', () => lines.replaceChildren(), 'clear-all', 'icon-only'));
  host.append(bar, lines);
  context.addEventListener('log', event => {
    const { message, error, time } = (event as CustomEvent).detail;
    const row = el('div', error ? 'log-line error' : 'log-line'); row.dataset.error = String(error);
    row.append(el('span', 'log-time', time.toLocaleTimeString()), el('span', error ? 'error' : 'accent', error ? 'ERROR' : 'INFO '), el('span', '', message));
    lines.append(row); while (lines.children.length > 500) lines.firstElementChild!.remove();
    applyFilter(); lines.scrollTop = lines.scrollHeight;
  });
}
