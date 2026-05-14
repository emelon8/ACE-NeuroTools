#!/usr/bin/env python3
"""
curate_neurons.py
-----------------
Standalone neuron curation tool. Loads a CNMF-E HDF5 file, displays each
neuron's spatial footprint on a background image (sum of all footprints),
and lets you accept/reject each one. Saves the kept neurons to a new HDF5
and/or an NPZ with the trimmed C matrix.

Usage:
    python curate_neurons.py /path/to/please_work.hdf5

Output (written next to the input file):
    estimates_curated.hdf5   — CNMF-E object with only kept components
    C_curated.npz            — { C, A_dense, neuron_ids } for kept neurons
"""

import sys
import os
import argparse
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.widgets import Button
from pathlib import Path

# ── CaImAn ────────────────────────────────────────────────────────────────────
import caiman as cm
import caiman.source_extraction.cnmf as cnmf_mod

# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Curate CNMF-E neurons by spatial footprint.")
    p.add_argument("hdf5", help="Path to CNMF-E .hdf5 estimates file")
    p.add_argument("--fr", type=float, default=None,
                   help="Frame rate (Hz). Pulled from HDF5 params if omitted.")
    p.add_argument("--out-dir", default=None,
                   help="Output directory. Defaults to same folder as hdf5.")
    p.add_argument("--window", type=float, default=30.0,
                   help="Seconds of trace to show in the zoomed panel (default: 30).")
    return p.parse_args()

# ── Load ──────────────────────────────────────────────────────────────────────

def load_cnmfe(hdf5_path: str):
    print(f"Loading CNMF-E estimates from {hdf5_path} ...")
    obj = cnmf_mod.cnmf.load_CNMF(hdf5_path)
    return obj

# ── Background image ──────────────────────────────────────────────────────────

def make_background(A, dims):
    """Sum of all spatial footprints → proxy background image."""
    bg = np.array(A.sum(axis=1)).reshape(dims, order='F')
    bg = bg / (bg.max() + 1e-9)
    return bg

def footprint_image(a_col, dims):
    """Single neuron footprint as 2-D array, normalised."""
    img = np.array(a_col.todense()).flatten().reshape(dims, order='F')
    img = img / (img.max() + 1e-9)
    return img

# ── GUI ───────────────────────────────────────────────────────────────────────

KEEP_COLOR   = "#00e676"   # bright green
REJECT_COLOR = "#ff1744"   # vivid red
SKIP_COLOR   = "#78909c"   # grey
BG_COLOR     = "#0d1117"
TEXT_COLOR   = "#e6edf3"

