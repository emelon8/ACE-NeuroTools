import { context } from '../api';
import { button, el, heading, Panel, table, timestamp } from '../ui';
import { WorkflowController } from './controller';
import { RecordingDropReader } from './drop';
import { bytes, terminal } from './types';
import type { Question, SetupResult } from './types';
import './workflow.css';

export class WorkflowPanel extends Panel {
  readonly controller: WorkflowController;
  private ready: Promise<void>;
  private reader = new RecordingDropReader();
  private body = el('div', 'workflow-body');
  private progress = el('progress');
  private progressText = el('span', 'muted');
  constructor(attached: (result: SetupResult) => Promise<void>, hasUnsaved: () => boolean, private readonly openResults: () => void) {
    super('Import & Run', 'run-all'); this.addClass('workflow-panel');
    this.controller = new WorkflowController(attached, hasUnsaved);
    this.node.append(heading('Import & Run', 'Recording → Experiment setup → Preflight → Run'), this.body);
    this.listen(this.controller, 'change', () => this.render());
    this.listen(this.controller, 'progress', () => this.renderProgress());
    this.node.addEventListener('dragover', event => { if (event.dataTransfer?.types.includes('Files')) { event.preventDefault(); event.dataTransfer.dropEffect = 'copy'; } });
    this.node.addEventListener('drop', event => { if (event.dataTransfer?.types.includes('Files')) { event.preventDefault(); event.stopPropagation(); void this.acceptDrop(event.dataTransfer); } });
    this.ready = this.controller.initialize();
  }
  async acceptDrop(data: DataTransfer): Promise<void> {
    try { const files = await this.reader.fromDrop(data); await this.ready; await this.controller.importFiles(files); }
    catch (error) { this.controller.error = String(error); this.controller.changed(); }
  }
  async selectConfiguration(path: string): Promise<void> { await this.ready; await this.controller.openConfiguration(path); }
  private render(): void {
    const c = this.controller;
    this.body.replaceChildren();
    if (c.busy) { const status = el('p', 'workflow-status', c.busy + '…'); status.setAttribute('role', 'status'); this.body.append(status); }
    if (c.error) { const error = el('p', 'workflow-error', c.error); error.setAttribute('role', 'alert'); this.body.append(error); }
    if (!c.imported && !c.plan) this.renderLanding();
    if (c.imported?.state === 'uploading') this.renderDrop();
    if (c.imported?.state === 'inspected' && !c.questionnaire) this.renderCandidateChoice();
    if (c.imported && c.imported.state !== 'uploading' && c.questionnaire) this.renderQuestions();
    if (c.plan) this.renderPlan();
    if (c.job) this.renderJob();
    if (c.jobs.length) {
      this.body.append(el('h2', 'section-title', 'Run history'), table(['Run', 'Operation', 'State', 'Started'], c.jobs.map(job => [
        button(job.id.slice(0, 8), () => c.showJob(job.id), undefined, 'text-button mono'), job.pipeline, job.state, timestamp(job.created),
      ])));
    }
    if (c.busy) this.body.querySelectorAll<HTMLButtonElement | HTMLInputElement | HTMLSelectElement>('button, input, select').forEach(control => { if (!control.hasAttribute('data-cancel-upload')) control.disabled = true; });
  }
  private renderLanding(): void {
    const c = this.controller;
    this.renderDrop();
    if (c.configurations.length) {
      this.body.append(el('h2', 'section-title', 'Saved recording workflows'));
      const choices = el('select'); choices.setAttribute('aria-label', 'Saved workflow');
      choices.append(new Option('Select a recording workflow', ''));
      c.configurations.forEach(item => choices.append(new Option(`${item.label} · ${item.pipeline}`, item.path)));
      choices.value = c.configuration;
      choices.addEventListener('change', () => { void c.openConfiguration(choices.value); });
      this.body.append(choices);
      if (c.configuration) {
        const bar = el('div', 'toolbar workflow-actions');
        bar.append(button('Edit workflow settings', () => c.openConfiguration(c.configuration, true), 'settings-gear'), button('Preflight run', () => c.preflight(), 'check', 'primary'));
        this.body.append(bar);
      }
    }
  }
  private renderDrop(): void {
    const c = this.controller;
    const drop = el('section', 'recording-drop'); drop.setAttribute('aria-label', 'Recording import');
    drop.append(el('h2', '', c.imported ? 'Incomplete recording copy' : 'Drop recording files or a folder here'));
    drop.append(el('p', 'muted', c.imported ? 'Reselect the same files to resume and verify the copied prefix, or discard this staged copy.' : 'Include acquisition metadata and timing files. Files are copied locally; originals stay in place.'));
    drop.append(el('p', 'mono muted workflow-path', `Project: ${context.session.project}`));
    const fileInput = el('input'); fileInput.type = 'file'; fileInput.multiple = true; fileInput.hidden = true; fileInput.setAttribute('aria-label', 'Recording files'); fileInput.dataset.testid = 'recording-files';
    const folderInput = el('input'); folderInput.type = 'file'; folderInput.multiple = true; folderInput.hidden = true; folderInput.setAttribute('webkitdirectory', ''); folderInput.setAttribute('aria-label', 'Recording folder');
    for (const input of [fileInput, folderInput]) input.addEventListener('change', () => {
      if (input.files) { const files = this.reader.fromPicker(input.files); void this.ready.then(() => c.importFiles(files)); }
    });
    const bar = el('div', 'toolbar'); bar.append(button('Choose files', () => fileInput.click(), 'files'), button('Choose folder', () => folderInput.click(), 'folder-opened'), fileInput, folderInput);
    if (c.imported) {
      if (c.busy) { const cancel = button('Pause copy', () => c.uploader.cancel(), 'debug-pause'); cancel.dataset.cancelUpload = ''; bar.append(cancel); }
      else bar.append(button('Discard staged copy', () => c.discard(), 'close'));
    }
    drop.append(bar);
    this.progress = el('progress'); this.progress.max = 1; this.progress.setAttribute('aria-label', 'Recording copy progress');
    this.progressText = el('span', 'muted workflow-progress-label');
    if (c.busy.includes('Copying') || c.imported?.state === 'uploading') drop.append(this.progress, this.progressText);
    this.renderProgress(); this.body.append(drop);
  }
  private renderProgress(): void {
    const p = this.controller.progress;
    this.progress.value = p.total ? p.done / p.total : 0;
    this.progressText.textContent = `${bytes(p.done)} / ${bytes(p.total)} · ${p.file}`;
  }
  private renderCandidateChoice(): void {
    const c = this.controller;
    this.body.append(el('h2', '', 'Choose a recording'), el('p', 'muted', 'Multiple acquisition candidates were found. Select the recording for this workflow; no pairing, merging or alignment is inferred.'));
    const selection = this.select('Detected recording', [{ value: '', label: 'Select a recording…' }, ...c.imported!.candidates!.map(item => ({ value: item.id, label: `${item.label} · ${item.directory}` }))], '');
    selection.input.addEventListener('change', () => { if (selection.input.value) void c.action('Inspecting selected recording', () => c.chooseCandidate(selection.input.value)); });
    this.body.append(selection.label, button('Discard staged copy', () => c.discard(), 'close'));
  }
  private renderQuestions(): void {
    const c = this.controller, imported = c.imported!, selected = c.selected!, questionnaire = c.questionnaire!;
    this.body.append(el('h2', '', c.configuration ? 'Edit recording workflow' : 'Set up this recording'));
    this.body.append(el('p', 'muted', `${imported.files.length} ${imported.files.length === 1 ? 'file' : 'files'} · ${bytes(imported.files.reduce((sum, file) => sum + file.size, 0))} copied and hashed`));
    const form = el('form', 'workflow-form');
    form.addEventListener('submit', event => { event.preventDefault(); void c.setup(); });
    if (!c.configuration) {
      const destination = this.select('Experiment', [{ value: 'new', label: 'Create a new experiment' }, ...context.session.workspaces.map(w => ({ value: w.id, label: `Add recording to ${w.name}` }))], c.destination);
      destination.input.addEventListener('change', () => { c.destination = destination.input.value; c.changed(); });
      form.append(destination.label);
      if (c.destination === 'new') {
        const field = this.field('Experiment name', 'This identifies the unit of work; it does not assign a subject or treatment.');
        const input = el('input'); input.required = true; input.maxLength = 100; input.value = c.name;
        input.addEventListener('input', () => { c.name = input.value; }); field.label.append(input); form.append(field.wrapper);
      }
    }
    const recording = this.select('Detected recording', imported.candidates!.map(item => ({ value: item.id, label: `${item.label} · ${item.directory}` })), c.candidate);
    recording.input.addEventListener('change', () => { void c.action('Inspecting selected recording', () => c.chooseCandidate(recording.input.value)); }); form.append(recording.label);
    form.append(el('p', 'muted', imported.candidates!.length > 1 ? 'Multiple candidates were found. This run uses only the selected recording; no pairing or alignment is inferred.' : 'Review the acquisition evidence before proceeding.'));
    const evidence = el('ul', 'workflow-evidence'); selected.evidence.forEach(line => evidence.append(el('li', '', line))); form.append(evidence);
    const rate = selected.metadata.frame_rate;
    if (rate) form.append(el('p', 'muted', `Acquisition frame rate: ${rate} Hz · source: ${selected.metadata.frame_rate_source}`));
    const columns = selected.metadata.columns as string[] | undefined;
    const timing = columns?.filter(column => column === 'time_s' || column === 'time_ms');
    if (timing?.length === 1) form.append(el('p', 'muted', `Time column: ${timing[0]} · ${timing[0] === 'time_s' ? 'seconds' : 'milliseconds'} (from the column name)`));
    const metadata = el('details'); metadata.append(el('summary', '', 'Acquisition metadata and ordered input files'), el('pre', 'workflow-json', JSON.stringify({ ...selected.metadata, files: selected.files }, null, 2))); form.append(metadata);
    const pipeline = this.select('Operation', selected.pipelines.map(p => ({ value: p.id, label: p.label })), c.pipeline);
    pipeline.input.addEventListener('change', () => { c.pipeline = pipeline.input.value; c.answers = {}; void c.action('Loading operation questions', () => c.loadQuestions()); });
    form.append(pipeline.label, el('p', 'muted', questionnaire.description));
    if (questionnaire.blockers.length) {
      const blockers = el('div', 'workflow-error'); blockers.setAttribute('role', 'alert');
      questionnaire.blockers.forEach(problem => blockers.append(el('p', '', problem))); form.append(blockers);
    }
    questionnaire.questions.forEach(q => form.append(this.question(q)));
    const actions = el('div', 'toolbar workflow-actions');
    const submit = button(c.configuration ? 'Save workflow settings' : c.destination === 'new' ? 'Create experiment' : 'Attach recording', () => { if (form.reportValidity()) return c.setup(); }, 'check', 'primary');
    submit.disabled = questionnaire.blockers.length > 0;
    actions.append(submit, button(c.configuration ? 'Close settings' : 'Discard staged copy', () => c.discard(), 'close'));
    form.append(actions); this.body.append(form);
  }
  private field(title: string, help = '') {
    const wrapper = el('div', 'workflow-field'), label = el('label', 'field'); label.append(el('span', '', title)); wrapper.append(label);
    if (help) { const note = el('span', 'muted workflow-help', help); wrapper.append(note); }
    return { wrapper, label };
  }
  private select(title: string, options: { value: string; label: string }[], value: string) {
    const label = el('label', 'field'); label.append(el('span', '', title)); const input = el('select'); input.setAttribute('aria-label', title);
    options.forEach(option => input.append(new Option(option.label, option.value))); input.value = value; label.append(input);
    return { label, input };
  }
  private question(q: Question): HTMLElement {
    const c = this.controller, field = this.field(q.label, q.help);
    let control: HTMLInputElement | HTMLSelectElement;
    const current = c.answers[q.key] ?? q.default;
    if (q.kind === 'select') {
      control = el('select'); control.append(new Option('Select…', ''));
      q.choices.forEach(choice => (control as HTMLSelectElement).append(new Option(choice.label, choice.value)));
    } else {
      control = el('input'); control.type = ['number', 'integer'].includes(q.kind) ? 'number' : 'text';
      if (control.type === 'number') { control.step = q.kind === 'integer' ? '1' : 'any'; if (q.minimum !== null) control.min = String(q.minimum); if (q.maximum !== null) control.max = String(q.maximum); }
      else control.maxLength = 160;
    }
    control.setAttribute('aria-label', q.label);
    control.value = current == null ? '' : String(current); control.required = q.required;
    control.addEventListener('input', () => { c.answers[q.key] = ['number', 'integer'].includes(q.kind) && control.value !== '' ? Number(control.value) : control.value; c.plan = undefined; });
    field.label.append(control); return field.wrapper;
  }
  private renderPlan(): void {
    const c = this.controller, plan = c.plan!;
    this.body.append(el('h2', '', plan.report.ok ? 'Review run configuration' : 'Preflight needs attention'));
    this.body.append(table(['Run property', 'Approved value'], [
      ['Operation', plan.configuration.pipeline], ['Recording', plan.configuration.candidate.label],
      ['Experiment revision', plan.pre_revision.slice(0, 8)], ['Output directory', plan.output],
      ['Disk required (estimate)', bytes(plan.required_disk_bytes)], ['Disk available', bytes(plan.available_disk_bytes)],
      ['Plan expires', new Date(plan.expires * 1000).toLocaleTimeString()],
    ]));
    if (!plan.report.ok) { const error = el('p', 'workflow-error', plan.report.error || 'Preflight failed.'); error.setAttribute('role', 'alert'); this.body.append(error); }
    (plan.report.warnings || []).forEach(warning => this.body.append(el('p', 'workspace-note', warning)));
    this.body.append(el('h3', '', 'Effective parameters'), el('pre', 'workflow-json', JSON.stringify(plan.configuration.effective, null, 2)));
    const checks = el('details'); checks.append(el('summary', '', 'Validated timing, runtime and resources'), el('pre', 'workflow-json', JSON.stringify(plan.report, null, 2))); this.body.append(checks);
    const actions = el('div', 'toolbar workflow-actions');
    if (plan.report.ok) actions.append(button('Run approved configuration', () => c.launch(), 'play', 'primary'));
    actions.append(button('Revise settings', () => c.openConfiguration(c.configuration, true), 'settings-gear'), button('Repeat preflight', () => c.preflight(), 'refresh'));
    this.body.append(actions);
  }
  private renderJob(): void {
    const c = this.controller, job = c.job!;
    const section = el('section', 'workflow-job'); section.setAttribute('aria-label', 'Run status');
    section.append(el('h2', '', `${job.pipeline} · ${job.state}`), el('p', 'muted', job.detail), el('p', 'mono workflow-path', job.output));
    const log = el('pre', 'workflow-log', job.log || 'Waiting for worker output…'); log.setAttribute('aria-label', 'Run log'); section.append(log);
    const bar = el('div', 'toolbar');
    if (!terminal.has(job.state)) bar.append(button('Cancel run', () => c.cancel(), 'debug-stop'));
    if (job.state === 'succeeded') bar.append(button('Browse run results', this.openResults, 'graph-line'));
    if (terminal.has(job.state)) bar.append(button('Prepare another run', () => { c.job = undefined; return c.openConfiguration(job.configuration_path); }, 'run-all'));
    section.append(bar); this.body.append(section);
  }
  dispose(): void { this.controller.dispose(); super.dispose(); }
}
