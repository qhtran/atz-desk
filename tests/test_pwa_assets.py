"""PWA manifest / service worker / icons routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import FRONTEND_DIR, app


client = TestClient(app)


def test_manifest_json_served():
    res = client.get("/manifest.json")
    assert res.status_code == 200
    assert "manifest" in (res.headers.get("content-type") or "")
    body = res.json()
    assert body["name"]
    assert body["start_url"] == "/"
    assert body["display"] == "standalone"
    assert body["theme_color"] == "#0a0a0a"
    assert any(i.get("sizes") == "192x192" for i in body["icons"])
    assert any(i.get("sizes") == "512x512" for i in body["icons"])


def test_service_worker_served_with_scope_header():
    res = client.get("/sw.js")
    assert res.status_code == 200
    assert "javascript" in (res.headers.get("content-type") or "")
    assert res.headers.get("service-worker-allowed") == "/"
    text = res.text
    assert "atz-desk-shell" in text
    assert "addEventListener" in text


def test_pwa_icons_exist_and_served():
    for name in ("icon-192.png", "icon-512.png", "apple-touch-icon.png"):
        assert (FRONTEND_DIR / "icons" / name).is_file()
        res = client.get(f"/icons/{name}")
        assert res.status_code == 200
        assert res.headers.get("content-type", "").startswith("image/png")
        assert res.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_pwa_icon_rejects_path_traversal():
    assert client.get("/icons/../index.html").status_code == 404
    assert client.get("/icons/not-a-png.txt").status_code == 404


def test_index_links_manifest_and_registers_sw():
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    assert 'rel="manifest"' in html and "/manifest.json" in html
    assert 'name="theme-color"' in html
    assert "apple-mobile-web-app-capable" in html
    assert 'serviceWorker.register("/sw.js"' in html or "serviceWorker.register('/sw.js'" in html
