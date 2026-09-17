import { describe, expect, it } from 'vitest';
import { parseParameter } from './parameter-value';

describe('scientific parameter form types', () => {
  it('preserves finite numbers and arrays without string coercion', () => {
    expect(parseParameter(0.85, '0.91')).toBe(0.91);
    expect(parseParameter([3, 3], '[4, 4]')).toEqual([4, 4]);
    expect(parseParameter(true, 'false')).toBe(false);
  });
  it.each(['null', '"0.9"', 'true', '1e999', 'NaN', ''])('rejects invalid numeric input %s', input => {
    expect(() => parseParameter(0.85, input)).toThrow();
  });
  it('does not coerce booleans or replace arrays and objects with scalars', () => {
    expect(() => parseParameter(false, '0')).toThrow();
    expect(() => parseParameter([3, 3], '3')).toThrow();
    expect(() => parseParameter({ x: 1 }, '[]')).toThrow();
  });
  it('allows raw strings and explicitly entered null values', () => {
    expect(parseParameter('oasis', 'corr_pnr')).toBe('corr_pnr');
    expect(parseParameter(null, 'null')).toBeNull();
    expect(parseParameter(null, '[2, 3]')).toEqual([2, 3]);
  });
});
