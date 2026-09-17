import { context, request } from '../api';
import { tracePlot } from '../plot';
import type { Preview, Run, Verification } from '../types';
import { button, el, empty, heading, Panel, report, short, table } from '../ui';

export class ResultsPanel extends Panel {
  private detail = el('div', 'artifact-preview');
  private generation = 0;
  constructor() {
    super('Results', 'graph-line');
    this.node.append(heading('Results', 'Artifacts linked to their producing revision. Integrity is checked on request.'));
    const list = el('div', 'results-list'); this.node.append(list, this.detail);
    const load = async () => {
      const runs = await request<Run[]>(context.path('/results'));
      if (this.isDisposed) return;
      list.replaceChildren();
      if (!runs.length) list.append(empty('No result manifests', 'Results recorded by the EVC pipeline hooks appear here. Run scientific processing through the existing CLI.'));
      for (const run of runs) {
        const section = el('section', 'result-run'); const status = el('span', 'muted', 'Not verified this session');
        const bar = el('div', 'toolbar');
        bar.append(el('h2', '', run.id), el('span', 'spacer'), status, button('Verify integrity', async () => {
          status.textContent = 'Hashing artifacts…';
          try {
            const report = await request<Verification>(context.path(`/results/${encodeURIComponent(run.id)}/verify`), 'POST');
            status.textContent = report.clean ? `Verified · ${report.verified.length} artifact(s)` : `Missing: ${report.missing.join(', ') || 'none'} · Modified: ${report.modified.join(', ') || 'none'}`;
            status.className = report.clean ? 'accent' : 'error';
            context.log(`Integrity ${run.id}: ${status.textContent}`, !report.clean);
          } catch (error) { status.textContent = 'Verification failed'; throw error; }
        }, 'verified'));
        section.append(bar);
        if (run.error) section.append(el('p', 'error', run.error));
        else section.append(table(['Artifact', 'Bytes', 'SHA-256', 'Producer / revision'], run.artifacts.map(artifact => [
          button(artifact.relpath, () => this.preview(run.id, artifact.relpath), 'file', 'text-button'),
          artifact.size.toLocaleString(), el('code', '', short(artifact.sha256)), `${artifact.producer?.pipeline || 'Unspecified'} / ${short(artifact.producer?.revision || null)}`,
        ])));
        list.append(section);
      }
    };
    void load().catch(report); this.listen(context, 'change', () => { void load().catch(report); });
  }
  private async preview(run: string, path: string): Promise<void> {
    const generation = ++this.generation;
    const data = await request<Preview>(context.path(`/results/${encodeURIComponent(run)}/preview?path=${encodeURIComponent(path)}`));
    if (this.isDisposed || generation !== this.generation) return;
    this.detail.replaceChildren(el('h2', '', path));
    if (data.kind === 'text') this.detail.append(el('pre', '', data.text));
    else {
      if (data.numeric?.length) this.detail.append(tracePlot(data.columns!, data.numeric));
      this.detail.append(el('p', 'muted', `${data.rows!.length} rows shown${data.truncated ? ' · preview limited to 500 rows' : ''}. Preview alone does not verify integrity.`));
      const scroll = el('div', 'table-scroll'); scroll.append(table(data.columns!, data.rows!)); this.detail.append(scroll);
    }
    this.detail.scrollIntoView({ block: 'nearest' });
  }
}
