"""Preserve scientific filtering semantics while suppressing interactive steps."""

from types import SimpleNamespace

import numpy as np
import pytest
from gui.run_specs import effective_parameters

from aceneurotools.shared.cli_utils import apply_headless_policy


def test_gui_preserves_cli_inline_default_without_inventing_a_policy_override():
    params, sources = effective_parameters("miniscope", {})
    assert params["inline"] is True and sources["inline"] == "CLI default"
    policy = apply_headless_policy(pipeline_name="miniscope", run_params={"headless": True})
    assert "inline" not in policy
    assert policy["plot_params"] is False and policy["remove_components_with_gui"] is False


@pytest.mark.parametrize("inline", [True, False])
def test_gui_and_cli_headless_policy_preserve_inline(inline):
    params, sources = effective_parameters("miniscope", {"inline": str(inline)})
    assert params["inline"] is inline and sources["inline"] == "Saved CSV"
    assert params["remove_components_with_gui"] is False
    for name in ["miniscope", "multimodal"]:
        params = apply_headless_policy(pipeline_name=name, run_params={"headless": True, "inline": inline})
        assert params["inline"] is inline
        assert params["inspect_motion_correction"] is False


@pytest.mark.parametrize("inline", [True, False])
def test_real_postprocessing_matches_interactive_pipeline_when_headless(tmp_path, monkeypatch, inline):
    from aceneurotools.pipelines import miniscope
    from aceneurotools.shared import plotting

    t = np.arange(600) / 30
    raw = np.sin(2 * np.pi * 0.5 * t) + 0.5 * np.sin(2 * np.pi * 5 * t)
    managers = []

    def create(**kwargs):
        dm = SimpleNamespace(
            movie=np.broadcast_to(raw[:, None, None], (600, 4, 4)).copy(),
            fr=30.0,
            dview=None,
            coords=None,
            projections=None,
            CNMFE_obj=SimpleNamespace(estimates=SimpleNamespace(C=np.zeros((1, 600)))),
            ca_events_idx=None,
            PSD_spect=None,
            t_spect=None,
            freqs_spect=None,
            p_spect=None,
            miniscope_phases=None,
            filter_object=None,
        )
        managers.append(dm)
        return dm

    class Preprocessor:
        def __init__(self, dm):
            self.dm, self.result = dm, None

        def preprocess_calcium_movie(self, *args, **kwargs):
            return self.dm

    class Processor(Preprocessor):
        def process_calcium_movie(self, *args, **kwargs):
            assert args[3] is False and args[4] is False
            return self.dm

    monkeypatch.setattr(miniscope.MiniscopeDataManager, "create", create)
    monkeypatch.setattr(miniscope, "MiniscopePreprocessor", Preprocessor)
    monkeypatch.setattr(miniscope, "MiniscopeProcessor", Processor)
    monkeypatch.setattr(plotting, "set_backend", lambda **kwargs: None)
    for headless in [False, True]:
        pipeline = miniscope.MiniscopePipeline()
        pipeline.run(
            line_num=1,
            project_path=tmp_path,
            data_path=tmp_path,
            crop_coords=[0, 0, 4, 4],
            crop=False,
            inline=inline,
            headless=headless,
            inspect_motion_correction=False,
            plot_params=False,
            remove_components_with_gui=False,
            find_calcium_events=False,
            compute_miniscope_spectrogram=False,
            compute_miniscope_phase=True,
        )
    interactive, headless = managers
    np.testing.assert_allclose(headless.projections.time, interactive.projections.time)
    np.testing.assert_allclose(headless.filter_object.filtered_data, interactive.filter_object.filtered_data)
    np.testing.assert_allclose(headless.miniscope_phases, interactive.miniscope_phases)
    expected = headless.filter_object.filtered_data if inline else raw
    np.testing.assert_allclose(headless.projections.time, expected)
