# Disposable GUI design study

See the [prototype guide](README.md) for setup, the review walkthrough, supported
interactions, limitations, troubleshooting, and validation evidence.

Question: how can researchers browse projects and operate experiments without an IDE or separate crop/neuron windows?

User direction: stacked project folders → experiments → a complete experiment workspace. Reuse the existing experiment version control backend through plain-language History. Keep scripts unchanged.

Run from the repository root:

```sh
python scripts/preview_guided_gui.py
```

Open http://127.0.0.1:8765/?variant=A. All variants have the same project home; open an experiment to compare tabbed (A), overview (B), and guided (C) layouts with the floating arrows.

Try editing settings, drawing a crop (or entering numeric bounds), excluding/keeping neurons, saving/comparing/restoring a version, and starting a simulated run. Imaging runs pause for review at 60%; apply the neuron selection to continue. Add project/experiment forms also use temporary demo data.

Everything is in memory. No real pipeline, files, scientific images, or EVC storage are connected. Reload resets the demo. This is not the production GUI.

Recommendation: A as the default, with the next useful action called out in Overview. Awaiting user design feedback. Preserve the final decision in `docs/design/guided-experiments-mvp.md`, then delete/replace the prototype rather than shipping it.
