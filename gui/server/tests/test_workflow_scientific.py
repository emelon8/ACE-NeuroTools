"""Opt-in real scientific runtime smoke tests, always using generated data."""

import csv
import json
import os
import struct
import subprocess
import time
from pathlib import Path

import pytest
from test_workflow import preflight, upload

RUNTIME = os.environ.get("ACE_TEST_SCIENTIFIC_PYTHON")
pytestmark = pytest.mark.skipif(
    not RUNTIME, reason="Set ACE_TEST_SCIENTIFIC_PYTHON to a CaImAn/Neo Python for real generated-data runs"
)


def execute(service, files, pipeline, answers, name):
    client, _, registry, _ = service
    registry.runner_python = RUNTIME
    key, info = upload(client, files)
    candidate = next(c for c in info["candidates"] if any(p["id"] == pipeline for p in c["pipelines"]))
    response = client.post(
        f"/api/workflow/imports/{key}/setup",
        json={
            "candidate": candidate["id"],
            "pipeline": pipeline,
            "answers": answers,
            "destination": "new",
            "name": name,
        },
    )
    assert response.status_code == 200, response.text
    setup = response.json()
    plan = preflight(client, setup)
    assert plan["report"]["ok"], plan["report"]
    response = client.post("/api/workflow/runs", json={"plan": plan["id"]})
    assert response.status_code == 200, response.text
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        job = client.get(f"/api/workflow/runs/{plan['id']}").json()
        if job["state"] in {"succeeded", "failed", "cancelled", "interrupted"}:
            break
        time.sleep(0.5)
    assert job["state"] == "succeeded", job
    verify = client.post(f"/api/workspaces/{setup['workspace']['id']}/results/{plan['id']}/verify")
    assert verify.json()["clean"], verify.text
    return Path(job["output"])


def test_real_rhs_reader_preserves_calibrated_samples(service, tmp_path):
    script = tmp_path / "generate.py"
    script.write_text("""import numpy as np
from pathlib import Path
root = Path(__file__).parent
samples = np.full((128, 32), 32768, dtype='<u2')
samples[:, 0] += np.arange(128, dtype=np.uint16)
samples.tofile(root / 'rhs2116pair-ac_0.raw')
np.full((128,32),512,dtype='<u2').tofile(root / 'rhs2116pair-dc_0.raw')
(np.arange(128,dtype=np.uint64)*8333).astype('<u8').tofile(root / 'rhs2116pair-clock_0.raw')
""")
    subprocess.run([RUNTIME, str(script)], check=True)
    files = {p.name: p.read_bytes() for p in tmp_path.glob("*.raw")}
    files["start-time_0.csv"] = b"2026-09-17T00:00:00,250000000,32,32\n"
    output = execute(service, files, "ephys-export", {"channel": "RHS2116_AC_0"}, "RHS generated fixture")
    with (output / "channel.csv").open() as stream:
        rows = list(csv.reader(stream))
    assert len(rows) == 129
    assert float(rows[1][1]) == pytest.approx(0, abs=0.001)
    assert float(rows[-1][1]) == pytest.approx(127 * 0.195, abs=0.002)
    assert float(rows[-1][0]) == pytest.approx(127 * 8333 / 250000000)
    assert json.loads((output / "channel-metadata.json").read_text())["signal_unit"] == "uV"


