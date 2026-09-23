"""Serve the throwaway GUI design locally: python scripts/preview_guided_gui.py."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1] / "prototypes" / "guided-experiments"
    server = ThreadingHTTPServer(("127.0.0.1", 8765), partial(SimpleHTTPRequestHandler, directory=str(root)))
    print("GUI design preview: http://127.0.0.1:8765/?variant=A", flush=True)
    print("Sample data only. Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
