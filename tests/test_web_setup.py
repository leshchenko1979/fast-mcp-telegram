from types import SimpleNamespace

import pytest
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


@pytest.fixture
def setup_routes():
    app = _FakeMcpApp()
    web_setup.register_web_setup_routes(app)
    return app.routes


@pytest.mark.asyncio
async def test_setup_phone_flood_returns_phone_form_without_session(
    monkeypatch, setup_routes, tmp_path
):
    web_setup._setup_sessions.clear()
    cfg = ServerConfig()
    cfg.session_dir = str(tmp_path)
    set_config(cfg)

    class _Client:
        async def connect(self):
            return None

        async def send_code_request(self, _phone):
            raise PhoneNumberFloodError(request=None)

        async def disconnect(self):
            return None

    captured = {}

    def _template_response(_request, template_name, context=None):
        captured["template"] = template_name
        captured["context"] = context or {}
        return SimpleNamespace(template=template_name, context=context or {})

    monkeypatch.setattr(web_setup, "create_session_client", lambda _path: _Client())
    monkeypatch.setattr(web_setup.templates, "TemplateResponse", _template_response)

    handler = setup_routes[("/setup/phone", ("POST",))]
    response = await handler(_FakeRequest({"phone": "+1234567890"}))

    assert response.template == "fragments/new_session_phone_form.html"
    assert "Too many attempts" in response.context["error"]
    assert len(web_setup._setup_sessions) == 0


@pytest.mark.asyncio
async def test_setup_verify_invalid_session_returns_html_error(
    monkeypatch, setup_routes
):
    web_setup._setup_sessions.clear()
    captured = {}

    def _template_response(_request, template_name, context=None):
        captured["template"] = template_name
        captured["context"] = context or {}
        return SimpleNamespace(template=template_name, context=context or {})

    monkeypatch.setattr(web_setup.templates, "TemplateResponse", _template_response)

    handler = setup_routes[("/setup/verify", ("POST",))]
    response = await handler(_FakeRequest({"setup_id": "missing", "code": "12345"}))

    assert response.template == "fragments/error.html"
    assert response.context["error"] == "Invalid setup session."
