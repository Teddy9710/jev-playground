# Jev Playground

本地单页应用：自己输入题目，实时调用 TypeSafe System One（Jev）看类型化答案。

## 启动

```
双击 start.bat
（或）D:\jev\bench\jev-benchmarking\.venv\Scripts\python.exe server.py
```

浏览器打开 <http://127.0.0.1:8770>。

## API Key（二选一）

1. **推荐**：启动前设环境变量
   ```
   set TYPESAFE_API_KEY=tsk-...   （cmd）
   $env:TYPESAFE_API_KEY="tsk-..." （PowerShell）
   ```
2. 或直接在页面右上角输入框粘贴（只存在你的浏览器 localStorage，服务器只在内存中转发，不落盘、不打日志）。

key 在 <https://console.typesafe.ai> 创建。计价：输入 $0.042/MTok，输出免费，一次典型请求约 $0.0001。

## 内置模板

| 模板 | 原语 | 说明 |
|---|---|---|
| 情感二分类 · IMDB/SST-2 | Choice(2) | 论文 accuracy 0.965 |
| 新闻四分类 · AG News | Choice(4) | 0.885 |
| 自然语言推理 · ANLI | Choice(3) | 0.739 |
| 四选一知识题 · MMLU | Choice(4) | 0.918（计算类 0.943，疑训练暴露） |
| 垃圾短信 · SMS Spam | Noul | F1 0.938 |
| 接地检查 · LLM-AggreFact | Noul | balanced acc 0.786，RAG 场景 |
| 语义相似度 · STS-B | Score(6) | Spearman 0.890 |
| 语言识别 · Language ID | Choice(20) | 0.996，可试中文 |
| 多标签情绪 · GoEmotions 风格 | Noul×7 | fan-out 演示：多标签会过报 yes |
| 自定义 | 任意 | state 用 JSON 编辑，可加任意多个问题 |

带「论文冻结模板」标记的提问文本逐字取自 `jev-benchmarking` harness
（arXiv 2609.37647，本机已 37/37 复现其全部结果），所以你测的就是论文同款提问方式。

## 读结果

- **Choice**：答案 + 全选项概率条（最高亮绿）+ 置信度（分布集中度，不是正确率）
- **Noul**：P(yes) 0-1 刻度条，虚线标 0.5 阈值；≈0.5 是"五五开"不是"中等程度"
- **Score**：概率加权分在 rubric 刻度上的位置 + 各级概率 + 等级全文

同一请求里的多个问题**并行独立**求值（fan-out），只按一次请求计输入 token。

## 结构

- `server.py` — stdlib http.server + typesafe_sdk；POST /api/ask，GET /api/health
- `static/index.html` — 全部前端（无框架、无 CDN、离线可用）
- 依赖：`D:\jev\bench\jev-benchmarking\.venv`（里面有 typesafe_sdk）
