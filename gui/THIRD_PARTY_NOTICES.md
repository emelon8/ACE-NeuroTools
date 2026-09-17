# Third-party components

ACENeuroTools Workbench is distributed under the repository's GPL-3.0-or-later
license. It uses the following open-source foundations:

| Component | Use | Upstream / license |
| --- | --- | --- |
| Lumino 2.x | JupyterLab docking, split panels, widgets, menus, command palette | [Project Jupyter](https://github.com/jupyterlab/lumino), BSD-3-Clause; includes PhosphorJS notices |
| Monaco Editor 0.56 | VS Code's editor, JSON workers, side-by-side diffs | [Microsoft](https://github.com/microsoft/monaco-editor), MIT; embedded dependency notices included |
| VS Code Codicons 0.0.36 | Unmodified IDE icon glyphs | [Microsoft](https://github.com/microsoft/vscode-codicons), CC-BY-4.0 artwork; MIT supporting code |
| DOMPurify 3.4.15 | Monaco's sanitized markdown rendering | [Cure53](https://github.com/cure53/DOMPurify), Apache-2.0 OR MPL-2.0 |
| Marked 14 | Monaco's markdown support | [Marked](https://github.com/markedjs/marked), MIT |

Codicons artwork © Microsoft Corporation; used without glyph modification.
See the [CC-BY-4.0 license](https://creativecommons.org/licenses/by/4.0/).
The interface changes surrounding colors and placement. No Microsoft or
Project Jupyter endorsement is implied. No Microsoft branding assets or
proprietary VS Code application binaries are redistributed.

`npm run build` generates the complete versioned notices and license texts at
[`public/THIRD_PARTY_NOTICES.txt`](public/THIRD_PARTY_NOTICES.txt), copied into
`dist/THIRD_PARTY_NOTICES.txt`. The generator includes all locked production
packages and Monaco's bundled ThirdPartyNotices. Lumino's monorepo license is
vendored at `public/licenses/lumino.txt` because its npm leaf packages omit it.
The About view links the notices, available locally without network access.

Python service dependencies retain their installed wheel/package license
metadata. The editable source installation does not bundle Python dependencies
or third-party native binaries into an application installer.