@pytest.mark.parametrize("acquisition", ["ucla", "onix"])
def test_real_cnmfe_extracts_generated_calcium_movie(service, tmp_path, acquisition):
    script = tmp_path / "generate.py"
    script.write_text("""import numpy as np, cv2
from pathlib import Path
root = Path(__file__).parent
rng = np.random.default_rng(421)
y,x=np.mgrid[:96,:96]
spots=[np.exp(-((x-cx)**2+(y-cy)**2)/(2*3**2)) for cx,cy in [(24,24),(65,30),(45,67)]]
writer=cv2.VideoWriter(str(root/'0.avi'),cv2.VideoWriter_fourcc(*'MJPG'),20,(96,96),False)
assert writer.isOpened()
for frame in range(160):
 movie=35+rng.normal(0,1,(96,96))
 for i,spot in enumerate(spots):
  amplitude=sum(65*np.exp(-(frame-peak)/8) for peak in (20+i*9,65+i*12,120+i*7) if frame>=peak)
  movie+=amplitude*spot
 writer.write(np.clip(movie,0,255).astype('uint8'))
writer.release()
""")
    subprocess.run([RUNTIME, str(script)], check=True)
    files = {
        "0.avi": (tmp_path / "0.avi").read_bytes(),
        "metaData.json": b'{"frameRate":20,"deviceType":"Miniscope_V4"}',
        "timeStamps.csv": (
            "Frame Number,Time Stamp (ms),Buffer Index\n" + "".join(f"{i},{i * 50},0\n" for i in range(160))
        ).encode(),
    }
    if acquisition == "onix":
        files = {
            "0.avi": files["0.avi"],
            "start-time_0_miniscope.csv": b"2026-09-17T00:00:00,250000000,32,32\n",
            "ucla-miniscope-v4-clock_0.raw": b"".join(struct.pack("<Q", i * 12500000) for i in range(160)),
        }
    output = execute(
        service,
        files,
        "cnmfe",
        {"decay_time": 0.4, "cell_radius": 3, "min_corr": 0.6, "min_pnr": 5, "motion_correct": "off"},
        "Calcium generated fixture",
    )
    review = json.loads((output / "quality-review.json").read_text())
    assert review["status"] == "uncurated"
    assert review["components"] > 0
    assert (output / "saved_movies/estimates.hdf5").is_file()
    assert sum(1 for _ in (output / "component-traces.csv").open()) == 161


def test_real_neuralynx_export_preserves_gaps_and_hardware_time(service, tmp_path):
    script = tmp_path / "generate.py"
    script.write_text('''import numpy as np
from pathlib import Path
from neo.rawio.neuralynxrawio.neuralynxrawio import NeuralynxRawIO, nev_dtype
root=Path(__file__).parent
base="""######## Neuralynx Data File Header
-FileVersion 3.4
-CheetahRev 5.7.4
-AcquisitionSystem AcqSystem1 DigitalLynxSX
-TimeCreated 2026/09/17 00:00:00
-TimeClosed 2026/09/17 00:01:00
-SamplingFrequency 1000
-ADBitVolts 0.000001
-InputInverted False
-ADMaxValue 32767
"""
header=(base+'-FileType CSC\\n-AcqEntName CSC1\\n-ADChannel 1\\n-NumADChannels 1\\n').encode().ljust(16384,b'\\0')
records=np.zeros(2,dtype=NeuralynxRawIO._ncs_dtype)
records['timestamp']=[10000000,12000000]
records['channel_id']=1
records['sample_rate']=1000
records['nb_valid']=512
records['samples'][0]=np.arange(512)
records['samples'][1]=np.arange(512)+1000
(root/'CSC1.ncs').write_bytes(header+records.tobytes())
events=np.zeros(1,dtype=nev_dtype)
events['timestamp']=10000000
events['event_id']=1
events['event_string']=b'synthetic start'
header=(base+'-FileType Event\\n-AcqEntName Events\\n').encode().ljust(16384,b'\\0')
(root/'Events.nev').write_bytes(header+events.tobytes())
''')
    subprocess.run([RUNTIME, str(script)], check=True)
    files = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.suffix in {".nev", ".ncs"}}
    output = execute(service, files, "ephys-export", {"channel": "CSC1"}, "Neuralynx generated fixture")
    with (output / "channel.csv").open() as stream:
        rows = list(csv.reader(stream))[1:]
    assert len(rows) == 1024  # No synthetic samples inserted in the recording gap.
    assert float(rows[0][0]) == pytest.approx(10)
    assert float(rows[512][0]) == pytest.approx(12)
    assert float(rows[512][1]) == pytest.approx(1000)
