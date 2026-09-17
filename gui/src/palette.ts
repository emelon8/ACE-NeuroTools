import { CommandPalette, Widget } from '@lumino/widgets';
import type { Shell } from './shell';
import { el } from './ui';

export function installPalette(shell: Shell): () => void {
  const overlay = el('div', 'palette-overlay'); overlay.hidden = true;
  overlay.setAttribute('role', 'dialog'); overlay.setAttribute('aria-label', 'Command palette'); overlay.setAttribute('aria-modal', 'true');
  const palette = new CommandPalette({ commands: shell.commands });
  palette.inputNode.placeholder = 'Type a command…'; palette.inputNode.setAttribute('aria-label', 'Find command');
  document.body.append(overlay); Widget.attach(palette, overlay);
  let previous: HTMLElement | null = null;
  const close = () => { overlay.hidden = true; previous?.focus(); };
  overlay.addEventListener('mousedown', event => { if (event.target === overlay) close(); });
  overlay.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); close(); }
    if (event.key === 'Tab') { event.preventDefault(); palette.inputNode.focus(); }
  });
  shell.commands.commandExecuted.connect((_sender, args) => { if (args.id !== 'palette' && !overlay.hidden) close(); });
  return () => {
    previous = document.activeElement as HTMLElement;
    palette.clearItems();
    for (const command of shell.commands.listCommands()) if (command !== 'palette') palette.addItem({ command, category: 'Workbench' });
    palette.inputNode.value = ''; overlay.hidden = false; palette.update(); palette.activate(); palette.inputNode.focus();
  };
}
