import { ApiError, request } from '../api';
import type { DroppedFile, ImportSession } from './types';

export class RecordingUploader {
  private aborter = new AbortController();
  cancel(): void { this.aborter.abort(); }

  async upload(files: DroppedFile[], existing: ImportSession | undefined, progress: (done: number, total: number, file: string) => void, begun: (session: ImportSession) => void): Promise<ImportSession> {
    if (!files.length) throw new Error('Choose recording files or a nonempty recording folder.');
    this.aborter = new AbortController();
    const sorted = [...files].sort((a, b) => a.path.localeCompare(b.path));
    const descriptors = sorted.map(item => ({ path: item.path, size: item.file.size }));
    let session: ImportSession;
    if (existing?.state === 'uploading') {
      if (JSON.stringify(existing.files.map(({ path, size }) => ({ path, size }))) !== JSON.stringify(descriptors)) throw new Error('To resume, select the same files and folder structure. Discard the incomplete copy to select different data.');
      session = existing;
    } else session = await request<ImportSession>('/workflow/imports', 'POST', { files: descriptors });
    begun(session);
    const total = sorted.reduce((sum, item) => sum + item.file.size, 0);
    let completed = 0;
    for (const [index, item] of sorted.entries()) {
      // Replay chunks on resume so changed source prefixes cannot form a hybrid recording.
      for (let offset = 0; offset < item.file.size; offset += 1024 * 1024) {
        const chunk = item.file.slice(offset, offset + 1024 * 1024);
        const response = await fetch(`/api/workflow/imports/${session.id}/files/${index}?offset=${offset}`, {
          method: 'PUT', headers: { 'X-Ace-Token': sessionStorage.getItem('ace-session') ?? '', 'Content-Type': 'application/octet-stream' },
          body: chunk, signal: this.aborter.signal,
        });
        if (!response.ok) { const data = await response.json(); throw new ApiError(response.status, data.detail || 'Upload failed.'); }
        progress(completed + offset + chunk.size, total, item.path);
      }
      completed += item.file.size;
    }
    return request<ImportSession>(`/workflow/imports/${session.id}/inspect`, 'POST');
  }
}
