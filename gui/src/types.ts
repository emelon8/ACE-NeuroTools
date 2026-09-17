export interface Workspace { id: string; name: string; path: string }
export interface ParamChange { key: string; old: unknown; new: unknown }
export interface FileDiff { path: string; status: string; param_changes: ParamChange[] }
export interface Status { branch: string; head: string | null; clean: boolean; changes: FileDiff[]; version: string }
export interface WorkspaceState { status: Status; documents: string[] }
export interface Revision { oid: string; tree: string; parents: string[]; author: string; author_time: number; message: string; files: string[] }
export interface Document { path: string; text: string; etag: string; revision: string | null }
export interface JournalEntry { timestamp: number; ref: string; old: string; new: string; op: string; message: string }
export interface Artifact { sha256: string; size: number; relpath: string; created: string; producer?: { pipeline: string; revision: string } }
export interface Run { id: string; artifacts: Artifact[]; error: string | null }
export interface Verification { clean: boolean; verified: string[]; missing: string[]; modified: string[] }
export interface Preview { kind: 'table' | 'text'; columns?: string[]; rows?: string[][]; numeric?: number[][]; truncated?: boolean; text?: string }
export interface Session { version: string; workspaces: Workspace[]; mode: string; author: string | null }
