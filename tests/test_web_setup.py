import os
import re
from types import SimpleNamespace

import pytest
from jinja2 import Environment, FileSystemLoader
from telethon.errors.rpcerrorlist import PhoneNumberFloodError

from src.config.server_config import ServerConfig, set_config
from src.server_components import web_setup


class _FakeMcpApp:
    def __init__(self):
        self.routes = {}

    def custom_route(self, path, methods):
        def decorator(func):
            self.routes[(path, tuple(methods))] = func
            return func

        return decorator


class _FakeRequest:
    def __init__(self, form_data):
        self._form_data = form_data

    async def form(self):
        return self._form_data


def _patch_template_response(monkeypatch, capture: dict | None = None):
    """Patch Jinja2Templates.TemplateResponse; optionally record last template and context."""

    def _tr(_request, template_name, context=None):
        ctx = context or {}
        if capture is not None:
            capture["template"] = template_name
            capture["context"] = ctx
        return SimpleNamespace(template=template_name, context=ctx)

    monkeypatch.setattr(web_setup.templates, "TemplateResponse", _tr)


@pytest.fixture
def setup_routes():
    app = _FakeMcpApp()
    web_setup.register_web_setup_routes(app)
    return app.routes


def test_new_session_phone_htmx_fragment_section_is_not_hidden():
    """HTMX replaces #setup-flow; a hidden root section would hide errors."""
    templates_dir = os.path.join(os.path.dirname(__file__), "..", "src", "templates")
    env = Environment(loader=FileSystemLoader(templates_dir))
    html = env.get_template("fragments/new_session_phone_form.html").render(
        error=web_setup.PHONE_INVALID_MESSAGE
    )
    m = re.search(r'<section[^>]*id="new-session-form"[^>]*>', html)
    assert m is not None
    assert "hidden" not in m.group(0).lower()


def test_reauthorize_token_htmx_fragment_section_is_not_hidden():
    """HTMX replaces #setup-flow; reauthorize token errors must stay visible."""
    templates_dir = os.path.join(os.path.dirname(__file__), "..", "src", "templates")
    env = Environment(loader=FileSystemLoader(templates_dir))
    html = env.get_template("fragments/reauthorize_token_form.html").render(
        error=web_setup.REAUTHORIZE_NO_SESSION_MESSAGE
    )
    m = re.search(r'<section[^>]*id="reauthorize-form"[^>]*>', html)
    assert m is not None
    assert "hidden" not in m.group(0).lower()


def test_delete_session_htmx_fragment_section_is_not_hidden():
    """HTMX replaces #setup-flow; delete errors must stay visible."""
    templates_dir = os.path.join(os.path.dirname(__file__), "..", "src", "templates")
    env = Environment(loader=FileSystemLoader(templates_dir))
    html = env.get_template("fragments/delete_session_form.html").render(
        error=web_setup.SESSION_NOT_FOUND_MESSAGE
    )
    m = re.search(r'<section[^>]*id="delete-session-form"[^>]*>', html)
    assert m is not None
    assert "hidden" not in m.group(0).lower()


@pytest.mark.asyncio
async def test_setup_reauthorize_empty_token_returns_token_form(
    monkeypatch, setup_routes, tmp_path
):
    web_setup._setup_sessions.clear()
    cfg = ServerConfig()
    cfg.session_dir = str(tmp_path)
    set_config(cfg)

    _patch_template_response(monkeypatch)

    handler = setup_routes[("/setup/reauthorize", ("POST",))]
    response = await handler(_FakeRequest({"token": ""}))

    assert response.template == "fragments/reauthorize_token_form.html"
    assert web_setup.BEARER_TOKEN_REQUIRED_MESSAGE in response.context["error"]


@pytest.mark.asyncio
async def test_setup_reauthorize_phone_invalid_setup_returns_token_form(
    monkeypatch, setup_routes, tmp_path
):
    web_setup._setup_sessions.clear()
    cfg = ServerConfig()
    cfg.session_dir = str(tmp_path)
    set_config(cfg)

    _patch_template_response(monkeypatch)

    handler = setup_routes[("/setup/reauthorize/phone", ("POST",))]
    response = await handler(
        _FakeRequest({"setup_id": "gone", "phone": "+12345678901"})
    )

    assert response.template == "fragments/reauthorize_token_form.html"
    assert "expired" in response.context["error"].lower()


@pytest.mark.asyncio
async def test_setup_delete_missing_token_returns_delete_form(
    monkeypatch, setup_routes, tmp_path
):
    web_setup._setup_sessions.clear()
    cfg = ServerConfig()
    cfg.session_dir = str(tmp_path)
    set_config(cfg)

    _patch_template_response(monkeypatch)

    handler = setup_routes[("/setup/delete", ("POST",))]
    response = await handler(_FakeRequest({"token": ""}))

    assert response.template == "fragments/delete_session_form.html"
    assert web_setup.BEARER_TOKEN_REQUIRED_MESSAGE in response.context["error"]


@pytest.mark.asyncio
async def test_setup_delete_session_not_found_returns_delete_form(
    monkeypatch, setup_routes, tmp_path
):
    web_setup._setup_sessions.clear()
    cfg = ServerConfig()
    cfg.session_dir = str(tmp_path)
    set_config(cfg)

    _patch_template_response(monkeypatch)

    handler = setup_routes[("/setup/delete", ("POST",))]
    response = await handler(_FakeRequest({"token": "no-such-session-file"}))

    assert response.template == "fragments/delete_session_form.html"
    assert "not found" in response.context["error"].lower()


