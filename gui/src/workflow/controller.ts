import { context, request } from '../api';
import type { Session } from '../types';
import { RecordingUploader } from './transport';
import { terminal } from './types';
import type { Configuration, ConfigurationItem, DroppedFile, ImportSession, Job, Questionnaire, RunPlan, SetupResult } from './types';

export class WorkflowController extends EventTarget {
  imported?: ImportSession;
  questionnaire?: Questionnaire;
  candidate = '';
  pipeline = '';
  answers: Record<string, unknown> = {};
  destination = 'new';
  name = '';
  configuration = '';
  configurations: ConfigurationItem[] = [];
  plan?: RunPlan;
  job?: Job;
  jobs: Job[] = [];
  busy = '';
  error = '';
  progress = { done: 0, total: 0, file: '' };
  uploader = new RecordingUploader();
  private timer?: number;
  private disposed = false;
  constructor(private readonly attached: (result: SetupResult) => Promise<void>, private readonly hasUnsaved: () => boolean) { super(); }
  get workspace(): string | undefined { return context.workspace?.id; }
  get selected() { return this.imported?.candidates?.find(c => c.id === this.candidate); }
  changed(): void { if (!this.disposed) this.dispatchEvent(new Event('change')); }
  async action(label: string, work: () => Promise<void>): Promise<void> {
    if (this.busy) return;
    this.busy = label; this.error = ''; this.changed();
    try { await work(); } catch (error) { this.error = error instanceof Error ? error.message : String(error); context.log(this.error, true); }
    finally { this.busy = ''; this.changed(); }
  }
  async initialize(): Promise<void> {
    await this.action('Loading workflows', async () => {
      if (this.workspace) {
        this.configurations = await request<ConfigurationItem[]>(`/workflow/configurations?workspace=${this.workspace}`);
        this.jobs = await request<Job[]>(`/workflow/runs?workspace=${this.workspace}`);
        const running = this.jobs.find(job => !terminal.has(job.state));
        if (running) { this.job = await request<Job>(`/workflow/runs/${running.id}`); this.poll(); }
      }
      const pending = sessionStorage.getItem('ace-import');
      if (pending) {
        try {
          const imported = await request<ImportSession>(`/workflow/imports/${pending}`);
          if (imported.state !== 'attached') { this.imported = imported; if (imported.state === 'inspected' && imported.candidates!.length === 1) await this.chooseCandidate(imported.candidates![0].id); }
          else sessionStorage.removeItem('ace-import');
        } catch { sessionStorage.removeItem('ace-import'); }
      }
    });
  }
  async importFiles(files: DroppedFile[]): Promise<void> {
    if (this.busy) { this.error = 'Wait for the current operation before dropping more files.'; this.changed(); return; }
    if (this.imported && this.imported.state !== 'uploading') { this.error = 'Finish or discard the current setup before selecting more files.'; this.changed(); return; }
    await this.action('Copying recording files', async () => {
      this.plan = undefined;
      this.imported = await this.uploader.upload(files, this.imported, (done, total, file) => {
        this.progress = { done, total, file }; this.dispatchEvent(new Event('progress'));
      }, session => { this.imported = session; sessionStorage.setItem('ace-import', session.id); });
      this.name = files[0].path.includes('/') ? files[0].path.split('/')[0] : files[0].file.name.replace(/\.[^.]+$/, '');
      if (this.imported.candidates!.length === 1) await this.chooseCandidate(this.imported.candidates![0].id);
      else { this.candidate = ''; this.pipeline = ''; this.questionnaire = undefined; }
      context.log(`Copied and inspected ${files.length} recording files locally`);
    });
  }
  async chooseCandidate(id: string): Promise<void> {
    this.candidate = id; this.pipeline = this.selected!.pipelines[0].id; this.answers = {};
    await this.loadQuestions();
  }
  async loadQuestions(): Promise<void> {
    this.plan = undefined;
    this.questionnaire = await request<Questionnaire>(`/workflow/imports/${this.imported!.id}/questions`, 'POST', { candidate: this.candidate, pipeline: this.pipeline });
    this.changed();
  }
  selection() { return { candidate: this.candidate, pipeline: this.pipeline, answers: this.answers }; }
  async setup(): Promise<void> {
    await this.action(this.configuration ? 'Saving workflow settings' : 'Creating experiment setup', async () => {
      this.requireSaved();
      if (this.configuration) {
        await request(`/workflow/configuration?workspace=${this.workspace}&path=${encodeURIComponent(this.configuration)}`, 'PUT', this.selection());
        await context.refresh(); this.plan = undefined; this.imported = undefined;
      } else {
        const result = await request<SetupResult>(`/workflow/imports/${this.imported!.id}/setup`, 'POST', { ...this.selection(), destination: this.destination, name: this.name });
        sessionStorage.removeItem('ace-import');
        context.session = await request<Session>('/session');
        this.imported = undefined;
        await this.attached(result);
      }
    });
  }
  async openConfiguration(path: string, edit = false): Promise<void> {
    await this.action('Loading recording configuration', async () => {
      this.configuration = path; this.plan = undefined;
      if (edit) {
        const value = await request<Configuration>(`/workflow/configuration?workspace=${this.workspace}&path=${encodeURIComponent(path)}`);
        this.imported = await request<ImportSession>(`/workflow/imports/${value.id}`);
        this.candidate = value.candidate.id; this.pipeline = value.pipeline; this.answers = value.answers;
        await this.loadQuestions();
      } else this.imported = undefined;
    });
  }
  async preflight(): Promise<void> {
    await this.action('Checking input hashes, timing, runtime and resources', async () => {
      this.requireSaved(); this.plan = undefined;
      this.plan = await request<RunPlan>('/workflow/preflight', 'POST', { workspace: this.workspace, configuration: this.configuration });
    });
  }
  async launch(): Promise<void> {
    await this.action('Starting approved run', async () => {
      this.requireSaved();
      this.job = await request<Job>('/workflow/runs', 'POST', { plan: this.plan!.id });
      this.plan = undefined; this.poll(); context.log(`Started ${this.job.pipeline} run ${this.job.id.slice(0, 8)}`);
    });
  }
  async cancel(): Promise<void> {
    await this.action('Requesting cancellation', async () => { this.job = await request<Job>(`/workflow/runs/${this.job!.id}/cancel`, 'POST'); this.poll(); });
  }
  async showJob(key: string): Promise<void> {
    await this.action('Loading run', async () => { this.job = await request<Job>(`/workflow/runs/${key}`); if (!terminal.has(this.job.state)) this.poll(); });
  }
  async discard(): Promise<void> {
    await this.action('Discarding staged copy', async () => {
      if (this.imported?.state !== 'attached') { await request(`/workflow/imports/${this.imported!.id}`, 'DELETE'); sessionStorage.removeItem('ace-import'); }
      this.imported = undefined; this.questionnaire = undefined; this.plan = undefined; this.configuration = ''; this.answers = {};
    });
  }
  private requireSaved(): void { if (this.hasUnsaved()) throw new Error('Save or close unsaved parameter editors before setup, preflight or running.'); }
  private poll(): void {
    window.clearTimeout(this.timer);
    if (this.disposed || !this.job || terminal.has(this.job.state)) return;
    this.timer = window.setTimeout(async () => {
      try {
        this.job = await request<Job>(`/workflow/runs/${this.job!.id}`);
        if (terminal.has(this.job.state)) { context.log(`${this.job.pipeline}: ${this.job.state}`); await context.refresh(); this.jobs = await request<Job[]>(`/workflow/runs?workspace=${this.workspace}`); }
      } catch (error) { this.error = String(error); }
      this.changed(); this.poll();
    }, 1000);
  }
  dispose(): void { this.disposed = true; this.uploader.cancel(); window.clearTimeout(this.timer); }
}
