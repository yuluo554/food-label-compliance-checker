"""Web 面板（M5 实现，plan/04 §7）。

形态（决策 D09）：FastAPI + vanilla JS 内联单页，无构建/无 vendor/0 外链，
docs_url 与 redoc_url 显式关闭（Swagger UI 引 CDN）。完整面板 M5 落地，
本文件当前仅提供 /api/health 健康检查的最小可用 app 供冒烟。
"""
from __future__ import annotations


def _import_fastapi():
    try:
        import fastapi  # noqa: F401
    except ImportError as exc:  # pragma: no cover - 依赖缺失路径
        raise ImportError(
            "Web 面板需要安装 web 扩展：pip install 'food-label-compliance-checker[web]'"
        ) from exc
    return fastapi


def create_app():
    """构建 FastAPI 应用（0 外链内联单页面板随 M5 完整实现）。"""
    fastapi = _import_fastapi()
    from .. import __version__ as _pkg_version

    app = fastapi.FastAPI(
        title="food-label-compliance-checker",
        version=_pkg_version,
        docs_url=None,
        redoc_url=None,
    )

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": _pkg_version}

    return app
