"""Web 面板最小冒烟（依赖 web extra；缺 fastapi 时整模块跳过——
extras 覆盖守门测试随 M5 落地，见 plan/05 M5 DoD）。"""
import pytest

fastapi = pytest.importorskip("fastapi")

from food_label_checker.webapp import create_app  # noqa: E402


def test_health_endpoint():
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
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