@pytest.mark.asyncio
async def test_setup_reauthorize_missing_session_returns_token_form(
    monkeypatch, setup_routes, tmp_path
):
    web_setup._setup_sessions.clear()
    cfg = ServerConfig()
    cfg.session_dir = str(tmp_path)
    set_config(cfg)

    _patch_template_response(monkeypatch)

    handler = setup_routes[("/setup/reauthorize", ("POST",))]
    response = await handler(_FakeRequest({"token": "nonexistent-token"}))

    assert response.template == "fragments/reauthorize_token_form.html"
    assert "not registered on this server" in response.context["error"]
    assert "Create New Session" in response.context["error"]
    assert len(web_setup._setup_sessions) == 0


@pytest.mark.asyncio
async def test_setup_phone_invalid_number_returns_phone_fragment(
    monkeypatch, setup_routes
):
    web_setup._setup_sessions.clear()

    _patch_template_response(monkeypatch)

    handler = setup_routes[("/setup/phone", ("POST",))]
    response = await handler(_FakeRequest({"phone": "123"}))

    assert response.template == "fragments/new_session_phone_form.html"
    assert "international format" in response.context["error"]


@pytest.mark.asyncio
async def test_setup_phone_flood_returns_phone_form_without_session(
    monkeypatch, setup_routes, tmp_path
):
    web_setup._setup_sessions.clear()
    cfg = ServerConfig()
    cfg.session_dir = str(tmp_path)
    set_config(cfg)
    monkeypatch.setattr(web_setup.time, "time", lambda: 1234.567)
    temp_session_path = tmp_path / "setup-1234567.session"
    temp_session_path.write_text("temp-session")

    class _Client:
        async def connect(self):
            return None

        async def send_code_request(self, _phone):
            raise PhoneNumberFloodError(request=None)

        async def disconnect(self):
            return None

    captured = {}
    monkeypatch.setattr(web_setup, "create_session_client", lambda _path: _Client())
    _patch_template_response(monkeypatch, captured)

    handler = setup_routes[("/setup/phone", ("POST",))]
    response = await handler(_FakeRequest({"phone": "+1234567890"}))

    assert response.template == "fragments/new_session_phone_form.html"
    assert web_setup.PHONE_FLOOD_MESSAGE in response.context["error"]
    assert len(web_setup._setup_sessions) == 0
    assert not temp_session_path.exists()


@pytest.mark.asyncio
async def test_setup_verify_invalid_session_returns_html_error(
    monkeypatch, setup_routes
):
    web_setup._setup_sessions.clear()
    captured = {}

    _patch_template_response(monkeypatch, captured)

    handler = setup_routes[("/setup/verify", ("POST",))]
    response = await handler(_FakeRequest({"setup_id": "missing", "code": "12345"}))

    assert response.template == "fragments/error.html"
    assert response.context["error"] == web_setup.INVALID_SETUP_SESSION_MESSAGE


@pytest.mark.asyncio
async def test_setup_reauthorize_phone_handles_send_code_failure(
    monkeypatch, setup_routes
):
    web_setup._setup_sessions.clear()
    setup_id = "reauth-1"

    class _Client:
        async def send_code_request(self, _phone):
            raise RuntimeError("rpc fail")

    web_setup._setup_sessions[setup_id] = {
        "client": _Client(),
        "created_at": 9999999999,
    }

    _patch_template_response(monkeypatch)

    handler = setup_routes[("/setup/reauthorize/phone", ("POST",))]
    response = await handler(
        _FakeRequest({"setup_id": setup_id, "phone": "+1234567890"})
    )

    assert response.template == "fragments/reauthorize_phone.html"
    assert "Failed to send code" in response.context["error"]


@pytest.mark.asyncio
async def test_setup_reauthorize_phone_rejects_invalid_phone(monkeypatch, setup_routes):
    web_setup._setup_sessions.clear()
    setup_id = "reauth-2"
    web_setup._setup_sessions[setup_id] = {
        "client": object(),
        "created_at": 9999999999,
    }

    _patch_template_response(monkeypatch)

    handler = setup_routes[("/setup/reauthorize/phone", ("POST",))]
    response = await handler(_FakeRequest({"setup_id": setup_id, "phone": "123"}))

    assert response.template == "fragments/reauthorize_phone.html"
    assert "international format" in response.context["error"]


@pytest.mark.asyncio
async def test_setup_reauthorize_phone_normalizes_formatted_phone(
    monkeypatch, setup_routes
):
    web_setup._setup_sessions.clear()
    setup_id = "reauth-3"
    seen = {"phone": None}

    class _Client:
        async def send_code_request(self, phone):
            seen["phone"] = phone
            return

    web_setup._setup_sessions[setup_id] = {
        "client": _Client(),
        "created_at": 9999999999,
    }

    _patch_template_response(monkeypatch)

    handler = setup_routes[("/setup/reauthorize/phone", ("POST",))]
    response = await handler(
        _FakeRequest({"setup_id": setup_id, "phone": "+1 (415) 555-2671"})
    )

    assert response.template == "fragments/code_form.html"
    assert seen["phone"] == "+14155552671"
