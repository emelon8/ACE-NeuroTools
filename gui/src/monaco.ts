import 'monaco-editor/features/find/register';
import 'monaco-editor/features/folding/register';
import 'monaco-editor/features/format/register';
import 'monaco-editor/features/contextmenu/register';
import 'monaco-editor/features/hover/register';
import 'monaco-editor/features/suggest/register';
import 'monaco-editor/features/bracketMatching/register';
import 'monaco-editor/features/clipboard/register';
import * as monaco from 'monaco-editor/editor/editor.api';
import { jsonDefaults } from 'monaco-editor/languages/features/json/register';
import EditorWorker from 'monaco-editor/editor/editor.worker?worker';
import JsonWorker from 'monaco-editor/languages/features/json/json.worker?worker';
import { request } from './api';

self.MonacoEnvironment = { getWorker: (_moduleId: string, label: string) => label === 'json' ? new JsonWorker() : new EditorWorker() };
monaco.editor.defineTheme('ace-viridis', {
  base: 'vs-dark', inherit: true,
  rules: [{ token: 'string.key.json', foreground: '80C7C0' }, { token: 'string.value.json', foreground: 'B5D68A' }, { token: 'number', foreground: 'D5DC87' }, { token: 'keyword', foreground: 'A6A0D7' }],
  colors: { 'editor.background': '#1d2026', 'editor.foreground': '#d9dee5', 'editorLineNumber.foreground': '#747c88', 'editorLineNumber.activeForeground': '#c3d6d2', 'editorCursor.foreground': '#63c6b8', 'editor.selectionBackground': '#315354', 'editor.lineHighlightBackground': '#23282f', 'editorIndentGuide.background1': '#303640', 'editorWidget.background': '#252a32', 'focusBorder': '#63c6b8', 'editorGutter.background': '#1d2026' },
});
monaco.editor.setTheme('ace-viridis');
export const options: monaco.editor.IStandaloneEditorConstructionOptions = {
  theme: 'ace-viridis', fontSize: 13, fontFamily: "'SFMono-Regular', Consolas, monospace", lineHeight: 21,
  minimap: { enabled: false }, scrollBeyondLastLine: false, automaticLayout: true,
  padding: { top: 14 }, tabSize: 2, renderWhitespace: 'selection', smoothScrolling: false,
  accessibilitySupport: 'on', fixedOverflowWidgets: true,
};
export async function configureSchemas(): Promise<void> {
  const schemas = await request<Record<string, object>>('/schemas');
  jsonDefaults.setDiagnosticsOptions({ validate: true, enableSchemaRequest: false, schemas: Object.entries(schemas).map(([name, schema]) => ({ uri: `ace://schemas/${name}`, fileMatch: [`**/${name}`], schema })) });
}
export { monaco };
