"""A second local user cannot access project APIs without the launch capability."""

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from tests.test_gui_server import TOKENS, viewer  # noqa: F401


def response(base, path, token=None, method="GET"):
    headers = {"Authorization": "Bearer " + token} if token is not None else {}
    data = b"{}" if method == "POST" else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    try:
        result = urlopen(Request(base + path, data=data, headers=headers), timeout=5)
    except HTTPError as error:
        result = error
    with result:
        return result.status, result.read()


@pytest.mark.parametrize(
    "path",
    [
        "/api/health",
        "/api/projects",
        "/api/folders",
        "/api/experiment",
        "/api/run/file",
        "/api/preview",
        "/api/neuron/sources",
    ],
)
def test_get_routes_require_token_even_from_same_host(viewer, path):  # noqa: F811
    base, _ = viewer
    assert response(base, path)[0] == 401
    assert response(base, path, "another-local-users-token")[0] == 401


@pytest.mark.parametrize(
    "path",
    [
        "/api/projects/open",
        "/api/experiment/save",
        "/api/run/start",
        "/api/run/stop",
        "/api/crop/save",
        "/api/neuron/decide",
    ],
)
def test_post_routes_require_token_even_from_same_host(viewer, path):  # noqa: F811
    base, _ = viewer
    assert response(base, path, method="POST")[0] == 403
    assert response(base, path, "wrong", "POST")[0] == 403


def test_own_token_works_but_api_responses_never_disclose_it(viewer):  # noqa: F811
    base, _ = viewer
    status, content = response(base, "/api/projects", TOKENS[base])
    assert status == 200 and json.loads(content)["projects"]
    assert TOKENS[base].encode() not in content
    assert response(base, "/")[0] == 200
    assert TOKENS[base].encode() not in response(base, "/")[1]
