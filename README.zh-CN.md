# Jev Playground

[English](README.md) · **中文**

本地单页应用：自己在浏览器里拼 Choice / Noul / Score 问题，实时调用 [TypeSafe System One](https://docs.typesafe.ai)（Jev）——也可以直接从**37 个公开基准数据集真题库**（[arXiv 2609.37647](https://arxiv.org/abs/2609.37647)）离线取题，自带标准答案对照。

## 启动

```
双击 start.bat        （服务崩溃会自动重启）
  或：  D:\jev\bench\jev-benchmarking\.venv\Scripts\python.exe server.py
```

浏览器打开 <http://127.0.0.1:8770>。前端零框架、零 CDN，完全离线可用。

## API Key

点顶栏 **Key** 打开 key 配置面板：**每个 provider 一把 key**（TypeSafe / OpenAI / OpenRouter / Cloudflare / …），只存在你的浏览器 localStorage，由本地服务内存转发——绝不落盘、绝不写日志。优先级：**页面配置 > 该端点的环境变量**（`TYPESAFE_API_KEY`、`OPENAI_API_KEY`、`OPENROUTER_API_KEY`、`CLOUDFLARE_AUTH_TOKEN`…）；面板里的状态点会显示环境变量是否已设置。对比模式自动给每个选手行带各自 provider 的 key。旧版单一 key 输入框里的值会自动迁移到你当时选中的 provider。

key 在 <https://console.typesafe.ai> / <https://platform.openai.com> / <https://openrouter.ai/keys> / <https://dash.cloudflare.com/profile/api-tokens> 创建。计价（每 MTok 输入，输出免费）：**Jev 与 Microsoft-Decision-1 $0.042、Clef-flash $0.09、OpenAI $0.10、Clef $0.24**，一次典型请求 ≈ $0.0001。页面会显示每次请求的 token 数和估算费用，并有会话累计，可与 console 用量页对账。

## 题库选题（零点击）

40 个任务（37 个基准数据集 + 探针）。打开页面、切换任务都会**自动出题**，「取题」按钮只是备用。点题目行（或行尾「载入」）载入编辑器；发送后结果卡上方显示该题标准答案。数据全部来自本地 HF 缓存——离线、不耗 token。

> 题库依赖磁盘上的 `jev-benchmarking` harness（见 `server.py` 里的 `HARNESS_ROOT`）及其 venv；不可用时 `/api/tasks` 会返回明确报错，不会无声失败。

## 自建题库

除了 40 个基准任务，还能上传自己的题，以纯 JSON 文件存在 `banks/` 目录：

- **上传** — 题库卡上的「上传题库 JSON」按钮接受 `{"name", "description", "items": [{"state", "questions", "gold"}]}` 文件（示例见 `banks/example.json`；形状与 `/api/pick` 返回的一致，零新概念——`questions` 用 raw Jev 形状：choice `criteria={选项:描述}`，score `criteria=[等级]`，noul `criteria=null`）。
- **编辑器存题** — 「存入题库」按钮把编辑器当前内容（state + 问题 + 可选 gold）作为一条新题存进指定题库；题库不存在则自动创建。
- 自建题库在任务下拉里显示为 `bank:<名称> — 📁 自建 · N 题`，同样支持零点击自动出题；完全不依赖 harness 和网络。「删除该题库」按钮删除题库（有确认弹窗）。

## 可插拔决策模型

顶栏下拉框选择「发送」调用的后端：

- **TypeSafe Jev（官方 API）** — 原路径，走 `typesafe_sdk`。
- **OpenAI Decisions（gpt-6-luna）** — OpenAI 的 Decisions API（`POST /v1/decisions`，2026-10-06 起公测）。需要 `OPENAI_API_KEY`（环境变量，或页面输入）。计价 **$0.10/MTok 仅输入**（约为 Jev 的 2.4 倍）。适配器做双向翻译：`noul`→`predicate`、choice criteria 字典→`choices` 数组、score 等级文本→`levels`。注意 OpenAI 的 score 是概率加权浮点，可能落在**两级之间**（前端能正常渲染）；模型拒答的题目会以 `refusal` 答案就地显示。
- **OpenRouter Decisions（microsoft-decision-1 / jev）** —— [Microsoft-Decision-1](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-microsoft-decision)（2026-10-09 发布，Qwen3.5-9B 后训练）说的就是 Jev 契约，直接走「兼容端点」路径。最省事是 [OpenRouter 的 Decisions API](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request)（alpha 阶段）：需要 `OPENROUTER_API_KEY`，model 填 `microsoft/microsoft-decision-1`（该端点也托管 Jev 本尊 `typesafe/jev-1.13`）。计价 **$0.042/MTok 输入、输出免费——与 Jev 完全相同**；真实费用随 `usage.cost` 回传，页面原样显示。也可 Azure Foundry 直连：部署模型后把 `url` 指向 `<资源端点>/providers/microsoft/v1/systemone`，加 `"auth": "api-key"`（Foundry 的 key 走 `api-key` 头、不走 Bearer），`model_default` 填 **deployment 名**。score 行为与 Jev 一致（概率加权浮点，可落两级之间）。
- **Cloudflare Clef（clef / clef-flash）** — Cloudflare 的开源决策模型（[Clef](https://developers.cloudflare.com/workers-ai/models/clef) 27B，2026-10-01 发布；Qwen 后训练），说的就是 **System One 契约原样**（它的 `images[]` 输入是官方标注的 Clef 扩展）。两条路：**OpenRouter** —— 与上面同一个 Decisions 端点，模型名直接填 `cloudflare/clef`（$0.24/MTok）或 `cloudflare/clef-flash`（$0.09），零配置；**Workers AI 直连** —— `url` 填 `https://api.cloudflare.com/client/v4/accounts/<AccountID>/ai/run/@cf/cloudflare/clef`，`key_env: CLOUDFLARE_AUTH_TOKEN`，并加 `"unwrap": "result"`（v4 API 把模型响应包在 `{"success", "result"}` 信封里）和 `"price_in_mtok": 0.24`（按 token 估算费用）。直连的 model 选择器填 `clef` / `clef-flash`（**不带** `cloudflare/` 前缀）。注意：Workers AI 目前会把长文本 state 截断到约前 2K token。
- **Jev 兼容端点** — 任何说 Jev HTTP 契约（`POST {state, model, questions}` → `{model, answers, usage}`）的自部署服务，例如 [Intern-Decision](https://github.com/intern_lm/Intern-Decision)：`bash scripts/demo.sh` 后填 `http://127.0.0.1:7860/v1/jev`。回传 `usage.cost` 的托管兼容端点（如 OpenRouter）显示真实费用而非 0；已知单价的端点可配 `price_in_mtok` 按 token 估算。

端点配置在 `providers.json`（首跑自动生成，热重载——改完不用重启；`providers.example.json` 是格式示例）。每个 provider：`id`、`kind`（`typesafe`/`openai`/`compatible`）、`url`、`model_default`、可选 `key_env`（存 API key 的**环境变量名**——文件里绝不放 key 本身；key 优先级：页面输入 > key_env 指定的环境变量）、可选 `auth`（Azure Foundry 直连用 `"api-key"`，默认 Bearer）、可选 `unwrap`（API 把响应包在信封里时下钻的键——Cloudflare Workers AI 直连用 `"result"`）、可选 `price_in_mtok`（每 MTok 输入的美元单价，端点不回 `usage.cost` 时按 token 估算费用）。没配 `key_env` 的兼容端点免认证（页面手动输入的 key 仍会带 `Authorization` 头）；配了 `key_env` 的端点解析不到 key 时直接报友好错误。

## 模型对比

顶栏 **对比** 按钮切换对比模式：provider/模型/key 控件隐藏，出现选手列表——每行是 *provider + 模型名*（因此也能比同端点的多个模型，比如 OpenRouter 上的 `microsoft/microsoft-decision-1` 对 `typesafe/jev-1.13` 对 `cloudflare/clef`）。「发送」把同一题目并行发给所有勾选行，渲染成**问题为行、模型为列**的网格：答案、概率条、延迟、token、费用并排；某个模型出错只显示红色 ❌ 列和错误信息，不影响其余列。每行自动带上各自 provider 在 Key 面板配置的 key（没有则落回该端点的环境变量）；每个模型各计一次费，会话累计如实相加。

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
- `README.md` — 英文版说明（GitHub 首页显示）
