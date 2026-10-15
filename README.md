# Jev Playground

**English** · [中文](#中文)

Local single-page app: compose your own Choice / Noul / Score questions in the browser and call [TypeSafe System One](https://docs.typesafe.ai) (Jev) live — or pull **real questions from a 37-dataset public benchmark** ([arXiv 2609.37647](https://arxiv.org/abs/2609.37647)) straight from the local offline cache, with gold answers to compare against.

## Quick start

```
double-click start.bat        (auto-restarts if the server crashes)
  or:  D:\jev\bench\jev-benchmarking\.venv\Scripts\python.exe server.py
```

Then open <http://127.0.0.1:8770>. No JS framework, no CDN, fully offline frontend.

## API key (pick one)

1. **Recommended** — set the env var before starting:
   ```
   set TYPESAFE_API_KEY=tsk-...      (cmd)
   $env:TYPESAFE_API_KEY="tsk-..."   (PowerShell)
   ```
2. Or paste it into the box at the top-right of the page (stored only in your browser's localStorage; the server forwards it in memory and never writes it to disk or logs).

Create keys at <https://console.typesafe.ai>. Pricing: **$0.042 / MTok input, output free** — a typical request costs ≈ $0.0001. The page shows per-request tokens & estimated cost, plus a session counter you can reconcile against the console usage page.

## Question bank (zero-click)

Pick from 40 tasks (37 public benchmark datasets + probes). Opening the page and switching tasks **auto-fetches** a batch of real questions — the 取题 button is optional. Click any item (or its 载入↓ button) to load it into the editor; after sending, the gold answer appears above the result card. Everything is served from the local HuggingFace cache — offline, zero tokens.

> Requires the `jev-benchmarking` harness on disk (see `HARNESS_ROOT` in `server.py`) plus its venv; if unavailable, `/api/tasks` returns a clear error instead of failing silently.

## Custom question banks

Beyond the 40 benchmark tasks you can bring your own questions, stored as plain JSON files in `banks/`:

- **Upload** — the ⬆ button on the bank card accepts a `{"name", "description", "items": [{"state", "questions", "gold"}]}` file (see `banks/example.json`; same shape `/api/pick` returns, zero new concepts — `questions` uses the raw Jev shape: choice `criteria={option: desc}`, score `criteria=[levels]`, noul `criteria=null`).
- **Save from editor** — the 存入题库 button stores whatever is currently in the editor (state + questions + optional gold) as a new item in a bank of your choosing; creates the bank if it doesn't exist.
- Custom banks show up in the task dropdown as `📁 name — 自建` and work with zero-click auto-pick; they never touch the harness or the network. 🗑 deletes a bank (with confirm).

## Pluggable decision models

The header dropdown picks the backend for 发送:

- **TypeSafe Jev（官方 API）** — the original path via `typesafe_sdk`.
- **Jev 兼容端点** — any self-hosted service speaking the Jev HTTP contract (`POST {state, model, questions}` → `{model, answers, usage}`), e.g. [Intern-Decision](https://github.com/intern_lm/Intern-Decision) via `bash scripts/demo.sh` on `http://127.0.0.1:7860/v1/jev`.

Endpoints are configured in `providers.json` (auto-created on first run, hot-reloaded — edit it without restarting; `providers.example.json` shows the schema). Per provider: `id`, `kind` (`typesafe`/`compatible`), `url`, `model_default`, and optional `key_env` (name of an env var holding the API key — the file itself must never contain key values; for the official provider the page input takes precedence, then `TYPESAFE_API_KEY`). Compatible endpoints need no key by default — the `Authorization` header is only sent when a key resolves.

## Built-in templates

Templates marked *paper-frozen* use the exact question wording from the benchmark harness (verified: this repo's author reproduced all 37/37 results offline).

| Template | Primitive | Note |
|---|---|---|
| Sentiment · IMDB/SST-2 | Choice(2) | paper accuracy 0.965 |
| News topic · AG News | Choice(4) | 0.885 |
| NLI · ANLI | Choice(3) | 0.739 |
| Knowledge · MMLU | Choice(4) | 0.918 (0.943 on math — suspected train exposure) |
| SMS spam | Noul | F1 0.938 |
| Grounding · LLM-AggreFact | Noul | balanced acc 0.786, RAG scenario |
| Similarity · STS-B | Score(6) | Spearman 0.890 |
| Language ID (20-way) | Choice(20) | 0.996, try Chinese |
| GoEmotions-style multi-label | Noul ×7 | fan-out demo: multi-label Nouls over-report yes |
| Custom | any | state as JSON, unlimited questions |

## Reading results

- **Choice**: answer + probability bar per option (top highlighted) + confidence (distribution concentration, *not* correctness)
- **Noul**: P(yes) on a 0–1 bar with the 0.5 threshold marked; ≈0.5 means "fifty-fifty", not "medium intensity"
- **Score**: probability-weighted position on the rubric scale + per-level probabilities + full level texts

Questions in one request are judged **independently, in parallel** (fan-out) — one request, one input-token charge.

## Layout

- `server.py` — stdlib `http.server` + `typesafe_sdk`; `POST /api/ask`, `GET /api/tasks` `/api/health`, `POST /api/pick`; logs request lines only (method/path) to `requests.log` — never bodies or keys
- `static/index.html` — the whole frontend in one file
- `start.bat` — launcher with crash auto-restart

---

# 中文

本地单页应用：自己在浏览器里拼 Choice / Noul / Score 问题，实时调用 [TypeSafe System One](https://docs.typesafe.ai)（Jev）——也可以直接从**37 个公开基准数据集真题库**（[arXiv 2609.37647](https://arxiv.org/abs/2609.37647)）离线取题，自带标准答案对照。

## 启动

```
双击 start.bat        （服务崩溃会自动重启）
  或：  D:\jev\bench\jev-benchmarking\.venv\Scripts\python.exe server.py
```

浏览器打开 <http://127.0.0.1:8770>。前端零框架、零 CDN，完全离线可用。

## API Key（二选一）

1. **推荐** — 启动前设环境变量：
   ```
   set TYPESAFE_API_KEY=tsk-...      （cmd）
   $env:TYPESAFE_API_KEY="tsk-..."   （PowerShell）
   ```
2. 或直接在页面右上角输入框粘贴（只存在你的浏览器 localStorage；服务器仅在内存中转发，绝不落盘、绝不写日志）。

key 在 <https://console.typesafe.ai> 创建。计价：**输入 $0.042/MTok，输出免费**，一次典型请求 ≈ $0.0001。页面会显示每次请求的 token 数和估算费用，并有会话累计，可与 console 用量页对账。

## 题库选题（零点击）

40 个任务（37 个基准数据集 + 探针）。打开页面、切换任务都会**自动出题**，「取题」按钮只是备用。点题目行（或行尾「载入↓」）载入编辑器；发送后结果卡上方显示该题标准答案。数据全部来自本地 HF 缓存——离线、不耗 token。

> 题库依赖磁盘上的 `jev-benchmarking` harness（见 `server.py` 里的 `HARNESS_ROOT`）及其 venv；不可用时 `/api/tasks` 会返回明确报错，不会无声失败。

## 自建题库

除了 40 个基准任务，还能上传自己的题，以纯 JSON 文件存在 `banks/` 目录：

- **上传** — 题库卡上的 ⬆ 按钮接受 `{"name", "description", "items": [{"state", "questions", "gold"}]}` 文件（示例见 `banks/example.json`；形状与 `/api/pick` 返回的一致，零新概念——`questions` 用 raw Jev 形状：choice `criteria={选项:描述}`，score `criteria=[等级]`，noul `criteria=null`）。
- **编辑器存题** — 「存入题库」按钮把编辑器当前内容（state + 问题 + 可选 gold）作为一条新题存进指定题库；题库不存在则自动创建。
- 自建题库在任务下拉里显示为 `📁 名称 — 自建`，同样支持零点击自动出题；完全不依赖 harness 和网络。🗑 删除题库（有确认弹窗）。

## 可插拔决策模型

顶栏下拉框选择「发送」调用的后端：

- **TypeSafe Jev（官方 API）** — 原路径，走 `typesafe_sdk`。
- **Jev 兼容端点** — 任何说 Jev HTTP 契约（`POST {state, model, questions}` → `{model, answers, usage}`）的自部署服务，例如 [Intern-Decision](https://github.com/intern_lm/Intern-Decision)：`bash scripts/demo.sh` 后填 `http://127.0.0.1:7860/v1/jev`。

端点配置在 `providers.json`（首跑自动生成，热重载——改完不用重启；`providers.example.json` 是格式示例）。每个 provider：`id`、`kind`（`typesafe`/`compatible`）、`url`、`model_default`、可选 `key_env`（存 API key 的**环境变量名**——文件里绝不放 key 本身；官方 provider 的 key 优先级：页面输入 > `TYPESAFE_API_KEY`）。兼容端点默认无需 key——只有解析到 key 时才发 `Authorization` 头。

## 内置模板

带「论文冻结模板」标记的提问文本与基准 harness 逐字一致（本仓库作者已离线复现论文 37/37 全部结果）。

| 模板 | 原语 | 说明 |
|---|---|---|
| 情感二分类 · IMDB/SST-2 | Choice(2) | 论文 accuracy 0.965 |
| 新闻四分类 · AG News | Choice(4) | 0.885 |
| 自然语言推理 · ANLI | Choice(3) | 0.739 |
| 四选一知识题 · MMLU | Choice(4) | 0.918（计算类 0.943，疑训练暴露） |
| 垃圾短信 · SMS Spam | Noul | F1 0.938 |
| 接地检查 · LLM-AggreFact | Noul | balanced acc 0.786，RAG 场景 |
| 语义相似度 · STS-B | Score(6) | Spearman 0.890 |
| 语言识别（20 选 1） | Choice(20) | 0.996，可试中文 |
| 多标签情绪 · GoEmotions 风格 | Noul×7 | fan-out 演示：多标签会过报 yes |
| 自定义 | 任意 | state 用 JSON 编辑，可加任意多个问题 |

## 读结果

- **Choice**：答案 + 全选项概率条（最高亮绿）+ 置信度（分布集中度，不是正确率）
- **Noul**：P(yes) 0-1 刻度条，虚线标 0.5 阈值；≈0.5 是"五五开"不是"中等程度"
- **Score**：概率加权分在 rubric 刻度上的位置 + 各级概率 + 等级全文

同一请求里的多个问题**并行独立**求值（fan-out），只按一次请求计输入 token。

## 结构

- `server.py` — stdlib `http.server` + `typesafe_sdk`；`POST /api/ask`、`GET /api/tasks` `/api/health`、`POST /api/pick`；只把请求行（方法/路径）记进 `requests.log`——绝不记请求体和 key
- `static/index.html` — 全部前端（单文件）
- `start.bat` — 启动器，崩溃自动重启
