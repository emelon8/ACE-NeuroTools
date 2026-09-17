"""Launch the local browser workbench without loading CaImAn."""

import argparse
import secrets
import threading
import webbrowser
from pathlib import Path

import uvicorn

from aceneurotools.evc.api import EVCError

from .app import create_app
from .demo import create_demo
from .workspaces import WorkspaceRegistry, discover


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        action="append",
        type=Path,
        default=[],
        help="Existing EVC experiment; repeat for multiple experiments",
    )
    parser.add_argument("--project", type=Path, help="Discover immediate child EVC experiments")
    parser.add_argument("--demo", type=Path, help="Create or reopen synthetic examples in this directory")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--author", help="'Name <email>' used for experiment history (defaults to EVC local identity)")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--dist", type=Path, default=Path(__file__).resolve().parents[2] / "dist")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    if not (args.dist / "index.html").is_file():
        parser.error("Build the GUI first: cd gui && npm ci && npm run build")
    roots = args.workspace
    try:
        if args.project:
            roots += discover(args.project)
        if args.demo:
            roots += create_demo(args.demo)
        registry = WorkspaceRegistry(roots, author=args.author)
    except (ValueError, OSError, EVCError) as exc:
        parser.error(str(exc))
    token = secrets.token_urlsafe(32)
    url = f"http://127.0.0.1:{args.port}/#token={token}"
    print(f"\nACENeuroTools Workbench\nOpen this local session URL:\n{url}\n", flush=True)
    if not args.no_browser:
        timer = threading.Timer(1.2, webbrowser.open, args=(url,))
        timer.daemon = True
        timer.start()
    uvicorn.run(create_app(registry, token, args.port, args.dist), host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
