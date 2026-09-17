const NS = 'http://www.w3.org/2000/svg';
const COLORS = ['#5ec962', '#35b5ac', '#a1a6dc', '#fde725', '#678fcc'];
export function tracePlot(columns: string[], rows: number[][]): SVGSVGElement {
  const svg = document.createElementNS(NS, 'svg'); svg.setAttribute('viewBox', '0 0 960 260');
  svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', `Artifact preview: ${columns.slice(1).join(', ')} against ${columns[0]}`);
  const add = (tag: string, attributes: Record<string, string>, text = '') => {
    const node = document.createElementNS(NS, tag); Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value)); node.textContent = text; svg.append(node); return node;
  };
  const count = Math.min(columns.length - 1, 5);
  const valid = rows.filter(row => row.length >= count + 1 && row.every(Number.isFinite));
  if (!valid.length || count < 1) return svg;
  const minX = Math.min(...valid.map(r => r[0])), maxX = Math.max(...valid.map(r => r[0]));
  const values = valid.flatMap(r => r.slice(1, count + 1));
  const minY = Math.min(...values), maxY = Math.max(...values);
  const x = (value: number) => 60 + (value - minX) / (maxX - minX || 1) * 870;
  const y = (value: number) => 212 - (value - minY) / (maxY - minY || 1) * 164;
  for (let i = 0; i <= 4; i++) {
    const yv = minY + (maxY - minY) * i / 4, xv = minX + (maxX - minX) * i / 4;
    add('line', { x1: '60', x2: '930', y1: String(y(yv)), y2: String(y(yv)), stroke: '#343a43', 'stroke-width': '.6' });
    add('text', { x: '48', y: String(y(yv) + 4), fill: '#a2abb8', 'text-anchor': 'end', 'font-size': '11' }, yv.toFixed(2));
    add('text', { x: String(x(xv)), y: '231', fill: '#a2abb8', 'text-anchor': 'middle', 'font-size': '11' }, xv.toFixed(1));
  }
  for (let index = 1; index <= count; index++) {
    const path = valid.map((row, i) => `${i ? 'L' : 'M'}${x(row[0]).toFixed(2)},${y(row[index]).toFixed(2)}`).join(' ');
    add('path', { d: path, fill: 'none', stroke: COLORS[index - 1], 'stroke-width': '1.6' });
    add('text', { x: String(60 + (index - 1) * 155), y: '22', fill: COLORS[index - 1], 'font-size': '11' }, columns[index]);
  }
  add('text', { x: '495', y: '253', fill: '#a2abb8', 'text-anchor': 'middle', 'font-size': '11' }, columns[0]);
  return svg;
}