class NeuronCurator:
    def __init__(self, obj, dims, fr, window_s=30.0):
        self.obj      = obj
        self.dims     = dims
        self.fr       = fr
        self.window_s = window_s
        self.A        = obj.estimates.A          # (pixels, n_neurons) sparse
        self.C        = obj.estimates.C          # (n_neurons, T)
        self.n        = self.A.shape[1]
        self.bg       = make_background(self.A, dims)

        # decision array: None=undecided, True=keep, False=reject
        self.decisions = [None] * self.n
        self.idx = 0

        self._build_figure()
        self._draw()

    # ── Figure layout ─────────────────────────────────────────────────────────

    def _build_figure(self):
        matplotlib.rcParams.update({
            'figure.facecolor':  BG_COLOR,
            'axes.facecolor':    BG_COLOR,
            'axes.edgecolor':    '#30363d',
            'axes.labelcolor':   TEXT_COLOR,
            'xtick.color':       TEXT_COLOR,
            'ytick.color':       TEXT_COLOR,
            'text.color':        TEXT_COLOR,
            'font.family':       'monospace',
        })

        self.fig = plt.figure(figsize=(16, 9))
        self.fig.patch.set_facecolor(BG_COLOR)
        self.fig.suptitle("", fontsize=13, color=TEXT_COLOR, fontfamily='monospace')

        gs = gridspec.GridSpec(
            2, 2,
            figure=self.fig,
            left=0.05, right=0.95,
            top=0.88, bottom=0.12,
            wspace=0.35, hspace=0.4,
        )

        self.ax_bg       = self.fig.add_subplot(gs[0, 0])   # all footprints
        self.ax_fp       = self.fig.add_subplot(gs[0, 1])   # this neuron
        self.ax_trace    = self.fig.add_subplot(gs[1, :])   # Ca trace

        for ax in [self.ax_bg, self.ax_fp]:
            ax.set_xticks([]); ax.set_yticks([])

        # ── Buttons ──────────────────────────────────────────────────────────
        btn_y = 0.02
        btn_h = 0.07

        ax_keep   = self.fig.add_axes([0.35, btn_y, 0.12, btn_h])
        ax_reject = self.fig.add_axes([0.50, btn_y, 0.12, btn_h])
        ax_prev   = self.fig.add_axes([0.20, btn_y, 0.10, btn_h])
        ax_next   = self.fig.add_axes([0.65, btn_y, 0.10, btn_h])
        ax_done   = self.fig.add_axes([0.78, btn_y, 0.12, btn_h])

        def _btn(ax, label, color, hover):
            b = Button(ax, label,
                       color=color, hovercolor=hover)
            b.label.set_fontfamily('monospace')
            b.label.set_fontsize(11)
            b.label.set_color('white')
            return b

        self.btn_keep   = _btn(ax_keep,   "✓  KEEP",   "#1a7f37", "#2ea043")
        self.btn_reject = _btn(ax_reject, "✗  REJECT", "#8b1a1a", "#cf2222")
        self.btn_prev   = _btn(ax_prev,   "◀  PREV",   "#21262d", "#30363d")
        self.btn_next   = _btn(ax_next,   "NEXT  ▶",   "#21262d", "#30363d")
        self.btn_done   = _btn(ax_done,   "DONE",      "#1f3a6e", "#2f5ab8")

        self.btn_keep.on_clicked(self._on_keep)
        self.btn_reject.on_clicked(self._on_reject)
        self.btn_prev.on_clicked(self._on_prev)
        self.btn_next.on_clicked(self._on_next)
        self.btn_done.on_clicked(self._on_done)

        # keyboard shortcuts
        self.fig.canvas.mpl_connect('key_press_event', self._on_key)

        # progress bar axes
        self.ax_prog = self.fig.add_axes([0.05, 0.945, 0.90, 0.02])
        self.ax_prog.set_xlim(0, self.n)
        self.ax_prog.set_ylim(0, 1)
        self.ax_prog.set_xticks([]); self.ax_prog.set_yticks([])
        self.ax_prog.set_facecolor('#21262d')

    # ── Draw current neuron ───────────────────────────────────────────────────

    def _draw(self):
        i   = self.idx
        fp  = footprint_image(self.A[:, i], self.dims)
        dec = self.decisions[i]

        # title
        status = {None: "?  undecided", True: "✓  kept", False: "✗  rejected"}[dec]
        color  = {None: TEXT_COLOR, True: KEEP_COLOR, False: REJECT_COLOR}[dec]
        self.fig.suptitle(
            f"Neuron  {i+1} / {self.n}     [{status}]     "
            f"[K] keep   [R] reject   [← →] navigate",
            fontsize=12, color=color,
        )

        # background (all footprints)
        self.ax_bg.clear()
        self.ax_bg.imshow(self.bg, cmap='inferno', vmin=0, vmax=1, aspect='auto')
        # mark centroid
        cy, cx = np.unravel_index(fp.argmax(), self.dims)
        self.ax_bg.plot(cx, cy, 'o', color=color, ms=6, mew=1.5,
                        markerfacecolor='none')
        self.ax_bg.set_title("All footprints  (centroid marked)", fontsize=9)
        self.ax_bg.set_xticks([]); self.ax_bg.set_yticks([])

        # individual footprint
        self.ax_fp.clear()
        self.ax_fp.imshow(fp, cmap='hot', vmin=0, vmax=1, aspect='auto')
        self.ax_fp.set_title(f"Neuron {i+1} footprint", fontsize=9)
        self.ax_fp.set_xticks([]); self.ax_fp.set_yticks([])


        # ── Fluorescence trace — raw C row, zoomed to window around peak ─────
        self.ax_trace.clear()
        if self.C is not None and i < self.C.shape[0]:
            trace = self.C[i]
            T     = trace.shape[0]
            t     = np.arange(T) / self.fr

            half    = self.window_s / 2.0
            peak_fr = int(np.argmax(trace))    # frame index of the peak
            peak_s  = peak_fr / self.fr

            t_start = max(0.0,   peak_s - half)
            t_end   = min(t[-1], peak_s + half)

            # if the window clips an edge, extend the opposite side
            if (t_end - t_start) < self.window_s:
                if t_start == 0.0:
                    t_end   = min(t[-1], self.window_s)
                else:
                    t_start = max(0.0, t_end - self.window_s)

            f_start = int(t_start * self.fr)
            f_end   = min(T, int(t_end * self.fr) + 1)

            self.ax_trace.plot(t[f_start:f_end], trace[f_start:f_end],
                               color='#58a6ff', lw=0.9, alpha=0.9)
            self.ax_trace.set_xlim(t_start, t_end)
            self.ax_trace.set_xlabel("Time (s)", fontsize=9)
            self.ax_trace.set_ylabel("Fluorescence (a.u.)", fontsize=9)

        self.ax_trace.set_title(
            f"Fluorescence trace  ({self.window_s:.0f} s window centred on peak)",
            fontsize=9,
        )
        self.ax_trace.set_facecolor(BG_COLOR)

        # progress bar
        self.ax_prog.clear()
        self.ax_prog.set_xlim(0, self.n)
        self.ax_prog.set_ylim(0, 1)
        self.ax_prog.set_xticks([]); self.ax_prog.set_yticks([])
        for j, d in enumerate(self.decisions):
            c = {None: '#30363d', True: KEEP_COLOR, False: REJECT_COLOR}[d]
            self.ax_prog.bar(j, 1, width=1, color=c, linewidth=0)
        # current position marker
        self.ax_prog.axvline(i + 0.5, color='white', lw=1.5, alpha=0.8)

        n_keep   = sum(1 for d in self.decisions if d is True)
        n_reject = sum(1 for d in self.decisions if d is False)
        n_left   = sum(1 for d in self.decisions if d is None)
        self.ax_prog.set_xlabel(
            f"  ✓ {n_keep}  kept      ✗ {n_reject}  rejected      ? {n_left}  undecided",
            fontsize=8, color=TEXT_COLOR, labelpad=2,
        )

        self.fig.canvas.draw_idle()

    # ── Button / key callbacks ────────────────────────────────────────────────

    def _on_keep(self, _=None):
        self.decisions[self.idx] = True
        self._advance()

    def _on_reject(self, _=None):
        self.decisions[self.idx] = False
        self._advance()

    def _advance(self):
        if self.idx < self.n - 1:
            self.idx += 1
        self._draw()

    def _on_prev(self, _=None):
        if self.idx > 0:
            self.idx -= 1
        self._draw()

    def _on_next(self, _=None):
        if self.idx < self.n - 1:
            self.idx += 1
        self._draw()

    def _on_key(self, event):
        if event.key in ('k', 'K'):
            self._on_keep()
        elif event.key in ('r', 'R'):
            self._on_reject()
        elif event.key in ('left',):
            self._on_prev()
        elif event.key in ('right',):
            self._on_next()
        elif event.key in ('d', 'D', 'enter'):
            self._on_done()

    def _on_done(self, _=None):
        undecided = [i for i, d in enumerate(self.decisions) if d is None]
        if undecided:
            self._show_confirm_dialog(undecided)
        else:
            plt.close(self.fig)

    def _show_confirm_dialog(self, undecided):
        """Show in-GUI buttons asking what to do with undecided neurons."""
        n = len(undecided)
        self.fig.suptitle(
            f"  {n} neurons still undecided — keep them all or reject them all?",
            fontsize=13, color="#f0c040",
        )

        ax_keep_all   = self.fig.add_axes([0.30, 0.44, 0.18, 0.08])
        ax_reject_all = self.fig.add_axes([0.52, 0.44, 0.18, 0.08])

        def _btn(ax, label, color, hover):
            b = Button(ax, label, color=color, hovercolor=hover)
            b.label.set_fontfamily('monospace')
            b.label.set_fontsize(11)
            b.label.set_color('white')
            return b

        btn_keep_all   = _btn(ax_keep_all,   f"✓  Keep all {n}",   "#1a7f37", "#2ea043")
        btn_reject_all = _btn(ax_reject_all, f"✗  Reject all {n}", "#8b1a1a", "#cf2222")

        def _keep_all(_=None):
            for i in undecided:
                self.decisions[i] = True
            plt.close(self.fig)

        def _reject_all(_=None):
            for i in undecided:
                self.decisions[i] = False
            plt.close(self.fig)

        btn_keep_all.on_clicked(_keep_all)
        btn_reject_all.on_clicked(_reject_all)

        # Keep references so they aren't garbage collected
        self._confirm_btns = [btn_keep_all, btn_reject_all]
        self.fig.canvas.draw_idle()

    def run(self):
        plt.show(block=True)
        return [i for i, d in enumerate(self.decisions) if d is True]

