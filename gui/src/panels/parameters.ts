import { el } from '../ui';

export function parameterForm(text: string, onChange: (text: string) => void): HTMLElement {
  const node = el('div', 'parameter-form');
  let document: Record<string, unknown>;
  try { document = JSON.parse(text); } catch { node.append(el('p', 'error', 'Fix JSON syntax before using the parameter form.')); return node; }
  const params = (document.params && typeof document.params === 'object' ? document.params : document) as Record<string, unknown>;
  node.append(el('p', 'muted', 'Changes stay in the editor until you save. Record a revision to add them to experiment history.'));
  for (const [key, value] of Object.entries(params)) {
    if (['_csv', 'schema'].includes(key)) continue;
    const label = el('label', 'parameter-row'); label.append(el('span', 'mono', key));
    let input: HTMLInputElement | HTMLSelectElement;
    if (typeof value === 'boolean') {
      input = el('select'); for (const option of ['true', 'false']) { const element = el('option', '', option); element.value = option; input.append(element); }
      input.value = String(value);
    } else {
      input = el('input'); input.value = typeof value === 'string' ? value : JSON.stringify(value);
      if (typeof value === 'number') { input.type = 'number'; input.step = 'any'; }
    }
    input.setAttribute('aria-label', key);
    const error = el('span', 'field-error'); error.setAttribute('aria-live', 'polite');
    input.addEventListener('change', () => {
      try {
        const next = typeof value === 'string' ? input.value : JSON.parse(input.value);
        if (typeof value === 'number' && (typeof next !== 'number' || !Number.isFinite(next))) throw new Error('Enter a finite number.');
        if (Array.isArray(value) && !Array.isArray(next)) throw new Error('Enter a JSON array, for example [3, 3].');
        params[key] = next; error.textContent = ''; input.removeAttribute('aria-invalid');
        onChange(JSON.stringify(document, null, 2) + '\n');
      } catch (reason) { error.textContent = reason instanceof Error ? reason.message : 'Invalid value'; input.setAttribute('aria-invalid', 'true'); }
    });
    label.append(input, error); node.append(label);
  }
  return node;
}
