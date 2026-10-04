"""M5 Web 真实上传冒烟：起真实 uvicorn 回环端口，用 urllib 发 multipart 与 UTF-8 JSON。

纪律：中文一律脚本内构造字节发送，不用 curl 命令行传中文（Windows 控制台 GBK
会污染请求体）；urllib 走 ProxyHandler({}) 直连——本机注册表系统代理曾被污染，
默认 getproxies() 会把回环请求路由到坏代理。
"""
import json
import socket
import threading
import time
import urllib.request

import pytest

fastapi = pytest.importorskip("fastapi")
uvicorn = pytest.importorskip("uvicorn")

from food_label_checker.webapp import create_app  # noqa: E402

# 直连（绕过系统/注册表代理）
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server():
    port = _free_port()
    config = uvicorn.Config(
        create_app(), host="127.0.0.1", port=port, log_level="warning"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            with _OPENER.open(base + "/api/health", timeout=2) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.2)
    else:
        server.should_exit = True
        raise RuntimeError("uvicorn 未在期限内就绪")
    yield base
    server.should_exit = True
    thread.join(timeout=10)


def _get(url):
    with _OPENER.open(url, timeout=10) as resp:
        return resp.status, resp.read()


def test_health_over_real_server(server):
    status, body = _get(server + "/api/health")
    assert status == 200
    assert json.loads(body)["status"] == "ok"


def test_real_index_page_zero_external(server):
    status, body = _get(server + "/")
    assert status == 200
    html = body.decode("utf-8")
    assert "食品标签合规审查面板" in html
    assert "http://" not in html and "https://" not in html


def test_real_multipart_upload_utf8(server):
    """真实进程 multipart 上传：UTF-8 中文标签 → 完整审查 JSON。"""
    label = (
        "食品名称：测试乳\n净含量：500mL\n"
        "生产日期：2026年09月12日\n保质期：6个月\n"
        "保质期到期日：2027年03月12日\n贮存条件：常温\n"
        "生产商：某厂\n地址：某地\n联系方式：400-000-0000\n"
        "食品生产许可证编号：SC12345678901234\n产品标准代号：GB 1234\n"
    )
    boundary = "----flchecksmoke2026"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="label.txt"\r\n'
        f"Content-Type: text/plain; charset=utf-8\r\n\r\n"
    ).encode("utf-8") + label.encode("utf-8") + f"\r\n--{boundary}--\r\n".encode(
        "utf-8"
    )
    req = urllib.request.Request(
        server + "/api/check",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with _OPENER.open(req, timeout=30) as resp:
        assert resp.status == 200
        data = json.loads(resp.read())
    assert set(data["results"]) == {"gb7718-2011", "gb7718-2025"}
    assert data["card"]["fields"]["food_name"]["value"] == "测试乳"
    assert data["card"]["fields"]["net_content"]["value"]["amount"] == 500
    nodes = [n["node"] for n in data["pipeline"]["nodes"]]
    assert nodes[0] == "load_input" and nodes[-1] == "emit"
    assert data["warnings"] == []
