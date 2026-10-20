"""Offline Box transfer and local-availability contracts from Comenius review."""

from types import SimpleNamespace as NS

import pytest

from aceneurotools.shared import file_downloader as downloader


def file(name="trace.ncs", identifier="2", size=None):
    return NS(type="file", id=identifier, name=name, size=size)


def client(entries, download=None, listing=None):
    return NS(
        folders=NS(get_folder_items=listing or (lambda *a, **kw: NS(entries=entries, next_marker=None))),
        downloads=NS(
            download_file_to_output_stream=download or (lambda i, output_stream: output_stream.write(b"COMPLETE"))
        ),
    )


def test_interrupted_transfer_never_installs_partial_bytes_and_retry_completes(tmp_path):
    def interrupted(identifier, output_stream):
        output_stream.write(b"PART")
        raise OSError("interrupted")

    assert not downloader.download_file(client([file()], interrupted), "recording", 1, base_file_path=tmp_path)
    destination = tmp_path / "recording"
    assert not (destination / "trace.ncs").exists()
    assert not downloader.verify_path("recording", base_file_path=tmp_path)
    assert downloader.download_file(client([file()]), "recording", 1, base_file_path=tmp_path)
    assert (destination / "trace.ncs").read_bytes() == b"COMPLETE"
    assert sorted(p.name for p in destination.iterdir()) == ["trace.ncs"]


@pytest.mark.parametrize("name", ["child", "Miniscope"])
def test_nested_listing_failure_reaches_caller(tmp_path, name):
    def listing(identifier, **kwargs):
        if identifier == "1":
            return NS(entries=[NS(type="folder", name=name, id="2")], next_marker=None)
        raise OSError("child listing failed")

    assert not downloader.download_file(client([], listing=listing), "recording", 1, base_file_path=tmp_path)
    assert not downloader.verify_path("recording", base_file_path=tmp_path)


def test_marker_pagination_downloads_every_page(tmp_path):
    markers = []

    def listing(identifier, *, usemarker, marker=None, **kwargs):
        assert usemarker is True
        markers.append(marker)
        return NS(
            entries=[file("second.ncs" if marker else "first.ncs")],
            next_marker=None if marker else "page2",
        )

    assert downloader.download_file(client([], listing=listing), "recording", 1, base_file_path=tmp_path)
    assert markers == [None, "page2"]
    assert sorted(p.name for p in (tmp_path / "recording").iterdir()) == ["first.ncs", "second.ncs"]


@pytest.mark.parametrize("name", ["README.txt", "metaData.json", "timeStamps.csv", "trace.ncs.part", "trace.ncs"])
def test_metadata_partial_and_empty_files_are_not_recording_data(tmp_path, name):
    folder = tmp_path / "recording"
    folder.mkdir()
    (folder / name).write_bytes(b"" if name == "trace.ncs" else b"metadata")
    assert not downloader.verify_path("recording", base_file_path=tmp_path)


@pytest.mark.parametrize("size", [4, 8], ids=["truncated", "complete"])
def test_existing_file_size_controls_retry_without_overwriting_complete_files(tmp_path, size):
    folder = tmp_path / "recording"
    folder.mkdir()
    path = folder / "trace.ncs"
    path.write_bytes(b"ORIGINAL"[:size])
    calls = []

    def download(identifier, output_stream):
        calls.append(identifier)
        output_stream.write(b"COMPLETE")

    assert downloader.download_file(client([file(size=8)], download), "recording", 1, base_file_path=tmp_path)
    assert path.read_bytes() == (b"COMPLETE" if size == 4 else b"ORIGINAL")
    assert calls == (["2"] if size == 4 else [])


def test_short_successful_response_does_not_replace_existing_file(tmp_path):
    folder = tmp_path / "recording"
    folder.mkdir()
    path = folder / "trace.ncs"
    path.write_bytes(b"OLD")
    api = client([file(size=8)], lambda identifier, output_stream: output_stream.write(b"SHORT"))
    assert not downloader.download_file(api, "recording", 1, base_file_path=tmp_path)
    assert path.read_bytes() == b"OLD"
    assert not list(folder.glob("*.part"))
    assert not downloader.verify_path("recording", base_file_path=tmp_path)


def test_nested_avi_selection_preserves_metadata_and_requested_movies(tmp_path):
    def listing(identifier, **kwargs):
        if identifier == "1":
            return NS(entries=[NS(type="folder", name="Miniscope", id="9")], next_marker=None)
        return NS(entries=[file("0.avi"), file("1.avi"), file("metaData.json")], next_marker=None)

    assert downloader.download_file(client([], listing=listing), "recording", 1, ["1.avi"], base_file_path=tmp_path)
    assert sorted(p.name for p in (tmp_path / "recording" / "Miniscope").iterdir()) == ["1.avi", "metaData.json"]


@pytest.mark.parametrize("name", ["../outside.ncs", "/outside.ncs", "..\\outside.ncs", ""])
def test_remote_names_cannot_escape_the_destination(tmp_path, name):
    assert not downloader.download_file(client([file(name)]), "recording", 1, base_file_path=tmp_path)
    assert not (tmp_path / "outside.ncs").exists()


