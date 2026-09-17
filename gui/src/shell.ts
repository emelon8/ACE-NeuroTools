import { CommandRegistry } from '@lumino/commands';
import { DockPanel, Menu, MenuBar, SplitPanel, Widget } from '@lumino/widgets';
import { button, el, icon } from './ui';

export class Shell {
  commands = new CommandRegistry();
  dock = new DockPanel();
  sidebar = new Widget();
  output = new Widget();
  horizontal = new SplitPanel({ orientation: 'horizontal', spacing: 3 });
  vertical = new SplitPanel({ orientation: 'vertical', spacing: 3 });
  activity = el('nav', 'activity');
  status = el('footer', 'statusbar');
  title = el('span', 'window-title', 'ACENeuroTools');
  root = el('div', 'workbench');
  menu = new MenuBar();
  constructor() {
    const top = el('header', 'titlebar');
    const mark = el('div', 'app-mark'); mark.append(icon('pulse'));
    top.append(mark);
    this.menu.addClass('menubar'); Widget.attach(this.menu, top);
    top.append(button('Search commands', () => this.commands.execute('palette').then(() => undefined), 'search', 'command-search'));
    top.append(this.title, el('span', 'badge local-label', 'LOCAL'));
    this.activity.setAttribute('aria-label', 'Workbench views');
    this.sidebar.addClass('sidebar'); this.sidebar.node.setAttribute('aria-label', 'Explorer');
    this.output.addClass('output'); this.output.node.setAttribute('aria-label', 'Operation output');
    this.dock.addClass('editor-dock'); this.dock.node.setAttribute('aria-label', 'Editor area');
    this.horizontal.addWidget(this.sidebar); this.horizontal.addWidget(this.dock);
    SplitPanel.setStretch(this.sidebar, 0); SplitPanel.setStretch(this.dock, 1);
    this.horizontal.setRelativeSizes([0.21, 0.79]);
    this.vertical.addWidget(this.horizontal); this.vertical.addWidget(this.output);
    SplitPanel.setStretch(this.horizontal, 1); SplitPanel.setStretch(this.output, 0);
    this.vertical.setRelativeSizes([0.79, 0.21]);
    const body = el('div', 'workbench-body'); const host = el('main', 'workspace-host');
    body.append(this.activity, host); this.root.append(top, body, this.status);
    document.getElementById('app')!.append(this.root);
    Widget.attach(this.vertical, host);
    const resize = () => this.vertical.update();
    new ResizeObserver(resize).observe(host); window.addEventListener('resize', resize);
    this.root.append(el('div', 'notifications')); this.root.lastElementChild!.id = 'notifications';
    document.addEventListener('keydown', event => this.commands.processKeydownEvent(event));
  }
  addMenu(title: string, commands: string[]): void {
    const menu = new Menu({ commands: this.commands }); menu.title.label = title;
    for (const command of commands) menu.addItem({ command });
    this.menu.addMenu(menu);
  }
  open(widget: Widget, split = false): void {
    if (!widget.parent) this.dock.addWidget(widget, split ? { mode: 'split-right' } : undefined);
    this.dock.activateWidget(widget);
  }
  activityButton(label: string, glyph: string, action: () => void): HTMLButtonElement {
    const node = button(label, () => {
      for (const child of this.activity.children) child.classList.remove('selected');
      node.classList.add('selected'); action();
    }, glyph, 'activity-button icon-only');
    this.activity.append(node); return node;
  }
  closeAll(): void { for (const widget of Array.from(this.dock.widgets())) widget.dispose(); }
}
