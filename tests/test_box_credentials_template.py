"""Check the two authentication choices in the copyable Box template."""

import runpy
import sys
from pathlib import Path
from types import ModuleType


def test_box_template_selects_ccg_or_developer_token(monkeypatch, tmp_path):
    class CCGConfig:
        def __init__(self, **values):
            self.values = values

    class BoxCCGAuth:
        def __init__(self, config):
            self.config = config

    class BoxDeveloperTokenAuth:
        def __init__(self, token):
            self.token = token

    sdk = ModuleType("box_sdk_gen")
    sdk.CCGConfig = CCGConfig
    sdk.BoxCCGAuth = BoxCCGAuth
    sdk.BoxDeveloperTokenAuth = BoxDeveloperTokenAuth
    monkeypatch.setitem(sys.modules, "box_sdk_gen", sdk)

    source = (
        Path(__file__).resolve().parents[1]
        / "src/aceneurotools/shared/BLANK_box_credentials.py"
    ).read_text()

    credentials_file = tmp_path / "box_credentials.py"
    credentials_file.write_text(source)
    ccg_auth = runpy.run_path(str(credentials_file))["auth"]
    assert isinstance(ccg_auth, BoxCCGAuth)

    credentials_file.write_text(
        source.replace(
            "dev_token = 'PUT_YOUR_BOX_DEVELOPER_TOKEN_HERE'",
            "dev_token = 'temporary-test-token'",
        )
    )
    token_auth = runpy.run_path(str(credentials_file))["auth"]
    assert isinstance(token_auth, BoxDeveloperTokenAuth)
    assert token_auth.token == "temporary-test-token"
