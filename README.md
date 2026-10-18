# Jev Playground
**English** · [中文](README.zh-CN.md)

Local single-page app: compose Choice / Noul / Score questions in the browser and call decision-model APIs — or pull real questions from a 37-dataset offline benchmark ([arXiv 2609.37647](https://arxiv.org/abs/2609.37647)), gold answers included.

## Features

**Composing questions**

- Three primitives per question: Choice (2–255 options with optional descriptions), Noul (optional true/false criteria), Score (2–10 unique levels) — mixed freely in one request.
- 10 built-in templates; 8 are paper-frozen (wording identical to the benchmark evaluation prompts) and show their paper metric under the dropdown.
- Dual-mode state editing: labeled field boxes for templates; pretty-printed JSON for the custom template and loaded bank items.
- Add/remove question cards, switch a question's primitive in place (id and instructions preserved), auto-lettered options A, B … Z, AA; Ctrl/Cmd+Enter sends from anywhere.

**Benchmark question bank**

- Real questions from the 37-dataset benchmark harness, served fully offline from the local HuggingFace cache — fetching costs zero tokens.
- Zero-click: opening the page or switching a task auto-fetches a batch; 取题 refetches from the start, 下一批 advances by 5 when the server reports more.
- Numbered item rows with a state preview (full JSON on hover); click a row or its 载入 button to load it into the editor.
- After sending a loaded item, a gold-answer banner appears above the results; the banner always carries a caveat that the gold answer may not apply if you edited the question before sending.

**Custom banks**

- 上传题库 JSON uploads/replaces a whole bank file; 存入题库 appends the current editor item with optional gold; 删除该题库 removes a bank after confirmation.
- Banks are plain, hand-editable JSON files in `banks/`, listed as `bank:<名称> — 📁 自建 · N 题`; they work without the harness or the network.

**Decision-model providers**

- Three provider kinds: `typesafe` (official SDK), `openai` (two-way contract translation), `compatible` (raw Jev-contract HTTP to any `url`; local services need no key).
- `providers.json` is auto-created with defaults on first run and hot-reloaded by mtime — edit providers without restarting the server.
- Friendly error mapping on the typesafe route: 401 invalid key, 402 insufficient balance, 429 rate-limited, 5xx → retryable 502; openai/compatible endpoints surface their raw HTTP status in the error message.
- Header provider dropdown + model-name input (pre-filled from `model_default`, remembered across reloads) picks the target for single-model sends.

**Model comparison**

- 对比 mode fires the identical payload at every checked model in parallel — one request per model, each billed separately.
- One grid: questions as rows, models as columns, with latency, input tokens and estimated cost per column; a failed model gets a red ❌ column instead of breaking the others.

**Keys & privacy**

- Key panel (header Key button): one key per provider, stored only in this browser's localStorage, forwarded in memory by the local server — never written to disk or logs.
- Precedence everywhere: page key > the provider's `key_env` env var; `requests.log` records request lines (method/path) plus server lifecycle events — never bodies or keys.

**Cost tracking**

- Every result shows latency, input tokens and estimated cost (input-only pricing, output free; a typical request ≈ $0.0001); a session counter accumulates requests · tokens · dollars across all successful sends — per model in compare mode.

## Supported decision models

| Model | How to reach it | API key | Price (per MTok input) | Notes |
|---|---|---|---|---|
| TypeSafe Jev (`jev-latest`) | Official API via `typesafe_sdk` ([docs](https://docs.typesafe.ai)) | `TYPESAFE_API_KEY` | $0.042, output free | Default provider; response body preserved as-is |
| OpenAI Decisions (`gpt-6-luna`) | `https://api.openai.com/v1/decisions` (kind `openai`) | `OPENAI_API_KEY` | $0.10, output free | Contract translated both ways (noul↔predicate, criteria↔choices, levels); refusals shown inline |
| Microsoft-Decision-1 | [OpenRouter](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request) `microsoft/microsoft-decision-1`, or [Azure Foundry](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-microsoft-decision) direct | `OPENROUTER_API_KEY` / `AZURE_API_KEY` | $0.042, output free | Speaks the Jev contract verbatim; Foundry needs `"auth": "api-key"` and `model_default` = deployment name |
| Jev on OpenRouter (`typesafe/jev-1.13`) | OpenRouter Decisions (kind `compatible`) | `OPENROUTER_API_KEY` | $0.042, output free | Real per-request cost arrives in `usage.cost` and is shown as-is |
| Cloudflare Clef 27B (`clef`) / `clef-flash` | OpenRouter `cloudflare/clef` / `cloudflare/clef-flash`; or [Workers AI](https://developers.cloudflare.com/workers-ai/models/clef) direct (`"unwrap": "result"`) | `OPENROUTER_API_KEY` / `CLOUDFLARE_AUTH_TOKEN` | Clef $0.24, clef-flash $0.09 | Direct route: model name without `cloudflare/` prefix, `price_in_mtok` for the cost estimate; Workers AI truncates long state (~2K tokens) |
| Any Jev-compatible endpoint | Your own `url`, e.g. [Intern-Decision](https://github.com/intern_lm/Intern-Decision) at `http://127.0.0.1:7860/v1/jev` | none (self-hosted) | free when self-hosted | Raw POST `{state, model, questions}`; Authorization header only added if a key exists |

All routes are wired up as examples in `providers.example.json` (typesafe, openai, openrouter, intern, azure-foundry, cloudflare) — see [Provider configuration](#provider-configuration).

## Quick start

```
double-click start.bat        (crash auto-restart; close the window to stop)
  or:  D:\jev\bench\jev-benchmarking\.venv\Scripts\python.exe server.py
```

Open <http://127.0.0.1:8770>. The server binds to 127.0.0.1 only and is stdlib `http.server` (ThreadingHTTPServer, so compare-mode concurrency works); the only real dependencies are `pydantic` and `typesafe_sdk` from the bench venv. A daemon thread prewarms the harness registry at startup, but the first switch to a task can still take tens of seconds to cache.

## API key

Click **Key** in the header: one row per provider with a status dot, the env-var name and a password input. Keys live only in this browser's localStorage (`jev_key_<provider>`) and are forwarded in memory by the local server — never written to disk or logs. Precedence: **page key > the provider's env var** (`TYPESAFE_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `AZURE_API_KEY`, `CLOUDFLARE_AUTH_TOKEN`, …); the dot turns green when either is set and, in compare mode, names exactly which providers still lack keys. Create keys at <https://console.typesafe.ai> / <https://platform.openai.com> / <https://openrouter.ai/keys> / <https://dash.cloudflare.com/profile/api-tokens>.

## Question bank (zero-click)

The bank card lists all harness tasks (name + description) plus your custom banks. Opening the page auto-fetches the first batch and switching a task auto-picks again — no clicks needed; 取题 refetches from offset 0 and 下一批 (only shown when more is available) advances by 5. Clicking a row (or its 载入 button) loads state + questions into the editor and scrolls there; after sending, a green banner shows the task's gold answer. Everything is read from the local HF cache (`HF_HUB_OFFLINE=1`), so fetching is offline and free. Requires the `jev-benchmarking` harness on disk (`HARNESS_ROOT` in `server.py`; first import takes seconds and >1 GB RAM); if it fails to load, `/api/tasks` returns `harness:false` and your custom banks still work.

## Custom question banks

- Plain JSON files in `banks/` next to `server.py`: `{name, description, items: [{state, questions, gold}]}` — see `banks/example.json`. `questions` uses the raw Jev shape (choice `criteria={option: desc}`, score `criteria=[levels]`, noul `criteria=null`).
- 上传题库 JSON — upload or replace an entire bank (validated per item).
- 存入题库 — append the current editor item (state + questions + optional gold object) to a bank, creating the bank if absent.
- Banks appear in the task dropdown as `bank:<名称> — 📁 自建 · N 题` and join the zero-click auto-pick; 删除该题库 deletes one after confirmation.
- Names keep Unicode letters/digits plus `-`/`_` (max 40 chars); corrupt bank files are skipped so one bad file can't break the task list. Only `banks/example.json` is committed — the rest are gitignored.

## Provider configuration

`providers.json` sits next to `server.py` (gitignored; auto-created with defaults on first run, and the typesafe provider is force-restored if missing). It hot-reloads by mtime — edit and save, no restart; a corrupt file falls back to the built-in defaults. `providers.example.json` documents the schema:

- `id` (required, unique), `kind` (required: `typesafe` / `openai` / `compatible`), `name` (display name, falls back to id)
- `url` — required for `compatible`/`openai` (an `openai` entry without `url` is skipped at load time)
- `model_default` — resolution chain: request `model` → `model_default` → `jev-latest`
- `key_env` — name of the env var holding the key; empty or absent = no key needed (local deployments). Never put key values in the file.
- `auth` — `"api-key"` sends the key in an `api-key` header instead of Bearer (Azure Foundry)
- `unwrap` — response key to drill into when the API wraps payloads (Cloudflare v4: `"result"`)
- `price_in_mtok` — USD per MTok input, for cost estimates when the endpoint doesn't return `usage.cost`

## Model comparison

The header 对比 button toggles compare mode (persisted across reloads). One contender row is created per provider; ＋ 添加选手 adds more. Each row is a participation checkbox + provider + model name (pre-filled with that provider's default). 发送请求 fires the identical state/questions at every checked row in parallel and renders one grid — questions as rows, models as columns, each column header showing provider, model, latency, input tokens and estimated cost; cells render the same visualizations as single mode, and a model that errors gets a red ❌ header with its message and dash cells. Every row carries its own provider's page key (falling back server-side to its env var); each model is billed separately, and per-model raw JSON sits in collapsibles under the grid.

## Built-in templates

Paper-frozen templates use the exact question wording from the benchmark harness (green badge); the note line under the dropdown shows each one's paper metric.

| Template | Primitive | Paper metric |
|---|---|---|
| Sentiment · IMDB/SST-2 | Choice(2) | accuracy 0.965 (n=25,000) |
| News topic · AG News | Choice(4) | accuracy 0.885 |
| NLI · ANLI | Choice(3) | accuracy 0.739 (R1 81.4% → R3 67.7%) |
| Knowledge · MMLU | Choice(4) | accuracy 0.918; 0.943 on math (suspected train exposure) |
| SMS spam | Noul | F1 0.938 |
| Grounding · LLM-AggreFact | Noul | balanced accuracy 0.786 |
| Similarity · STS-B | Score(6) | Spearman 0.890 |
| Language ID (20-way) | Choice(20) | accuracy 0.996 — try Chinese |
| GoEmotions-style multi-label | Noul ×7 | fan-out demo; multi-label Noul over-reports yes, raise thresholds |
| Custom | any | state as JSON, unlimited questions |

MMLU merges the A/B/C/D state fields into the option descriptions before sending; the GoEmotions template fans one state field out to 7 parallel Noul questions. Questions in one request are judged independently and in parallel (fan-out) — one request, one input-token charge.

## Reading results

- **Choice** — answer line plus per-option probability bars (sorted, top tinted and marked ◁) and a confidence bar: distribution concentration, *not* correctness.
- **Noul** — `P(yes)` with a reading (>0.65 leans yes, <0.35 leans no, ≈0.5 is fifty-fifty — not "medium intensity") on a 0–1 bar with a dashed 0.5 threshold.
- **Score** — probability-weighted `X.XX / n` on a labeled rail, per-level probability bars, and the full level texts in a collapsible legend.
- Refusals show a warning plus the raw JSON; every card carries collapsibles with the sent request and the full raw response, and new cards prepend above older ones.

## Layout

- `server.py` — stdlib `http.server` backend (concurrent): validation, provider routing, pricing estimation; JSON API `/api/ask`, `/api/pick`, `/api/banks*`, `/api/health`, `/api/models`, `/api/tasks`
- `static/index.html` — the entire frontend in one file; the page-version stamp proves you got the latest page after a refresh
- `providers.example.json` → copy/adjust to `providers.json` (live config, gitignored)
- `banks/` — custom question banks; only `example.json` is committed
- `start.bat` — launcher with crash auto-restart, reuses the `D:\jev\bench` venv python; serves <http://127.0.0.1:8770>
- `requests.log` — request lines (method/path) plus server/bank lifecycle events (start/stop, prewarm, bank save/delete); never bodies or keys; gitignored
- `README.md` / `README.zh-CN.md` — bilingual READMEs
