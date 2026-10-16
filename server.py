"""Jev Playground — 本地单页应用：自输入题目，实时调 TypeSafe System One API。

零第三方 web 依赖（stdlib http.server）；只依赖 bench venv 里的 typesafe_sdk。
API key 优先取环境变量 TYPESAFE_API_KEY，也可由页面输入（仅存内存/浏览器，绝不落盘、绝不打日志）。

启动:  D:/jev/bench/jev-benchmarking/.venv/Scripts/python server.py  (或双击 start.bat)
"""

import atexit
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient, TypeSafeAPIError

# 题库：复用 jev-benchmarking harness + 本地 HF 缓存（必须在 import datasets 前设置）
os.environ.setdefault("HF_HOME", "D:/jev/hf-home")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
HARNESS_ROOT = "D:/jev/bench/jev-benchmarking"

HOST, PORT = "127.0.0.1", 8770
STATIC = Path(__file__).parent / "static"
LOG_FILE = Path(__file__).parent / "requests.log"  # 只记请求行（方法/路径），绝不记请求体
BANKS_DIR = Path(__file__).parent / "banks"  # 自建题库（纯 JSON 文件，可手编）
PROVIDERS_FILE = Path(__file__).parent / "providers.json"  # 决策模型提供方（gitignore，首跑自动生成）
USD_PER_MTOK = 0.042  # Jev 计价：输入 $0.042/MTok，输出免费


class RawResponse(BaseModel):
    """原样保留响应体，前端直接渲染。"""

    model_config = ConfigDict(extra="allow")


class Bad(Exception):
    """请求本身不合法（4xx 可恢复，前端展示 message）。"""


def validate_questions(specs: list[dict]) -> dict:
    """前端 specs（choice.options / score.levels）→ 统一 raw 形状 {id: {type, instructions, criteria}}。

    raw 形状即 Jev HTTP 契约里的 questions：choice.criteria={选项:描述}，score.criteria=[等级]，
    noul.criteria={true,false}|None。题库文件、兼容端点请求、SDK 转换共用这一层。
    """
    out: dict = {}
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
            out[qid] = {"type": "choice", "instructions": instr,
                        "criteria": {k: (str(v) if v not in (None, "") else None) for k, v in opts.items()}}
        elif t == "score":
            levels = [str(x).strip() for x in (s.get("levels") or []) if str(x).strip()]
            if not (2 <= len(levels) <= 10) or len(set(levels)) != len(levels):
                raise Bad(f"问题 {qid}: score 需要 2-10 个非空且不重复的等级")
            out[qid] = {"type": "score", "instructions": instr, "criteria": levels}
        elif t == "noul":
            crit = s.get("criteria") or {}
            true_, false_ = str(crit.get("true") or "").strip(), str(crit.get("false") or "").strip()
            out[qid] = {"type": "noul", "instructions": instr,
                        "criteria": ({"true": true_, "false": false_} if true_ and false_ else None)}
        else:
            raise Bad(f"问题 {qid}: 未知类型 {t!r}（choice/noul/score）")
    if not out:
        raise Bad("questions 不能为空")
    return out


def validate_raw_question(q: object, where: str) -> dict:
    """校验单个 raw（harness/Jev 契约）形状的问题；题库文件与上传 JSON 用。"""
    if not isinstance(q, dict):
        raise Bad(f"{where}: 不是对象")
    instr = str(q.get("instructions") or "").strip()
    if not instr:
        raise Bad(f"{where}: instructions 不能为空")
    t = q.get("type")
    if t == "choice":
        crit = q.get("criteria") or {}
        if not isinstance(crit, dict) or not (2 <= len(crit) <= 255):
            raise Bad(f"{where}: choice 需要 2-255 个选项")
        return {"type": "choice", "instructions": instr,
                "criteria": {str(k): (str(v) if v not in (None, "") else None) for k, v in crit.items()}}
    if t == "score":
        crit = [str(x).strip() for x in (q.get("criteria") or []) if str(x).strip()]
        if not (2 <= len(crit) <= 10) or len(set(crit)) != len(crit):
            raise Bad(f"{where}: score 需要 2-10 个非空且不重复的等级")
        return {"type": "score", "instructions": instr, "criteria": crit}
    if t == "noul":
        c = q.get("criteria") or None
        if isinstance(c, dict):
            true_, false_ = str(c.get("true") or "").strip(), str(c.get("false") or "").strip()
            c = {"true": true_, "false": false_} if (true_ and false_) else None
        else:
            c = None
        return {"type": "noul", "instructions": instr, "criteria": c}
    raise Bad(f"{where}: 未知类型 {t!r}（choice/noul/score）")


