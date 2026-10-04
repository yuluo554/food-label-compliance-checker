"""Web 面板（M5，plan/04 §7）。

形态（决策 D09）：FastAPI + 零依赖内联单页（vanilla JS + inline CSS，
见 page.py），无构建/无 vendor/页面 0 外链，断网可演示；docs_url 与
redoc_url 显式关闭（Swagger UI 引 CDN）。依赖 fastapi/uvicorn/python-multipart
（web extra，multipart 解析缺 python-multipart 会启动即崩——extras 守门测试锁定）。

路由：GET /（面板）、POST /api/check（multipart 上传文本 → 完整审查 JSON）、
GET /api/health。

注意：本模块不能启用 `from __future__ import annotations`——端点注解会被字符串化，
而 UploadFile 等在 create_app() 内导入，pydantic 回解 ForwardRef 时不可见
（Python 3.8 + fastapi 0.124 实测 PydanticUserError）。
"""


def _import_fastapi():
    try:
        import fastapi  # noqa: F401
    except ImportError as exc:  # pragma: no cover - 依赖缺失路径（extras 守门测试 mock 注入覆盖）
        raise ImportError(
            "Web 面板需要安装 web 扩展：pip install 'food-label-compliance-checker[web]'"
        ) from exc
    return fastapi


def create_app():
    """构建 FastAPI 应用（0 外链内联单页面板 + 审查 API）。"""
    fastapi = _import_fastapi()
    from fastapi import File, Form, UploadFile
    from fastapi.responses import HTMLResponse, JSONResponse

    from .. import __version__ as _pkg_version
    from ..pipeline import check_text
    from ..rules.engine import resolve_ruleset_ids
    from .page import PAGE_HTML

    app = fastapi.FastAPI(
        title="food-label-compliance-checker",
        version=_pkg_version,
        docs_url=None,
        redoc_url=None,
    )

    @app.get("/", response_class=HTMLResponse)
    def index():
        return PAGE_HTML

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": _pkg_version}

    @app.post("/api/check")
    async def api_check(
        file: UploadFile = File(None),
        text: str = Form(""),
        ruleset: str = Form("both"),
        llm: str = Form("false"),
    ):
        if file is not None and file.filename:
            raw = await file.read()
            try:
                content = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                return JSONResponse(
                    status_code=400,
                    content={"error": "上传文件需为 UTF-8 编码"},
                )
        elif text:
            content = text
        else:
            return JSONResponse(
                status_code=400,
                content={"error": "请上传标签文本文件（字段 file）或粘贴文本（字段 text）"},
            )
        try:
            ids = resolve_ruleset_ids(ruleset)
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})

        llm_config = None
        if llm == "true":
            from ..llm.config import from_env as llm_from_env

            llm_config = llm_from_env()
            llm_config.enabled = True  # 面板勾选为显式开启开关；不可达由兜底层降级
        return check_text(content, ids, llm_config)

    return app
