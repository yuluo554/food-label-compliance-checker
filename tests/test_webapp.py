"""Web 面板测试（依赖 web extra；缺 fastapi 时整模块跳过——pyproject extras
覆盖由 tests/test_extras_gate.py 静态守门，见 plan/05 M5 DoD）。"""
import pytest

fastapi = pytest.importorskip("fastapi")

from food_label_checker.webapp import create_app  # noqa: E402
from food_label_checker.webapp.page import PAGE_HTML  # noqa: E402


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    return TestClient(create_app())


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_swagger_docs_disabled():
    """0 外链纪律：Swagger UI/ReDoc 引 CDN，必须显式关闭。"""
    app = create_app()
    assert app.docs_url is None
    assert app.redoc_url is None


def test_index_page_zero_external_links(client):
    """单页面板可开且 0 外链：整页 HTML 不得含任何 http(s) 引用。"""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "食品标签合规审查面板" in html
    assert "http://" not in html and "https://" not in html


def test_index_page_source_zero_external_links():
    """源码常量层直接断言（不依赖路由）：改动 page.py 必过此关。"""
    assert "http://" not in PAGE_HTML and "https://" not in PAGE_HTML
    assert "食品标签合规审查面板" in PAGE_HTML


def test_api_check_multipart_utf8(client):
    """multipart 上传 UTF-8 标签文本 → 完整审查 JSON（含 trace）。"""
    files = {
        "file": (
            "label.txt",
            "食品名称：测试乳\n净含量：500mL\n".encode("utf-8"),
            "text/plain",
        )
    }
    resp = client.post("/api/check", files=files, data={"ruleset": "2011"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["results"]) == {"gb7718-2011"}
    assert body["card"]["fields"]["food_name"]["value"] == "测试乳"
    assert body["pipeline"]["nodes"]
    assert "dual_diff" not in body  # 单规则集不对照


def test_api_check_text_field_dual(client):
    resp = client.post(
        "/api/check", data={"text": "食品名称：测试乳\n", "ruleset": "both"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["results"]) == {"gb7718-2011", "gb7718-2025"}
    assert "dual_diff" in body


def test_api_check_requires_input(client):
    resp = client.post("/api/check", data={"ruleset": "both"})
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_api_check_unknown_ruleset_400(client):
    resp = client.post(
        "/api/check", data={"text": "食品名称：测试乳\n", "ruleset": "1990"}
    )
    assert resp.status_code == 400
    assert "未知规则集" in resp.json()["error"]


def test_api_check_bad_encoding_400(client):
    files = {"file": ("bad.txt", b"\xff\xfe\x00\x01not-utf8", "text/plain")}
    resp = client.post("/api/check", files=files)
    assert resp.status_code == 400
    assert "UTF-8" in resp.json()["error"]