def to_sdk(raw: dict) -> dict:
    """raw 形状 → typesafe_sdk 问题对象（kw_only 构造器）。"""
    out = {}
    for qid, q in raw.items():
        if q["type"] == "choice":
            out[qid] = Choice(instructions=q["instructions"], criteria=q["criteria"])
        elif q["type"] == "score":
            out[qid] = Score(instructions=q["instructions"], criteria=q["criteria"])
        else:
            c = q["criteria"]
            out[qid] = Noul(instructions=q["instructions"], criteria=(c if (c and c.get("true") and c.get("false")) else None))
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


# ---------------- 决策模型提供方（可插拔适配层） ----------------
DEFAULT_PROVIDERS = {"providers": [
    {"id": "typesafe", "name": "TypeSafe Jev（官方 API）", "kind": "typesafe", "model_default": "jev-latest"},
    {"id": "openai", "name": "OpenAI Decisions（gpt-6-luna）", "kind": "openai",
     "url": "https://api.openai.com/v1/decisions", "model_default": "gpt-6-luna", "key_env": "OPENAI_API_KEY"},
    {"id": "openrouter", "name": "OpenRouter Decisions（microsoft-decision-1 / jev）", "kind": "compatible",
     "url": "https://openrouter.ai/api/alpha/decisions", "model_default": "microsoft/microsoft-decision-1",
     "key_env": "OPENROUTER_API_KEY"},
    {"id": "jev-compatible", "name": "Jev 兼容端点（改 providers.json 的 url）", "kind": "compatible",
     "url": "http://127.0.0.1:7860/v1/jev", "model_default": "intern-decision-2b", "key_env": ""},
]}
_providers_cache: tuple[float, dict] | None = None  # (mtime, {id: provider})


