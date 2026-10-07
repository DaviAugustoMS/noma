import socket

import httpx
import pytest

from app import create_app
from app.services import site_seed
from app.services.site_seed import SiteSeedError


def _resolve_to(monkeypatch, *addresses):
    def fake(host, port, type=0, **_):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, port)) for a in addresses]

    monkeypatch.setattr(site_seed.socket, "getaddrinfo", fake)


@pytest.mark.parametrize("url", [
    "", "   ", "ftp://example.com", "javascript:alert(1)", "https://user:pw@example.com",
    "https://example.com:8080/", "https://example.com:bad/",
])
def test_rejects_malformed_or_unsafe_urls(monkeypatch, url):
    _resolve_to(monkeypatch, "93.184.216.34")
    with pytest.raises(SiteSeedError):
        site_seed.validate_public_url(url)


@pytest.mark.parametrize("address", [
    "127.0.0.1", "10.0.0.5", "192.168.1.10", "172.16.0.1", "169.254.169.254", "0.0.0.0", "100.64.0.1", "::1",
])
def test_blocks_private_and_metadata_addresses(monkeypatch, address):
    _resolve_to(monkeypatch, address)
    with pytest.raises(SiteSeedError) as error:
        site_seed.validate_public_url("https://interno.example.com")
    assert error.value.code == "siteUrlBlocked"


def test_blocks_when_any_resolved_address_is_private(monkeypatch):
    _resolve_to(monkeypatch, "93.184.216.34", "10.0.0.1")
    with pytest.raises(SiteSeedError):
        site_seed.validate_public_url("https://example.com")


def test_adds_https_when_scheme_missing(monkeypatch):
    _resolve_to(monkeypatch, "93.184.216.34")
    assert site_seed.validate_public_url("example.com/a") == "https://example.com/a"


def test_redirect_to_internal_address_is_blocked(monkeypatch):
    def fake(host, port, type=0, **_):
        ip = "10.0.0.1" if host == "interno.local" else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    monkeypatch.setattr(site_seed.socket, "getaddrinfo", fake)

    def handler(request):
        return httpx.Response(302, headers={"location": "http://interno.local/segredo"})

    real_client = httpx.Client
    monkeypatch.setattr(
        site_seed.httpx, "Client",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    with pytest.raises(SiteSeedError) as error:
        site_seed._download("https://publico.example.com")
    assert error.value.code == "siteUrlBlocked"


def test_extract_page_drops_scripts_and_requires_text():
    html = (
        "<html><head><title>Acme</title><meta name='description' content='Saude'></head>"
        "<body><script>evil()</script><nav>menu</nav><main>"
        + "A Acme oferece beneficios corporativos de saude. " * 5
        + "</main></body></html>"
    )
    page = site_seed.extract_page("https://acme.com", html)
    assert page.title == "Acme" and page.description == "Saude"
    assert "evil" not in page.text and "menu" not in page.text and "Acme oferece" in page.text
    with pytest.raises(SiteSeedError) as error:
        site_seed.extract_page("https://acme.com", "<html><body>oi</body></html>")
    assert error.value.code == "siteNoContent"


class _FakeLLM:
    def __init__(self, result):
        self.result = result
        self.messages = None

    def chat_json(self, messages, **_):
        self.messages = messages
        return self.result


def test_generate_from_url_returns_seed_and_prompt(monkeypatch):
    page = "A Acme oferece beneficios corporativos de saude. " * 5
    monkeypatch.setattr(site_seed, "_download", lambda url: ("https://acme.com", f"<main>{page}</main>"))
    llm = _FakeLLM({"title": "Acme", "seed_markdown": "# Acme", "simulation_requirement": "Simular reacao."})
    data = site_seed.generate_from_url("acme.com", llm=llm)
    assert data == {
        "url": "https://acme.com", "title": "Acme",
        "seed_markdown": "# Acme", "simulation_requirement": "Simular reacao.",
    }
    assert "untrusted" in llm.messages[0]["content"] and "LANGUAGE RULE" in llm.messages[1]["content"]


def test_generate_from_url_rejects_incomplete_llm_answer(monkeypatch):
    page = "A Acme oferece beneficios corporativos de saude. " * 5
    monkeypatch.setattr(site_seed, "_download", lambda url: ("https://acme.com", f"<main>{page}</main>"))
    with pytest.raises(SiteSeedError) as error:
        site_seed.generate_from_url("acme.com", llm=_FakeLLM({"seed_markdown": "", "title": "x"}))
    assert error.value.code == "siteGenerationFailed"


def test_route_maps_errors_to_status_and_message(monkeypatch):
    def boom(url, llm=None):
        raise SiteSeedError("siteUrlBlocked")

    monkeypatch.setattr(site_seed, "generate_from_url", boom)
    client = create_app().test_client()
    response = client.post("/api/graph/seed/from-url", json={"url": "http://127.0.0.1"})
    body = response.get_json()
    assert response.status_code == 400 and body["success"] is False and body["code"] == "siteUrlBlocked"
    assert body["error"] and not body["error"].startswith("err.")


def test_route_success(monkeypatch):
    monkeypatch.setattr(site_seed, "generate_from_url", lambda url, llm=None: {"seed_markdown": "# x", "simulation_requirement": "y", "title": "t", "url": url})
    response = create_app().test_client().post("/api/graph/seed/from-url", json={"url": "acme.com"})
    assert response.get_json()["data"]["seed_markdown"] == "# x"


def test_extract_page_uses_metadata_json_ld_and_extra_text_for_js_sites():
    html = (
        "<html><head><title>Clean</title><meta name='description' content='App para macOS'>"
        "<meta property='og:description' content='Entenda o que ocupa espaco'>"
        "<script type='application/ld+json'>{\"@type\":\"SoftwareApplication\",\"name\":\"Clean DLEC\","
        "\"description\":\"Revisa cada limpeza com IA\"}</script></head>"
        "<body><div id='root'></div><script>app()</script></body></html>"
    )
    page = site_seed.extract_page("https://clean.example", html, "## Fatos\n- Tudo vai para a Lixeira.")
    assert "Entenda o que ocupa espaco" in page.text
    assert "Revisa cada limpeza com IA" in page.text and "Lixeira" in page.text
    assert "app()" not in page.text


def test_llms_txt_is_ignored_when_site_returns_html_or_fails(monkeypatch):
    monkeypatch.setattr(site_seed, "_download", lambda url: (url, "<!doctype html><html></html>"))
    assert site_seed._fetch_llms_txt("https://x.example/a/b") == ""

    def fail(url):
        raise SiteSeedError("siteFetchFailed", 502)

    monkeypatch.setattr(site_seed, "_download", fail)
    assert site_seed._fetch_llms_txt("https://x.example") == ""


def test_llms_txt_is_requested_from_the_same_origin(monkeypatch):
    seen = []
    monkeypatch.setattr(site_seed, "_download", lambda url: (seen.append(url), (url, "# Site\n- fato"))[1])
    assert "fato" in site_seed._fetch_llms_txt("https://x.example/a/b?q=1")
    assert seen == ["https://x.example/llms.txt"]