# ── Save ──────────────────────────────────────────────────────────────────────

def save_results(obj, kept_ids: list, out_dir: str, fr: float):
    kept = sorted(kept_ids)
    if not kept:
        print("No neurons kept — nothing saved.")
        return

    print(f"\nKeeping {len(kept)} / {obj.estimates.A.shape[1]} neurons: {kept}")

    # ── Trim the estimates object in-place ────────────────────────────────────
    obj.estimates.select_components(idx_components=kept)

    # ── Save curated HDF5 ─────────────────────────────────────────────────────
    hdf5_out = os.path.join(out_dir, "estimates_curated.hdf5")
    print(f"Saving curated CNMF-E object → {hdf5_out}")
    obj.save(hdf5_out)

    # ── Save lightweight NPZ ──────────────────────────────────────────────────
    npz_out = os.path.join(out_dir, "C_curated.npz")
    payload = {
        "C":          obj.estimates.C,
        "neuron_ids": np.array(kept, dtype=int),
        "fr":         float(fr),
    }
    # A as dense (can be large — skip if too big)
    try:
        A_dense = np.array(obj.estimates.A.todense())
        payload["A_dense"] = A_dense
    except MemoryError:
        print("Warning: A matrix too large to densify — skipping A_dense in NPZ.")

    np.savez_compressed(npz_out, **payload)
    print(f"Saved trimmed C matrix → {npz_out}")
    print(f"  Shape: {obj.estimates.C.shape}  (neurons × time)")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    hdf5_path = args.hdf5
    out_dir   = args.out_dir or str(Path(hdf5_path).parent)
    os.makedirs(out_dir, exist_ok=True)

    obj = load_cnmfe(hdf5_path)

    dims = tuple(obj.dims)
    fr   = args.fr or float(obj.params.get("data", "fr"))
    n    = obj.estimates.A.shape[1]
    print(f"  dims={dims}  fr={fr} Hz  n_neurons={n}")

    # try a non-interactive backend fallback
    for backend in ['Qt5Agg', 'MacOSX', 'TkAgg', 'Agg']:
        try:
            matplotlib.use(backend)
            break
        except Exception:
            continue

    curator = NeuronCurator(obj, dims, fr, window_s=args.window)
    kept    = curator.run()

    if not kept:
        print("No neurons were kept. Exiting without saving.")
        return

    save_results(obj, kept, out_dir, fr)
    print("\nDone.")

if __name__ == "__main__":
    main()
