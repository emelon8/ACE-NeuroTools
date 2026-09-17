import { readFileSync, readdirSync, mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
const root = resolve(import.meta.dirname, '..');
const lock = JSON.parse(readFileSync(resolve(root, 'package-lock.json'), 'utf8'));
let text = 'ACENeuroTools Workbench — bundled third-party notices\n\n';
text += 'Codicons artwork © Microsoft Corporation, licensed CC-BY-4.0; unmodified glyphs.\nhttps://github.com/microsoft/vscode-codicons\nNo endorsement by Microsoft or Project Jupyter is implied.\n\n';
for (const [path, info] of Object.entries(lock.packages)) {
  if (!path || info.dev) continue;
  const directory = resolve(root, path);
  const pkg = JSON.parse(readFileSync(resolve(directory, 'package.json'), 'utf8'));
  text += `\n${'='.repeat(72)}\n${pkg.name} ${pkg.version} — ${pkg.license}\n${typeof pkg.repository === 'object' ? pkg.repository.url : pkg.repository || pkg.homepage || ''}\n\n`;
  const names = readdirSync(directory).filter(name => /^(license|licence|copying|thirdpartynotices)/i.test(name));
  if (names.length) for (const name of names) text += `${name}\n${readFileSync(resolve(directory, name), 'utf8')}\n`;
  else if (pkg.name.startsWith('@lumino/')) text += readFileSync(resolve(root, 'public/licenses/lumino.txt'), 'utf8');
  else throw new Error(`Missing license text for ${pkg.name}`);
}
mkdirSync(resolve(root, 'public'), { recursive: true });
writeFileSync(resolve(root, 'public/THIRD_PARTY_NOTICES.txt'), text);
