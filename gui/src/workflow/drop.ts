import type { DroppedFile } from './types';

interface Entry { name: string; isFile: boolean; isDirectory: boolean; file?: (resolve: (file: File) => void, reject: (error: DOMException) => void) => void; createReader?: () => { readEntries: (resolve: (entries: Entry[]) => void, reject: (error: DOMException) => void) => void } }

export class RecordingDropReader {
  fromPicker(files: FileList): DroppedFile[] {
    return [...files].filter(file => file.name !== '.DS_Store').map(file => ({ path: file.webkitRelativePath || file.name, file }));
  }

  async fromDrop(data: DataTransfer): Promise<DroppedFile[]> {
    // Capture entries synchronously: the browser clears the drag data store after dispatch.
    const entries = [...data.items].filter(item => item.kind === 'file').map(item => item.webkitGetAsEntry?.() as Entry | null);
    const fallback = this.fromPicker(data.files);
    if (!entries.length || entries.some(entry => !entry)) return fallback;
    const result: DroppedFile[] = [];
    const walk = async (entry: Entry, parent: string, depth: number): Promise<void> => {
      if (depth > 20 || result.length >= 10000) throw new Error('Recording selection exceeds the folder depth or 10,000-file limit.');
      if (entry.name === '.DS_Store') return;
      const path = parent ? `${parent}/${entry.name}` : entry.name;
      if (entry.isFile && entry.file) {
        const file = await new Promise<File>((resolve, reject) => entry.file!(resolve, reject));
        result.push({ path, file });
      } else if (entry.isDirectory && entry.createReader) {
        const reader = entry.createReader();
        while (true) {
          const batch = await new Promise<Entry[]>((resolve, reject) => reader.readEntries(resolve, reject));
          if (!batch.length) break;
          for (const child of batch) await walk(child, path, depth + 1);
        }
      } else throw new Error(`Cannot read ${path}. Choose the recording folder using the folder picker.`);
    };
    for (const entry of entries) await walk(entry!, '', 0);
    return result;
  }
}
