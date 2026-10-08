"""Jev Playground — 本地单页应用：自输入题目，实时调 TypeSafe System One API。

零第三方 web 依赖（stdlib http.server）；只依赖 bench venv 里的 typesafe_sdk。
API key 优先取环境变量 TYPESAFE_API_KEY，也可由页面输入（仅存内存/浏览器，绝不落盘、绝不打日志）。

启动:  D:/jev/bench/jev-benchmarking/.venv/Scripts/python server.py  (或双击 start.bat)
"""

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient, TypeSafeAPIError

HOST, PORT = "127.0.0.1", 8770
STATIC = Path(__file__).parent / "static"
USD_PER_MTOK = 0.042  # Jev 计价：输入 $0.042/MTok，输出免费


class RawResponse(BaseModel):
    """原样保留响应体，前端直接渲染。"""

    model_config = ConfigDict(extra="allow")


class Bad(Exception):
    """请求本身不合法（4xx 可恢复，前端展示 message）。"""


def build_questions(specs: list[dict]) -> dict:
    if not specs:
        raise Bad("questions 不能为空")
    out = {}
    for i, s in enumerate(specs):
        qid = str(s.get("id") or f"q{i + 1}").strip()
        if not qid or qid in out:
            raise Bad(f"问题 id 非法或重复: {qid!r}")
        instr = str(s.get("instructions") or "").strip()
        if not instr:
            raise Bad(f"问题 {qid}: instructions 不能为空")
        t = s.get("type")
        if t == "choice":
            opts = s.get("options") or {}
            if not isinstance(opts, dict) or not (2 <= len(opts) <= 255):
                raise Bad(f"问题 {qid}: choice 需要 2-255 个选项")
            keys = [str(k).strip() for k in opts]
            if any(not k for k in keys) or len(set(keys)) != len(keys):
                raise Bad(f"问题 {qid}: 选项 key 为空或重复")
            out[qid] = Choice(instructions=instr, criteria={k: (str(v) if v not in (None, "") else None) for k, v in opts.items()})
        elif t == "score":
            levels = [str(x).strip() for x in (s.get("levels") or []) if str(x).strip()]
            if not (2 <= len(levels) <= 10) or len(set(levels)) != len(levels):
                raise Bad(f"问题 {qid}: score 需要 2-10 个非空且不重复的等级")
            out[qid] = Score(instructions=instr, criteria=levels)
        elif t == "noul":
            crit = s.get("criteria") or {}
            true_, false_ = str(crit.get("true") or "").strip(), str(crit.get("false") or "").strip()
            out[qid] = Noul(instructions=instr, criteria=({"true": true_, "false": false_} if true_ and false_ else None))
        else:
            raise Bad(f"问题 {qid}: 未知类型 {t!r}（choice/noul/score）")
    return out


def friendly_error(e: Exception) -> tuple[int, str]:
    if isinstance(e, TypeSafeAPIError):
        status = e.status or 0
        msg = str(e)[:300]
        if status == 401:
            return 401, f"API key 无效或未授权（HTTP 401）。检查 console.typesafe.ai 的 key。{msg}"
        if status == 402:
            return 402, f"账户余额不足（HTTP 402）。{msg}"
        if status == 429:
            return 429, f"触发限流（HTTP 429），稍等几秒重试。{msg}"
        if status in (413, 422):
            return 400, f"请求被 API 拒绝（HTTP {status}，多为 state 过长或字段校验失败）。{msg}"
        if status >= 500:
            return 502, f"TypeSafe 服务端错误（HTTP {status}），可重试。{msg}"
        return 502, msg
    return 502, f"{type(e).__name__}: {e}"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # 安静模式：不打印请求体，杜绝 key 泄漏到控制台
        print(f"[{time.strftime('%H:%M:%S')}] {self.address_string()} {fmt % args}", file=sys.stderr)

    def _send(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _static(self, name: str, mime: str):
        data = (STATIC / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{mime}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._static("index.html", "text/html")
        elif self.path == "/api/health":
            import os
            self._send(200, {"ok": True, "key_env": bool(os.environ.get("TYPESAFE_API_KEY"))})
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if self.path != "/api/ask":
            self._send(404, {"ok": False, "error": "not found"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception as e:
            self._send(400, {"ok": False, "error": f"请求体不是合法 JSON: {e}"})
            return

        import os
        key = str(req.get("key") or "").strip() or os.environ.get("TYPESAFE_API_KEY", "")
        if not key:
            self._send(400, {"ok": False, "error": "没有 API key：设置环境变量 TYPESAFE_API_KEY，或在页面右上角输入（只存你的浏览器）。"})
            return
        model = str(req.get("model") or "jev-latest").strip()
        state = req.get("state")
        if isinstance(state, str) and state.strip():
            state = state.strip()
        if not isinstance(state, (dict, list, str)) or state in ({}, [], ""):
            self._send(400, {"ok": False, "error": "state 不能为空（字符串或 JSON 对象/数组）"})
            return

        try:
            questions = build_questions(req.get("questions") or [])
        except Bad as e:
            self._send(400, {"ok": False, "error": str(e)})
            return

        t0 = time.monotonic()
        try:
            with TypeSafeClient(api_key=key, model=model, timeout=60.0) as client:
                resp = client.system_one(state, questions, response_model=RawResponse)
        except Exception as e:  # noqa: BLE001
            code, msg = friendly_error(e)
            self._send(code, {"ok": False, "error": msg})
            return
        latency_ms = round((time.monotonic() - t0) * 1000)

        body = resp.model_dump()
        usage = body.get("usage") or {}
        in_tok = int(usage.get("input_tokens") or 0)
        self._send(200, {
            "ok": True,
            "model": body.get("model") or model,
            "latency_ms": latency_ms,
            "usage": usage,
            "est_cost_usd": round(in_tok / 1e6 * USD_PER_MTOK, 6),
            "answers": body.get("answers") or {},
        })


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Jev Playground  http://{HOST}:{PORT}   (Ctrl-C 停止)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
