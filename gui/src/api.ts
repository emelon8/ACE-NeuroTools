import type { Session, Workspace, WorkspaceState } from './types';

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

const fragment = new URLSearchParams(location.hash.slice(1));
const incoming = fragment.get('token');
if (incoming) {
  sessionStorage.setItem('ace-session', incoming);
  history.replaceState(null, '', location.pathname + location.search);
}

export async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method, headers: { 'X-Ace-Token': sessionStorage.getItem('ace-session') ?? '', 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new ApiError(response.status, typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
  return data as T;
}

export class Context extends EventTarget {
  session!: Session;
  workspace!: Workspace;
  state!: WorkspaceState;
  private generation = 0;
  path(suffix: string): string { return `/workspaces/${encodeURIComponent(this.workspace.id)}${suffix}`; }
  async refresh(): Promise<void> {
    const generation = ++this.generation;
    const workspace = this.workspace.id;
    const state = await request<WorkspaceState>(this.path('/state'));
    if (generation !== this.generation || workspace !== this.workspace.id) return;
    this.state = state;
    this.dispatchEvent(new Event('change'));
  }
  log(message: string, error = false): void {
    this.dispatchEvent(new CustomEvent('log', { detail: { message, error, time: new Date() } }));
  }
}
export const context = new Context();
