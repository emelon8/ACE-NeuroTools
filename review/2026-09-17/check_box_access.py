"""Read-only Box identity/folder probe. Secrets never appear in arguments/output.

This does not configure the project's legacy downloader or download recordings.
CCG JSON shape: client_id, client_secret, and exactly one of user_id/enterprise_id.
JWT accepts Box's downloaded JSON configuration unchanged.
"""

import argparse
import getpass
import json
import sys
from pathlib import Path


def make_client(args):
    from box_sdk_gen import BoxCCGAuth, BoxClient, BoxDeveloperTokenAuth, BoxJWTAuth, CCGConfig, JWTConfig

    if args.jwt_config:
        auth = BoxJWTAuth(config=JWTConfig.from_config_file(str(Path(args.jwt_config).expanduser())))
    elif args.token_prompt:
        auth = BoxDeveloperTokenAuth(token=getpass.getpass("Temporary Box access token (hidden): "))
    else:
        if args.ccg_config:
            data = json.loads(Path(args.ccg_config).expanduser().read_text())
        else:
            data = {
                "client_id": input("Client ID: ").strip(),
                "client_secret": getpass.getpass("Client secret (hidden): "),
            }
            subject = input("Authenticate as 'user' or enterprise 'service' account: ").strip().lower()
            if subject not in ("user", "service"):
                raise ValueError("Choose user or service")
            key = "user_id" if subject == "user" else "enterprise_id"
            data[key] = input(f"{key}: ").strip()
        if bool(data.get("user_id")) == bool(data.get("enterprise_id")):
            raise ValueError("Provide exactly one user_id or enterprise_id")
        config = CCGConfig(
            client_id=data["client_id"],
            client_secret=data["client_secret"],
            **{key: str(data[key]) for key in ("user_id", "enterprise_id") if data.get(key)},
        )
        auth = BoxCCGAuth(config=config)
    return BoxClient(auth=auth)


def main():
    parser = argparse.ArgumentParser(
        description="Verify Box identity and folder access without downloading files or saving secrets."
    )
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument(
        "--ccg-prompt", action="store_true", help="Enter existing CCG credentials locally; do not save them"
    )
    modes.add_argument("--ccg-config", metavar="PATH", help="Read an existing private CCG JSON file")
    modes.add_argument("--jwt-config", metavar="PATH", help="Read Box's existing downloaded JWT JSON")
    modes.add_argument(
        "--token-prompt", action="store_true", help="Temporary access-token check, not durable OAuth configuration"
    )
    parser.add_argument("--folder-id", help="Numeric ID from the lab's /folder/ URL; prompts if omitted")
    args = parser.parse_args()
    stage = "credential loading"
    try:
        client = make_client(args)
        folder_id = args.folder_id or input("Lab Box folder ID: ").strip()
        if not folder_id.isdecimal():
            print("Expected a numeric folder ID, not a shared-link token.", file=sys.stderr)
            return 2
        stage = "identity verification"
        me = client.users.get_user_me(fields=["id", "name"])
        print(f"Authenticated identity: {me.name} (ID {me.id})")
        stage = "folder access verification"
        folder = client.folders.get_folder_by_id(folder_id, fields=["id", "name"])
        client.folders.get_folder_items(folder_id, limit=1, fields=["id", "type"])
        print(f"Verified folder: {folder.name} (ID {folder.id})")
        print(
            "Identity, folder metadata, and folder listing succeeded. File download permission/integrity has not been tested."
        )
        print("No recordings downloaded. No credentials saved. No remote content changed.")
        return 0
    except (KeyboardInterrupt, EOFError):
        print("Cancelled; no credentials saved.", file=sys.stderr)
        return 130
    except Exception as exc:
        # Box exceptions can contain request bodies. Never print str(exc) or a traceback.
        status = getattr(exc, "status_code", None)
        suffix = f" (HTTP {status})" if isinstance(status, int) else ""
        print(
            f"Box check failed during {stage}{suffix}. Error details suppressed to protect credentials.",
            file=sys.stderr,
        )
        print("Check the authentication type, app authorization, account identity, and folder access.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