def load_providers() -> dict:
    """读 providers.json（mtime 热重载，改文件不用重启服务）；坏了回退默认。"""
    global _providers_cache
    try:
        mtime = PROVIDERS_FILE.stat().st_mtime
        if _providers_cache and _providers_cache[0] == mtime:
            return _providers_cache[1]
        data = json.loads(PROVIDERS_FILE.read_text(encoding="utf-8"))
        provs = {}
        for p in data.get("providers") or []:
            pid, kind = str(p.get("id") or "").strip(), str(p.get("kind") or "").strip()
            if not pid or pid in provs or kind not in ("typesafe", "compatible", "openai"):
                continue
            if kind in ("compatible", "openai") and not str(p.get("url") or "").strip():
                continue
            provs[pid] = p
        if "typesafe" not in provs:
            provs["typesafe"] = DEFAULT_PROVIDERS["providers"][0]
        _providers_cache = (mtime, provs)
        return provs
    except FileNotFoundError:
        try:
            PROVIDERS_FILE.write_text(json.dumps(DEFAULT_PROVIDERS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError:
            pass
        return {p["id"]: p for p in DEFAULT_PROVIDERS["providers"]}
    except Exception as e:  # noqa: BLE001
        _log_line(f"providers.json 解析失败，用默认: {e}")
        return {p["id"]: p for p in DEFAULT_PROVIDERS["providers"]}


def _normalize_compatible_answers(answers: dict, questions_raw: dict) -> dict:
    """兼容端点 answers → 前端期望形状（纯函数）。唯一已知差异：OpenRouter 的
    score legend 回传是 {"0": "...", "1": ...} 对象而前端要数组 —— 以本地 criteria
    为权威重建（同 OpenAI 适配器思路）；legend 已是数组（如 Intern-Decision）不动。
    """
    out = {}
    for qid, a in answers.items():
        if isinstance(a, dict) and a.get("type") == "score" and not isinstance(a.get("legend"), list):
            q = questions_raw.get(qid) or {}
            a = {**a, "legend": list(q.get("criteria") or [])}
        out[qid] = a
    return out


def ask_compatible(url: str, key: str, model: str, state, questions_raw: dict,
                   timeout: float = 60.0, auth: str = "bearer") -> dict:
    """裸 HTTP 调 Jev 契约兼容端点（SDK 的路径硬拼 /v1/systemone，指不过去，所以自己发）。

    本地自部署服务通常不需要 key —— 仅在 key 非空时带 Authorization。
    auth="api-key" 时改发 `api-key` 头（Azure Foundry 的 key 认证不用 Bearer）。
    """
    body = {"state": state, "model": model, "questions": questions_raw}
    r = urllib.request.Request(
        url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"})
    if key:
        if auth == "api-key":
            r.add_header("api-key", key)
        else:
            r.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:200]
        except Exception:  # noqa: BLE001
            pass
        raise Bad(f"端点返回 HTTP {e.code}：{detail or e.reason}")
    except urllib.error.URLError as e:
        raise Bad(f"连不上端点 {url}（服务没起来？）：{e.reason}")
    if not isinstance(payload, dict) or not isinstance(payload.get("answers"), dict):
        raise Bad(f"端点返回不是 Jev 契约形状（缺 answers 字段）：{str(payload)[:150]}")
    return {"model": payload.get("model") or model,
            "answers": _normalize_compatible_answers(payload["answers"], questions_raw),
            "usage": payload.get("usage") or {}}


# ---------------- OpenAI Decisions API（gpt-6-luna）适配 ----------------
OPENAI_USD_PER_MTOK = 0.10  # 官方计价：仅输入 token 计费


def _openai_request(state, questions_raw: dict, model: str) -> dict:
    """Jev raw 问题 → OpenAI Decisions 请求体（契约映射，纯函数便于直测）。

    差异：input 是文本（state 序列化注入）；noul→predicate（判据折进 instructions）；
    choice criteria 字典 → choices 数组；score criteria 等级文本 → levels 数组。
    """
    text = state if isinstance(state, str) else json.dumps(state, ensure_ascii=False, indent=2)
    questions = []
    for qid, q in questions_raw.items():
        t, instr = q.get("type"), q.get("instructions")
        if t == "choice":
            item = {"type": "choice", "name": qid, "instructions": instr,
                    "choices": [{"value": k, **({"description": d} if d else {})}
                                for k, d in (q.get("criteria") or {}).items()]}
        elif t == "score":
            item = {"type": "score", "name": qid, "instructions": instr,
                    "levels": [{"label": str(i), "description": lv}
                               for i, lv in enumerate(q.get("criteria") or [])]}
        else:  # noul → predicate（predicate 没有 criteria 字段，判据折进 instructions）
            crit = q.get("criteria") or {}
            parts = [instr]
            if crit.get("true"):
                parts.append(f"Condition is true when: {crit['true']}")
            if crit.get("false"):
                parts.append(f"Condition is false when: {crit['false']}")
            item = {"type": "predicate", "name": qid, "instructions": "\n".join(parts)}
        questions.append(item)
    return {"model": model, "input": text, "questions": questions}


def _openai_normalize(payload: dict, questions_raw: dict) -> dict:
    """OpenAI answers 数组 → 统一 Jev 形状 {id: {...}}（纯函数）。legend 以本地 criteria 为权威。"""
    answers = {}
    for a in payload.get("answers") or []:
        qid, t = a.get("name"), a.get("type")
        if not qid:
            continue
        if t == "predicate":
            answers[qid] = {"type": "noul", "noul": float(a.get("probability") or 0.0)}
        elif t == "choice":
            answers[qid] = {"type": "choice", "choice": a.get("choice"),
                            "probabilities": {str(p.get("value")): float(p.get("probability") or 0.0)
                                              for p in a.get("probabilities") or []}}
            if a.get("confidence") is not None:
                answers[qid]["confidence"] = a["confidence"]
        elif t == "score":
            levels = (questions_raw.get(qid) or {}).get("criteria") or []
            answers[qid] = {"type": "score", "score": a.get("score"),
                            "probabilities": {str(p.get("value")): float(p.get("probability") or 0.0)
                                              for p in a.get("probabilities") or []},
                            "legend": list(levels)}
            if a.get("confidence") is not None:
                answers[qid]["confidence"] = a["confidence"]
        else:  # refusal 等未知类型原样透传（前端显示拒绝提示 + raw JSON）
            answers[qid] = {"type": t or "unknown",
                            **{k: v for k, v in a.items() if k not in ("type", "name")}}
    return {"model": payload.get("model") or "gpt-6-luna", "answers": answers,
            "usage": payload.get("usage") or {}}


def ask_openai(url: str, key: str, model: str, state, questions_raw: dict, timeout: float = 60.0) -> dict:
    """调 OpenAI Decisions API（/v1/decisions，契约与 Jev 不同，这里做双向映射）。"""
    body = _openai_request(state, questions_raw, model)
    r = urllib.request.Request(
        url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:200]
        except Exception:  # noqa: BLE001
            pass
        if e.code == 401:
            raise Bad(f"OpenAI key 无效（HTTP 401）。{detail}")
        if e.code == 429:
            raise Bad(f"触发限流（HTTP 429），稍等重试。{detail}")
        raise Bad(f"OpenAI 返回 HTTP {e.code}：{detail or e.reason}")
    except urllib.error.URLError as e:
        raise Bad(f"连不上 OpenAI 端点 {url}：{e.reason}")
    if not isinstance(payload, dict) or not isinstance(payload.get("answers"), list):
        raise Bad(f"端点返回不是 Decisions 契约形状（缺 answers 数组）：{str(payload)[:150]}")
    return _openai_normalize(payload, questions_raw)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # 只记请求行（方法/路径），绝不记请求体，杜绝 key 泄漏
        _log_line(f"{self.address_string()} {fmt % args}")

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
        self.send_header("Cache-Control", "no-store")  # 页面迭代频繁，避免浏览器拿旧 JS
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlsplit(self.path).path  # 剥掉查询串，/?x 与 / 等价
        if path in ("/", "/index.html"):
            self._static("index.html", "text/html")
        elif path == "/api/health":
            self._send(200, {"ok": True, "key_env": bool(os.environ.get("TYPESAFE_API_KEY"))})
        elif path == "/api/models":
            provs = load_providers()
            self._send(200, {"ok": True, "models": [
                {"id": p["id"], "name": p.get("name") or p["id"], "kind": p.get("kind"),
                 "model_default": p.get("model_default") or "",
                 "needs_key": p.get("kind") == "typesafe" or bool(p.get("key_env")),
                 "key_env": p.get("key_env") or "",
                 "env_key": bool(p.get("key_env") and os.environ.get(str(p["key_env"])))}  # 只报存在性，不回传内容
                for p in provs.values()]})
        elif path == "/api/tasks":
            tasks, harness_ok = [], True
            try:
                tasks = [{"name": k, "description": t.description} for k, t in sorted(harness_tasks().items())]
            except Exception:  # noqa: BLE001  # harness 缺/内存不足时，自建题库仍可用
                harness_ok = False
            tasks += bank_tasks()
            self._send(200, {"ok": True, "tasks": tasks, "harness": harness_ok})
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        path = urlsplit(self.path).path
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            self._send(400, {"ok": False, "error": f"请求体不是合法 JSON: {e}"})
            return
        routes = {
            "/api/pick": do_pick,
            "/api/ask": do_ask,
            "/api/banks": do_bank_save,
            "/api/banks/add_item": do_bank_add_item,
            "/api/banks/delete": do_bank_delete,
        }
        fn = routes.get(path)
        if fn is None:
            self._send(404, {"ok": False, "error": "not found"})
            return
        try:
            code, payload = fn(req)
        except Bad as e:
            code, payload = 400, {"ok": False, "error": str(e)}
        except Exception as e:  # noqa: BLE001
            code, payload = 500, {"ok": False, "error": f"{type(e).__name__}: {e}"}
        self._send(code, payload)


# ---------------- 题库（harness 离线取题） ----------------
_TASKS = None
_tasks_lock = threading.Lock()


_log_lock = threading.Lock()  # 对比模式会并发打 /api/ask，锁住日志行追加


def _log_line(s: str):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {s}"
    with _log_lock:
        print(line, file=sys.stderr)
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


def harness_tasks():
    """懒加载 harness 的全部任务（首次 import datasets 需几秒、>1GB 内存）。"""
    global _TASKS
    with _tasks_lock:
        if _TASKS is None:
            sys.path.insert(0, HARNESS_ROOT)
            from jev_benchmarking.tasks import ALL_TASKS
            _TASKS = dict(ALL_TASKS)
        return _TASKS


def prewarm():
    """启动后后台预热题库，首次取题不再等几十秒；失败不致命（取题时会给明确报错）。"""
    try:
        tasks = harness_tasks()
        t = tasks.get("rotten_tomatoes") or next(iter(tasks.values()))
        t.examples("eval", limit=1)
        _log_line("prewarm done")
    except BaseException as e:  # noqa: BLE001  # MemoryError 也要留下痕迹
        _log_line(f"prewarm failed: {type(e).__name__}: {str(e)[:200]}")


def serialize_example(e) -> dict:
    gold = {k: (sorted(v) if isinstance(v, frozenset) else v) for k, v in e.gold.items()}
    return {"state": e.state, "questions": e.questions, "gold": gold}


def do_pick(req: dict) -> tuple[int, dict]:
    name = str(req.get("task") or "")
    try:
        offset = max(0, min(int(req.get("offset") or 0), 400))
        n = max(1, min(int(req.get("n") or 5), 10))
    except (TypeError, ValueError):
        return 400, {"ok": False, "error": "offset/n 需为整数"}

    if name.startswith("bank:"):  # 自建题库：纯文件读，不依赖 harness
        bname = name[5:]
        try:
            data = load_bank(bname)
        except FileNotFoundError:
            return 404, {"ok": False, "error": f"题库 {bname!r} 不存在"}
        except Bad as e:
            return 400, {"ok": False, "error": str(e)}
        items = (data.get("items") or [])[offset:offset + n]
        return 200, {"ok": True, "task": name, "description": data.get("description") or "",
                     "offset": offset, "items": items,
                     "more": len(data.get("items") or []) >= offset + n}

    try:
        tasks = harness_tasks()
    except Exception as e:  # noqa: BLE001
        return 503, {"ok": False, "error": f"题库加载失败（多半是内存不足，关掉些大程序再点取题）: {type(e).__name__}: {str(e)[:150]}"}
    if name not in tasks:
        return 400, {"ok": False, "error": f"未知任务 {name!r}"}
    t = tasks[name]
    try:
        exs = t.examples("eval", limit=offset + n)
    except Exception as e:  # noqa: BLE001
        return 502, {"ok": False, "error": f"题目加载失败: {type(e).__name__}: {str(e)[:200]}"}
    items = [serialize_example(e) for e in exs[offset:offset + n]]
    return 200, {
        "ok": True, "task": name, "description": t.description,
        "offset": offset, "items": items,
        "more": len(exs) >= offset + n,  # 还有下一批可取
    }


# ---------------- /api/ask（provider 分发） ----------------
def do_ask(req: dict) -> tuple[int, dict]:
    provider_id = str(req.get("provider") or "typesafe")
    prov = load_providers().get(provider_id)
    if prov is None:
        return 400, {"ok": False, "error": f"未知 provider {provider_id!r}（GET /api/models 查看可用）"}
    model = str(req.get("model") or "").strip() or str(prov.get("model_default") or "jev-latest")

    state = req.get("state")
    if isinstance(state, str) and state.strip():
        state = state.strip()
    if not isinstance(state, (dict, list, str)) or state in ({}, [], ""):
        return 400, {"ok": False, "error": "state 不能为空（字符串或 JSON 对象/数组）"}
    try:
        raw = validate_questions(req.get("questions") or [])
    except Bad as e:
        return 400, {"ok": False, "error": str(e)}

    t0 = time.monotonic()
    if prov.get("kind") == "compatible":
        url = str(prov.get("url") or "").strip()
        if not url:
            return 400, {"ok": False, "error": f"provider {provider_id!r} 缺 url（编辑 providers.json）"}
        key = str(req.get("key") or "").strip()
        if not key and prov.get("key_env"):
            key = os.environ.get(str(prov["key_env"]), "")
            if not key:
                return 400, {"ok": False, "error": f"没有 API key：设置环境变量 {prov['key_env']}，或在页面右上角输入（只存你的浏览器）。"}
        try:
            result = ask_compatible(url, key, model, state, raw, auth=str(prov.get("auth") or "bearer"))
        except Bad as e:
            return 400, {"ok": False, "error": str(e)}
        # 自部署端点不计价；托管兼容端点（如 OpenRouter）回真实 usage.cost 就直接用
        real_cost = float((result["usage"] or {}).get("cost") or 0.0)
        return 200, {
            "ok": True, "provider": provider_id, "model": result["model"],
            "latency_ms": round((time.monotonic() - t0) * 1000),
            "usage": result["usage"], "est_cost_usd": round(real_cost, 6) if real_cost > 0 else 0.0,
            "answers": result["answers"],
        }

    # OpenAI Decisions API（gpt-6-luna），$0.10/MTok 仅输入
    if prov.get("kind") == "openai":
        url = str(prov.get("url") or "").strip() or "https://api.openai.com/v1/decisions"
        env_name = str(prov.get("key_env") or "OPENAI_API_KEY")
        key = str(req.get("key") or "").strip() or os.environ.get(env_name, "")
        if not key:
            return 400, {"ok": False, "error": f"没有 API key：设置环境变量 {env_name}，或在页面右上角输入（只存你的浏览器）。"}
        try:
            result = ask_openai(url, key, model, state, raw)
        except Bad as e:
            return 400, {"ok": False, "error": str(e)}
        in_tok = int(result["usage"].get("input_tokens") or 0)
        return 200, {
            "ok": True, "provider": provider_id, "model": result["model"],
            "latency_ms": round((time.monotonic() - t0) * 1000),
            "usage": result["usage"], "est_cost_usd": round(in_tok / 1e6 * OPENAI_USD_PER_MTOK, 6),
            "answers": result["answers"],
        }

    # TypeSafe 官方（SDK 路径，行为与旧版完全一致）
    key = str(req.get("key") or "").strip() or os.environ.get("TYPESAFE_API_KEY", "")
    if not key:
        return 400, {"ok": False, "error": "没有 API key：设置环境变量 TYPESAFE_API_KEY，或在页面右上角输入（只存你的浏览器）。"}
    try:
        with TypeSafeClient(api_key=key, model=model, timeout=60.0) as client:
            resp = client.system_one(state, to_sdk(raw), response_model=RawResponse)
    except Exception as e:  # noqa: BLE001
        code, msg = friendly_error(e)
        return code, {"ok": False, "error": msg}
    body = resp.model_dump()
    usage = body.get("usage") or {}
    in_tok = int(usage.get("input_tokens") or 0)
    return 200, {
        "ok": True, "provider": provider_id, "model": body.get("model") or model,
        "latency_ms": round((time.monotonic() - t0) * 1000),
        "usage": usage, "est_cost_usd": round(in_tok / 1e6 * USD_PER_MTOK, 6),
        "answers": body.get("answers") or {},
    }


# ---------------- 自建题库（banks/*.json 纯文件） ----------------
def _safe_bank_name(name: object) -> str:
    n = "".join(c for c in str(name or "").strip() if c.isalnum() or c in "-_")[:40]
    if not n:
        raise Bad("题库名不能为空（只允许字母数字、-、_，最长 40 字符）")
    return n


def bank_tasks() -> list[dict]:
    """banks/ 目录里的题库列表（坏了的文件跳过，不炸 /api/tasks）。"""
    try:
        BANKS_DIR.mkdir(exist_ok=True)
        out = []
        for p in sorted(BANKS_DIR.glob("*.json")):
            try:
                items = json.loads(p.read_text(encoding="utf-8")).get("items") or []
                if items:
                    out.append({"name": f"bank:{p.stem}", "description": f"📁 自建 · {len(items)} 题"})
            except Exception:  # noqa: BLE001
                continue
        return out
    except Exception:  # noqa: BLE001
        return []


def load_bank(name: str) -> dict:
    path = BANKS_DIR / f"{_safe_bank_name(name)}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise Bad(f"题库 {name!r} 格式不对（缺 items 数组）")
    return data


def _write_bank(name: str, data: dict):
    BANKS_DIR.mkdir(exist_ok=True)
    (BANKS_DIR / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _validate_bank_item(it: object, where: str) -> dict:
    if not isinstance(it, dict):
        raise Bad(f"{where}: 不是对象")
    state = it.get("state")
    if isinstance(state, str):
        state = state.strip()
    if state in (None, "", {}, []):
        raise Bad(f"{where}.state 不能为空")
    qmap = it.get("questions")
    if not isinstance(qmap, dict) or not qmap:
        raise Bad(f"{where}.questions 不能为空（{{id: {{type, instructions, criteria}}}}）")
    qout = {str(qid): validate_raw_question(q, f"{where}.questions[{qid}]") for qid, q in qmap.items()}
    gold = it.get("gold") or {}
    if not isinstance(gold, dict):
        raise Bad(f"{where}.gold 需为对象（{{问题id: 标准答案}}）")
    return {"state": state, "questions": qout, "gold": gold}


def do_bank_save(req: dict) -> tuple[int, dict]:
    """上传/整体替换题库：{name, description?, items: [{state, questions, gold?}]}"""
    name = _safe_bank_name(req.get("name"))
    items_in = req.get("items")
    if not isinstance(items_in, list) or not items_in:
        raise Bad("items 需为非空数组")
    items = [_validate_bank_item(it, f"item[{i}]") for i, it in enumerate(items_in)]
    _write_bank(name, {"name": name, "description": str(req.get("description") or ""), "items": items})
    _log_line(f"bank saved: {name} ({len(items)} items)")
    return 200, {"ok": True, "bank": name, "count": len(items)}


def do_bank_add_item(req: dict) -> tuple[int, dict]:
    """编辑器存题：{bank, state, questions(前端 specs), gold?}；题库不存在则新建。"""
    name = _safe_bank_name(req.get("bank"))
    state = req.get("state")
    if isinstance(state, str):
        state = state.strip()
    if state in (None, "", {}, []):
        raise Bad("state 不能为空")
    raw = validate_questions(req.get("questions") or [])  # 前端 specs → raw（同时完成校验）
    gold = req.get("gold") or {}
    if not isinstance(gold, dict):
        raise Bad("gold 需为对象（{问题id: 标准答案}）")
    path = BANKS_DIR / f"{name}.json"
    if path.exists():
        data = load_bank(name)
        if (data.get("items") or []) and any(not isinstance(x, dict) for x in data["items"]):
            raise Bad(f"题库 {name!r} 现有文件损坏，请先删除再存")
    else:
        data = {"name": name, "description": "", "items": []}
    data.setdefault("items", []).append({"state": state, "questions": raw, "gold": gold})
    _write_bank(name, data)
    _log_line(f"bank add_item: {name} -> {len(data['items'])} items")
    return 200, {"ok": True, "bank": name, "count": len(data["items"])}


def do_bank_delete(req: dict) -> tuple[int, dict]:
    name = _safe_bank_name(req.get("bank"))
    path = BANKS_DIR / f"{name}.json"
    if path.exists():
        path.unlink()
        _log_line(f"bank deleted: {name}")
    return 200, {"ok": True, "bank": name}


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    _log_line(f"SERVER START pid={os.getpid()}  http://{HOST}:{PORT}")
    atexit.register(lambda: _log_line(f"SERVER STOP pid={os.getpid()}"))
    threading.Thread(target=prewarm, daemon=True).start()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    srv.serve_forever()


if __name__ == "__main__":
    main()
