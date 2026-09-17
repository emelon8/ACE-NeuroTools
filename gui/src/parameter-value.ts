/** Preserve parameter types when editing scientific settings through the form. */
export function parseParameter(previous: unknown, input: string): unknown {
  if (typeof previous === 'string') return input;
  const next: unknown = JSON.parse(input);
  if (typeof previous === 'number' && (typeof next !== 'number' || !Number.isFinite(next))) throw new Error('Enter a finite number.');
  if (typeof previous === 'boolean' && typeof next !== 'boolean') throw new Error('Choose true or false.');
  if (Array.isArray(previous) && !Array.isArray(next)) throw new Error('Enter a JSON array, for example [3, 3].');
  if (previous && typeof previous === 'object' && !Array.isArray(previous) && (!next || typeof next !== 'object' || Array.isArray(next))) throw new Error('Enter a JSON object.');
  return next;
}
