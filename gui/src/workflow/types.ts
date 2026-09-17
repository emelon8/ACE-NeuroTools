import type { Workspace } from '../types';

export interface DroppedFile { path: string; file: File }
export interface InputFile { path: string; size: number; received: number; sha256?: string }
export interface Operation { id: string; label: string; description: string; scientific: boolean }
export interface Candidate { id: string; format: string; label: string; directory: string; files: string[]; evidence: string[]; blockers: string[]; metadata: Record<string, unknown>; pipelines: Operation[] }
export interface ImportSession { id: string; state: 'uploading' | 'inspected' | 'attached'; files: InputFile[]; candidates?: Candidate[]; workspace?: Workspace; configuration?: string }
export interface Question { key: string; label: string; kind: string; help: string; default: unknown; choices: { value: string; label: string }[]; minimum: number | null; maximum: number | null; required: boolean }
export interface Questionnaire { questions: Question[]; known: Record<string, unknown>; blockers: string[]; description: string }
export interface Configuration { id: string; candidate: Omit<Candidate, 'pipelines'>; pipeline: string; answers: Record<string, unknown>; effective: Record<string, unknown> }
export interface ConfigurationItem { path: string; pipeline: string; label: string }
export interface SetupResult { workspace: Workspace; configuration: string; revision: string }
export interface RunPlan { id: string; workspace: string; configuration_path: string; configuration: Configuration; report: { ok: boolean; error?: string; warnings?: string[]; environment?: Record<string, unknown>; [key: string]: unknown }; output: string; expires: number; required_disk_bytes: number; available_disk_bytes: number; pre_revision: string }
export interface Job { id: string; workspace: string; pipeline: string; configuration_path: string; state: string; created: number; finished: number | null; detail: string; output: string; pre_revision: string; post_revision: string | null; log?: string }
export const terminal = new Set(['succeeded', 'failed', 'cancelled', 'interrupted']);
export function bytes(value: number): string { if (value < 1024) return `${value} B`; const power = Math.min(3, Math.floor(Math.log(value) / Math.log(1024))); return `${(value / 1024 ** power).toFixed(1)} ${['B', 'KiB', 'MiB', 'GiB'][power]}`; }
