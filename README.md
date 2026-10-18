# Jev Playground

**English** · [中文](README.zh-CN.md)

Local single-page app: compose your own Choice / Noul / Score questions in the browser and call [TypeSafe System One](https://docs.typesafe.ai) (Jev) live — or pull **real questions from a 37-dataset public benchmark** ([arXiv 2609.37647](https://arxiv.org/abs/2609.37647)) straight from the local offline cache, with gold answers to compare against.

## Quick start

```
double-click start.bat        (auto-restarts if the server crashes)
  or:  D:\jev\bench\jev-benchmarking\.venv\Scripts\python.exe server.py
```

Then open <http://127.0.0.1:8770>. No JS framework, no CDN, fully offline frontend.

## API key

Click **Key** in the header to open the key panel: **one key per provider** (TypeSafe / OpenAI / OpenRouter / Cloudflare / …), stored only in your browser's localStorage and forwarded in memory by the local server — never written to disk or logs. Precedence: **page key > the provider's env var** (`TYPESAFE_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `CLOUDFLARE_AUTH_TOKEN`, …); the panel's status dot shows whether an env var is already set. Compare mode automatically sends each contender row its own provider's key. Keys from the old single-key box are migrated to the provider you had selected.

Create keys at <https://console.typesafe.ai> / <https://platform.openai.com> / <https://openrouter.ai/keys> / <https://dash.cloudflare.com/profile/api-tokens>. Pricing per MTok input (output free): **Jev & Microsoft-Decision-1 $0.042, Clef-flash $0.09, OpenAI $0.10, Clef $0.24** — a typical request costs ≈ $0.0001. The page shows per-request tokens & estimated cost, plus a session counter you can reconcile against the console usage page.

## Question bank (zero-click)

Pick from 40 tasks (37 public benchmark datasets + probes). Opening the page and switching tasks **auto-fetches** a batch of real questions — the 取题 button is optional. Click any item (or its 载入 button) to load it into the editor; after sending, the gold answer appears above the result card. Everything is served from the local HuggingFace cache — offline, zero tokens.

> Requires the `jev-benchmarking` harness on disk (see `HARNESS_ROOT` in `server.py`) plus its venv; if unavailable, `/api/tasks` returns a clear error instead of failing silently.

## Custom question banks

Beyond the 40 benchmark tasks you can bring your own questions, stored as plain JSON files in `banks/`:

- **Upload** — the 上传题库 JSON button on the bank card accepts a `{"name", "description", "items": [{"state", "questions", "gold"}]}` file (see `banks/example.json`; same shape `/api/pick` returns, zero new concepts — `questions` uses the raw Jev shape: choice `criteria={option: desc}`, score `criteria=[levels]`, noul `criteria=null`).
- **Save from editor** — the 存入题库 button stores whatever is currently in the editor (state + questions + optional gold) as a new item in a bank of your choosing; creates the bank if it doesn't exist.
- Custom banks show up in the task dropdown as `bank:<name> — 📁 自建 · N 题` and work with zero-click auto-pick; they never touch the harness or the network. The 删除该题库 button deletes a bank (with confirm).

## Pluggable decision models

The header dropdown picks the backend for 发送:

- **TypeSafe Jev（官方 API）** — the original path via `typesafe_sdk`.
- **OpenAI Decisions（gpt-6-luna）** — OpenAI's Decisions API (`POST /v1/decisions`, public beta since Oct 6 2026). Needs `OPENAI_API_KEY` (env var, or paste in the page). Priced at **$0.10/MTok input-only** (~2.4× Jev). The adapter translates both ways: `noul`→`predicate`, choice criteria dict→`choices` array, score level texts→`levels`. Note OpenAI's score is a probability-weighted float that can fall *between* two levels (the frontend renders that fine); a question the model declines becomes a `refusal` answer shown inline.
- **OpenRouter Decisions（microsoft-decision-1 / jev）** — [Microsoft-Decision-1](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-microsoft-decision) (released Oct 9 2026, post-trained from Qwen3.5-9B) speaks the Jev contract verbatim, so it runs on the *compatible* path. Easiest route is [OpenRouter's Decisions API](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request) (alpha): needs `OPENROUTER_API_KEY`, model `microsoft/microsoft-decision-1` (Jev itself is hosted there as `typesafe/jev-1.13` too). Priced at **$0.042/MTok input, output free — identical to Jev**; the real per-request cost arrives in `usage.cost` and is displayed as-is. Azure Foundry direct works too: deploy the model, point `url` at `<resource-endpoint>/providers/microsoft/v1/systemone`, add `"auth": "api-key"` (Foundry keys go in the `api-key` header, not Bearer) and set `model_default` to your **deployment name**. Same Jev-style score behavior (probability-weighted float, can fall between levels).
- **Cloudflare Clef（clef / clef-flash）** — Cloudflare's open-source decision models ([Clef](https://developers.cloudflare.com/workers-ai/models/clef) 27B, released Oct 1 2026; fine-tunes of Qwen) speak the System One contract **verbatim** (their `images[]` input is a documented Clef extension of it). Two routes: **OpenRouter** — same Decisions endpoint as above, just use model `cloudflare/clef` ($0.24/MTok) or `cloudflare/clef-flash` ($0.09), zero config; or **Workers AI direct** — point `url` at `https://api.cloudflare.com/client/v4/accounts/<AccountID>/ai/run/@cf/cloudflare/clef` with `key_env: CLOUDFLARE_AUTH_TOKEN` and add `"unwrap": "result"` (the v4 API wraps the model response in a `{"success", "result"}` envelope) plus `"price_in_mtok": 0.24` so the cost display estimates from tokens. Direct model selector is `clef` / `clef-flash` (**no** `cloudflare/` prefix). Note: Workers AI currently truncates long text state to roughly the first 2K tokens.
- **Jev 兼容端点** — any self-hosted service speaking the Jev HTTP contract (`POST {state, model, questions}` → `{model, answers, usage}`), e.g. [Intern-Decision](https://github.com/intern_lm/Intern-Decision) via `bash scripts/demo.sh` on `http://127.0.0.1:7860/v1/jev`. Hosted compatible endpoints that return `usage.cost` (e.g. OpenRouter) show the real cost instead of the default $0; endpoints with a known price can set `price_in_mtok` for a token-based estimate.

Endpoints are configured in `providers.json` (auto-created on first run, hot-reloaded — edit it without restarting; `providers.example.json` shows the schema). Per provider: `id`, `kind` (`typesafe`/`openai`/`compatible`), `url`, `model_default`, optional `key_env` (name of an env var holding the API key — the file itself must never contain key values; key precedence: page input, then the `key_env` variable), optional `auth` (`"api-key"` for Azure Foundry–style header auth; default Bearer), optional `unwrap` (key to descend into when the API wraps responses — Cloudflare Workers AI direct uses `"result"`), and optional `price_in_mtok` (USD per MTok input, for cost estimation when the endpoint doesn't return `usage.cost`). Compatible endpoints without `key_env` need no auth — a key typed into the page is still sent as `Authorization`; endpoints with `key_env` fail fast with a friendly message when no key resolves.

## Model comparison

The **对比** button in the header switches to compare mode: the provider/model/key controls hide and a contender list appears — each row is *provider + model name* (so you can also pit several models of the same endpoint against each other, e.g. `microsoft/microsoft-decision-1` vs `typesafe/jev-1.13` vs `cloudflare/clef` on OpenRouter). 发送 fires the same questions at every checked row in parallel and renders one grid with **questions as rows, models as columns**: answers, probability bars, latency, tokens and cost side by side; a model that errors gets a red ❌ column with the message instead of breaking the others. Each row automatically carries its own provider's key from the Key panel (falling back to that endpoint's env var); each model is billed separately — the session counter reflects that.

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
- `README.zh-CN.md` — the Chinese version of this README
