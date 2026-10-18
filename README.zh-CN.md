# Jev Playground
[English](README.md) · **中文**

本地单页应用：在浏览器里编排 Choice / Noul / Score 问题并调用决策模型 API —— 或从 37 个数据集的离线基准（[arXiv 2609.37647](https://arxiv.org/abs/2609.37647)）抽取真题，附带标准答案。

## 功能

**出题**

- 每个问题三种原语：Choice（2–255 个选项，可选描述）、Noul（可选 true/false 判据）、Score（2–10 个不重复等级）——一个请求内自由混用。
- 10 个内置模板，其中 8 个论文冻结（措辞与基准评测提问完全一致），下拉框下方显示各自的论文指标。
- state 双模式编辑：模板按字段分框；自定义模板与载入的题库条目整体按 JSON 编辑。
- 增删问题卡片、原地切换问题原语（保留 id 与 instructions）、选项自动编号 A、B … Z、AA；Ctrl/Cmd+Enter 全页发送。

**基准题库**

- 来自 37 个数据集基准 harness 的真题，完全从本地 HuggingFace 缓存离线提供 —— 取题零 token 花费。
- 零点击：打开页面或切换任务即自动出题；取题 从头重取，服务器报告还有更多时显示 下一批，每次前进 5 题。
- 编号条目行带 state 预览（悬停显示完整 JSON）；点击行或其 载入 按钮即载入编辑器。
- 发送载入的条目后，结果上方出现标准答案横幅；横幅始终带有提示：若你在发送前改过题目，标准答案可能不再适用。

**自建题库**

- 上传题库 JSON 上传/整体替换题库文件；存入题库 把当前编辑器条目（可带标准答案）追加进题库；删除该题库 确认后删除题库。
- 题库是 `banks/` 下可直接手改的纯 JSON 文件，在任务下拉框中显示为 `bank:<名称> — 📁 自建 · N 题`；不依赖 harness 与网络也能用。

**决策模型接入**

- 三种 provider kind：`typesafe`（官方 SDK）、`openai`（双向契约翻译）、`compatible`（向任意 `url` 发原生 Jev 契约 HTTP；本地服务无需 key）。
- `providers.json` 首次运行自动生成默认配置，并按 mtime 热重载 —— 改端点不用重启服务。
- typesafe 路由的友好错误映射：401 key 无效、402 余额不足、429 限流、5xx → 可重试的 502；openai/compatible 直接展示端点自身的状态码与报错。
- 页头 provider 下拉框 + 模型名输入框（预填该 provider 的默认模型，刷新后保持）用于单模式发送时选定目标。

**模型对比**

- 对比 模式把同一份负载并行打向每个勾选的模型 —— 每个模型一次请求、各计一次费。
- 单一网格：问题为行、模型为列，每列带延迟、输入 token 与估算费用；出错模型得到红色 ❌ 列，不影响其他模型。

**Key 与隐私**

- Key 面板（页头 Key 按钮）：每个 provider 一把 key，只存在本浏览器的 localStorage，由本地服务在内存中转发 —— 绝不落盘、绝不进日志。
- 处处一致的优先级：页面 key > 该 provider 的 `key_env` 环境变量；`requests.log` 只记录请求行（方法/路径）与服务生命周期事件，绝不记录请求体或 key。

**费用统计**

- 每个结果显示延迟、输入 token 与估算费用（只按输入计价，输出免费；典型请求 ≈ $0.0001）；会话计数器累计所有成功发送的 次数 · token · 美元 —— 对比模式下按模型逐个累计。

## 支持的决策模型

| 模型 | 接入方式 | API key | 价格（每 MTok 输入） | 备注 |
|---|---|---|---|---|
| TypeSafe Jev（`jev-latest`） | 官方 API，走 `typesafe_sdk`（[文档](https://docs.typesafe.ai)） | `TYPESAFE_API_KEY` | $0.042，输出免费 | 默认 provider；响应体原样保留 |
| OpenAI Decisions（`gpt-6-luna`） | `https://api.openai.com/v1/decisions`（kind `openai`） | `OPENAI_API_KEY` | $0.10，输出免费 | 契约双向翻译（noul↔predicate、criteria↔choices、levels）；拒绝回答原样展示 |
| Microsoft-Decision-1 | [OpenRouter](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request) `microsoft/microsoft-decision-1`，或 [Azure Foundry](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-microsoft-decision) 直连 | `OPENROUTER_API_KEY` / `AZURE_API_KEY` | $0.042，输出免费 | 原生说 Jev 契约；Foundry 需 `"auth": "api-key"` 且 `model_default` = 部署名 |
| OpenRouter 上的 Jev（`typesafe/jev-1.13`） | OpenRouter Decisions（kind `compatible`） | `OPENROUTER_API_KEY` | $0.042，输出免费 | 真实单次费用随 `usage.cost` 返回并原样展示 |
| Cloudflare Clef 27B（`clef`）/ `clef-flash` | OpenRouter `cloudflare/clef` / `cloudflare/clef-flash`；或 [Workers AI](https://developers.cloudflare.com/workers-ai/models/clef) 直连（`"unwrap": "result"`） | `OPENROUTER_API_KEY` / `CLOUDFLARE_AUTH_TOKEN` | Clef $0.24，clef-flash $0.09 | 直连路由：模型名去掉 `cloudflare/` 前缀，`price_in_mtok` 估算费用；Workers AI 会截断长 state（约 2K token） |
| 任意 Jev 兼容端点 | 自定义 `url`，例如 [Intern-Decision](https://github.com/intern_lm/Intern-Decision) 的 `http://127.0.0.1:7860/v1/jev` | 无（自部署） | 自部署免费 | 原生 POST `{state, model, questions}`；仅当存在 key 时才加 Authorization 头 |

以上路由都在 `providers.example.json` 里给出了示例（typesafe、openai、openrouter、intern、azure-foundry、cloudflare）—— 见[端点配置](#端点配置)。

## 启动

```
双击 start.bat        （崩溃自动重启；关闭窗口即停止）
  或：  D:\jev\bench\jev-benchmarking\.venv\Scripts\python.exe server.py
```

打开 <http://127.0.0.1:8770>。服务只绑定 127.0.0.1，用标准库 `http.server`（ThreadingHTTPServer，支持对比模式并发）；唯一真正的依赖是 bench venv 里的 `pydantic` 与 `typesafe_sdk`。启动时有守护线程后台预热 harness 注册表，但首次切到某任务仍可能要几十秒缓存。

## API Key

点击页头 **Key**：每个 provider 一行，带状态点、环境变量名与密码输入框。key 只存在本浏览器的 localStorage（`jev_key_<provider>`），由本地服务在内存中转发 —— 绝不落盘、绝不进日志。优先级：**页面 key > 该 provider 的环境变量**（`TYPESAFE_API_KEY`、`OPENAI_API_KEY`、`OPENROUTER_API_KEY`、`AZURE_API_KEY`、`CLOUDFLARE_AUTH_TOKEN` …）；任一配置好状态点即变绿，对比模式下会点名还缺 key 的 provider。在 <https://console.typesafe.ai> / <https://platform.openai.com> / <https://openrouter.ai/keys> / <https://dash.cloudflare.com/profile/api-tokens> 创建 key。

## 题库选题（零点击）

题库卡片列出全部 harness 任务（名称 + 描述）与你的自建题库。打开页面即自动取第一批，切换任务又自动出题 —— 全程零点击；取题 从 offset 0 重取，下一批（仅当还有更多时显示）每次前进 5 题。点击条目行（或其 载入 按钮）把 state + 问题载入编辑器并平滑滚动过去；发送后绿色横幅显示该任务的标准答案。全部内容读自本地 HF 缓存（`HF_HUB_OFFLINE=1`），取题离线且免费。需要磁盘上有 `jev-benchmarking` harness（`server.py` 里的 `HARNESS_ROOT`；首次导入耗时数秒且 >1 GB 内存）；若加载失败，`/api/tasks` 返回 `harness:false`，自建题库仍可用。

## 自建题库

- `banks/`（与 `server.py` 同目录）下的纯 JSON 文件：`{name, description, items: [{state, questions, gold}]}` —— 见 `banks/example.json`。`questions` 用原生 Jev 形状（choice `criteria={选项: 描述}`，score `criteria=[等级]`，noul `criteria=null`）。
- 上传题库 JSON —— 上传或整体替换一个题库（逐条校验）。
- 存入题库 —— 把当前编辑器条目（state + questions + 可选 gold 对象）追加进题库，题库不存在则创建。
- 题库在任务下拉框中显示为 `bank:<名称> — 📁 自建 · N 题`，并加入零点击自动出题；删除该题库 确认后删除。
- 名称保留 Unicode 字母/数字及 `-`/`_`（最长 40 字符）；损坏的题库文件被跳过，一个坏文件拖不垮任务列表。只有 `banks/example.json` 入库 —— 其余 gitignore。

## 端点配置

`providers.json` 与 `server.py` 同目录（gitignore；首次运行自动生成默认配置，typesafe provider 缺失时会被强制恢复）。按 mtime 热重载 —— 改完保存即生效，无需重启；文件损坏时回落到内置默认。`providers.example.json` 即字段文档：

- `id`（必填、唯一）、`kind`（必填：`typesafe` / `openai` / `compatible`）、`name`（显示名，缺省回落到 id）
- `url` —— `compatible`/`openai` 必填（缺 `url` 的 `openai` 条目会在加载时被跳过）
- `model_default` —— 解析链：请求 `model` → `model_default` → `jev-latest`
- `key_env` —— 存 key 的环境变量名；留空或缺省 = 无需 key（本地部署）。绝不把 key 值写进文件。
- `auth` —— `"api-key"` 时改用 `api-key` 头发送 key（Azure Foundry）
- `unwrap` —— API 包装响应时要钻取的键（Cloudflare v4：`"result"`）
- `price_in_mtok` —— 每百万输入 token 的美元单价，端点不回传 `usage.cost` 时用于估算费用

## 模型对比

页头 对比 按钮切换对比模式（刷新后保持）。每个 provider 自动建一行选手；＋ 添加选手 追加行。每行 = 参与勾选框 + provider + 模型名（预填该 provider 的默认模型）。发送请求 把同一份 state/questions 并行打向每个勾选行，渲染一个网格 —— 问题为行、模型为列，每列表头显示 provider、模型、延迟、输入 token 与估算费用；单元格渲染与单模式相同的可视化，出错的模型得到红色 ❌ 表头与错误消息、单元格显示占位横线。每行带各自 provider 的页面 key（服务端落回其环境变量）；每个模型各计一次费，各模型的原始 JSON 在网格下方的折叠区里。

## 内置模板

论文冻结模板使用基准 harness 的原版提问措辞（绿色徽章）；下拉框下方一行注释显示各模板的论文指标。

| 模板 | 原语 | 论文指标 |
|---|---|---|
| 情感二分类 · IMDB/SST-2 | Choice(2) | accuracy 0.965（n=25,000） |
| 新闻四分类 · AG News | Choice(4) | accuracy 0.885 |
| 自然语言推理 · ANLI | Choice(3) | accuracy 0.739（R1 81.4% → R3 67.7%） |
| 知识题 · MMLU | Choice(4) | accuracy 0.918；计算类 0.943（论文疑训练暴露） |
| 垃圾短信 · SMS Spam | Noul | F1 0.938 |
| 接地检查 · LLM-AggreFact | Noul | balanced accuracy 0.786 |
| 语义相似度 · STS-B | Score(6) | Spearman 0.890 |
| 语言识别（20 选 1） | Choice(20) | accuracy 0.996 —— 试试中文 |
| GoEmotions 风格多标签 | Noul ×7 | fan-out 演示；多标签 Noul 会过报 yes，阈值需上调 |
| 自定义 | 任意 | state 按 JSON 编辑，问题数不限 |

MMLU 在发送前把 A/B/C/D 四个 state 字段并入选项描述；GoEmotions 模板把一个 state 字段扇出为 7 个并行 Noul 问题。同一请求内的问题并行独立求值（fan-out）—— 一次请求、一次输入 token 计费。

## 读结果

- **Choice** —— 答案行 + 各选项概率条（降序，最高者着色并标 ◁）与置信度条：分布集中度，*不是*正确性。
- **Noul** —— `P(yes)` 及其口头读数（>0.65 倾向 是，<0.35 倾向 否，≈0.5 五五开 —— 不是「中等程度」），0–1 条上带 0.5 虚线阈值。
- **Score** —— 概率加权的 `X.XX / n` 落在带刻度的滑轨上，配各级概率条，折叠区里是各级全文。
- 拒绝回答显示警告与原始 JSON；每张结果卡带已发送请求与完整原始响应的折叠区，新卡插在旧卡上方。

## 结构

- `server.py` —— 标准库 `http.server` 后端（支持并发）：校验、provider 路由、计价估算；JSON API `/api/ask`、`/api/pick`、`/api/banks*`、`/api/health`、`/api/models`、`/api/tasks`
- `static/index.html` —— 整个前端单文件；页面版本戳证明刷新后拿到的是最新页面
- `providers.example.json` → 复制/调整为 `providers.json`（实际配置，gitignore）
- `banks/` —— 自建题库；只有 `example.json` 入库
- `start.bat` —— 崩溃自动重启的启动器，复用 `D:\jev\bench` venv 的 python；服务地址 <http://127.0.0.1:8770>
- `requests.log` —— 记录请求行（方法/路径）及服务/题库生命周期事件（启动/停止、预热、题库保存/删除），绝不记录请求体或 key；gitignore
- `README.md` / `README.zh-CN.md` —— 中英双语 README
