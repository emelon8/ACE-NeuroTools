import { describe, expect, it } from 'vitest';
import { RecordingDropReader } from './drop';

describe('recording folder enumeration', () => {
  it('keeps all files when a browser directory reader returns multiple batches', async () => {
    const makeFile = (name: string) => ({ name, isFile: true, isDirectory: false, file: (resolve: (file: File) => void) => resolve(new File(['data'], name)) });
    const batches = [Array.from({ length: 100 }, (_, index) => makeFile(`${index}.avi`)), [makeFile('100.avi'), makeFile('metaData.json')], []];
    const entry = { name: 'recording', isFile: false, isDirectory: true, createReader: () => ({ readEntries: (resolve: (entries: unknown[]) => void) => resolve(batches.shift()!) }) };
    const data = { files: [], items: [{ kind: 'file', webkitGetAsEntry: () => entry }] } as unknown as DataTransfer;
    const files = await new RecordingDropReader().fromDrop(data);
    expect(files).toHaveLength(102);
    expect(files.map(file => file.path)).toContain('recording/100.avi');
    expect(files.map(file => file.path)).toContain('recording/metaData.json');
    expect(files.every(file => file.file.size === 4)).toBe(true);
  });

  it('propagates unreadable files rather than silently omitting a recording segment', async () => {
    const entry = { name: '0.avi', isFile: true, isDirectory: false, file: (_resolve: unknown, reject: (error: Error) => void) => reject(new Error('unreadable source')) };
    const data = { files: [], items: [{ kind: 'file', webkitGetAsEntry: () => entry }] } as unknown as DataTransfer;
    await expect(new RecordingDropReader().fromDrop(data)).rejects.toThrow('unreadable source');
  });
});
