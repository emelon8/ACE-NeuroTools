"""Exercise a real movie read and local GUI HTTP requests after installation."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]


def main():
    import caiman
    import cv2
    import numpy as np
    from gui.server import ProjectServer

    with tempfile.TemporaryDirectory(prefix="ace-setup-check-") as folder:
        movie_path = Path(folder) / "test.avi"
        writer = cv2.VideoWriter(str(movie_path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (32, 32))
        if not writer.isOpened():
            raise RuntimeError("OpenCV cannot write the small test movie.")
        try:
            for level in (20, 40, 60, 80):
                writer.write(np.full((32, 32, 3), level, dtype=np.uint8))
        finally:
            writer.release()
        movie = caiman.load_movie_chain([str(movie_path)])
        assert movie.shape == (4, 32, 32), f"Unexpected test movie shape: {movie.shape}"
        assert np.allclose(np.asarray(movie).mean(axis=(1, 2)), [20, 40, 60, 80], atol=3)
    server = ProjectServer(("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        with urlopen(url + "/api/health", timeout=10) as response:
            assert json.load(response)["application"] == "ACE Experiments"
        for resource in ("/", "/app.js", "/assets/inter-latin-wght.woff2"):
            with urlopen(url + resource, timeout=10) as response:
                assert response.status == 200 and response.read(), resource
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    print("Movie reading and GUI checks passed. ACE is ready to open in your browser.")


if __name__ == "__main__":
    main()