def test_repeated_pagination_marker_fails_instead_of_looping(tmp_path):
    calls = []

    def listing(identifier, **kwargs):
        calls.append(kwargs)
        if len(calls) > 3:
            pytest.fail("pagination loop did not stop")
        return NS(entries=[file()], next_marker="same")

    assert not downloader.download_file(client([], listing=listing), "recording", 1, base_file_path=tmp_path)
    assert len(calls) <= 2


@pytest.mark.parametrize("nested", [False, True])
def test_local_avi_is_found_in_supported_flat_or_miniscope_layout(tmp_path, nested):
    directory = tmp_path / "recording" / "Miniscope" if nested else tmp_path / "recording"
    directory.mkdir(parents=True)
    movie = directory / "0.avi"
    movie.write_bytes(b"MOVIE")
    assert downloader.verify_avi("recording", "0.avi", base_file_path=tmp_path)
    movie.write_bytes(b"")
    assert not downloader.verify_avi("recording", "0.avi", base_file_path=tmp_path)


def test_failed_folder_sync_is_retried_even_after_one_recording_file_arrived(tmp_path, monkeypatch):
    csv = tmp_path / "experiments.csv"
    csv.write_text("line number,calcium imaging directory,ephys directory,Box ephys folder ID\n1,,recording,1\n")
    attempts = []

    def download(identifier, output_stream):
        attempts.append(identifier)
        if identifier == "3" and attempts.count("3") == 1:
            output_stream.write(b"PART")
            raise OSError("second file interrupted")
        output_stream.write(b"COMPLETE")

    api = client([file("first.ncs", "2", 8), file("second.ncs", "3", 8)], download)
    monkeypatch.setattr(downloader, "is_box_installed", lambda: True)
    monkeypatch.setattr(downloader, "is_box_configured", lambda: True)
    monkeypatch.setattr(downloader, "make_auth", lambda: api)
    assert not downloader.verify_file_by_line(1, csv, "ephys", base_file_path=tmp_path)
    assert (tmp_path / "recording" / "first.ncs").read_bytes() == b"COMPLETE"
    assert not downloader.verify_path("recording", base_file_path=tmp_path)
    assert downloader.verify_file_by_line(1, csv, "ephys", base_file_path=tmp_path)
    assert attempts == ["2", "3", "3"]
    assert sorted(p.name for p in (tmp_path / "recording").iterdir()) == ["first.ncs", "second.ncs"]


def test_successful_metadata_download_is_not_reported_as_available_recording(tmp_path, monkeypatch):
    csv = tmp_path / "experiments.csv"
    csv.write_text("line number,calcium imaging directory,ephys directory,Box ephys folder ID\n1,,recording,1\n")
    monkeypatch.setattr(downloader, "is_box_installed", lambda: True)
    monkeypatch.setattr(downloader, "is_box_configured", lambda: True)
    monkeypatch.setattr(downloader, "make_auth", lambda: client([file("README.txt")]))
    assert not downloader.verify_file_by_line(1, csv, "ephys", base_file_path=tmp_path)


def test_empty_legacy_file_without_size_metadata_is_retried(tmp_path):
    directory = tmp_path / "recording"
    directory.mkdir()
    (directory / "trace.ncs").touch()
    assert downloader.download_file(client([file()]), "recording", 1, base_file_path=tmp_path)
    assert (directory / "trace.ncs").read_bytes() == b"COMPLETE"


def test_retry_keeps_the_original_avi_selection(tmp_path, monkeypatch):
    csv = tmp_path / "experiments.csv"
    csv.write_text("line number,calcium imaging directory,ephys directory,Box Calcium Folder ID\n1,recording,,1\n")
    attempts = []

    def download(identifier, output_stream):
        attempts.append(identifier)
        if identifier == "4" and attempts.count("4") == 1:
            raise OSError("metadata interrupted")
        output_stream.write(b"COMPLETE")

    api = client([file("0.avi", "2", 8), file("1.avi", "3", 8), file("metaData.json", "4", 8)], download)
    monkeypatch.setattr(downloader, "is_box_installed", lambda: True)
    monkeypatch.setattr(downloader, "is_box_configured", lambda: True)
    monkeypatch.setattr(downloader, "make_auth", lambda: api)
    assert not downloader.verify_file_by_line(1, csv, "miniscope", ["0.avi"], base_file_path=tmp_path)
    assert downloader.verify_file_by_line(1, csv, "miniscope", ["0.avi"], base_file_path=tmp_path)
    assert attempts == ["2", "4", "4"]
    assert not (tmp_path / "recording" / "1.avi").exists()


@pytest.mark.parametrize(
    "name,available",
    [("rhs2116pair-ac_0.raw", True), ("rhs2116pair-dc_0.raw", True), ("rhs2116pair-clock_0.raw", False)],
)
def test_local_rhs_signal_is_distinct_from_clock_metadata(tmp_path, name, available):
    directory = tmp_path / "recording"
    directory.mkdir()
    (directory / name).write_bytes(b"data")
    assert downloader.verify_path("recording", base_file_path=tmp_path) is available
