# PaperQuery

PaperQuery 是一个面向论文阅读、论文知识库管理和多模型问答的 AI Agent 应用。项目支持上传 PDF 论文，将论文切分为向量知识库，并通过 RAG 检索把相关论文片段注入大模型上下文，实现基于论文内容的问答、翻译、笔记和多文件 Chat。

## 功能亮点

- **Library 论文知识库**：支持创建知识库、上传 PDF、查看处理状态、按标签和文件名检索论文。
- **后台异步向量化**：上传文件后由 `vector.py` 独立完成 PDF 解析、文本切分、摘要生成和 ChromaDB 向量入库。
- **Reader 问答助手**：在 PDF 阅读页内对当前论文提问，基于当前论文 `documentID` 做单文件 RAG 检索。
- **多模型 Chat**：支持 DeepSeek、Kimi K3、OpenAI 三类 OpenAI-compatible Chat API，并可在前端切换。
- **多文件 RAG 对话**：Chat 页面可绑定多篇论文，把多个 `documentID` 传给后端进行跨论文检索问答。
- **SSE 流式回答**：后端使用 Server-Sent Events 流式返回模型输出，前端边接收边渲染。
- **模型切换上下文压缩**：切换模型时压缩近期对话和当前论文信息，降低跨模型切换造成的上下文漂移。
- **会话可追踪体验**：前端记录历史会话快照，展示会话标题、模型、绑定论文和更新时间。
- **错误可观测性**：流式接口和 Reader 问答增加异常兜底，模型调用失败时向前端返回可读错误。

## 技术栈

**Frontend**

- Vue 3
- TypeScript
- Vite
- Pinia
- Vuex
- Vue Router
- Element Plus
- Tailwind CSS
- Markdown-it
- highlight.js
- Fetch ReadableStream / SSE

**Backend**

- Python
- FastAPI
- Uvicorn
- SQLAlchemy
- SQLite
- LangChain
- ChromaDB
- PyMuPDF
- Tencent Cloud TMT
- JWT

**AI / Agent**

- DeepSeek Chat API
- Kimi K3 API
- OpenAI-compatible Chat Completions API
- RAG
- Embedding
- Vector Search
- Context Compression
- Multi-model Routing

## 项目结构

```text
PaperQuery/
├── PaperQuery_Frontend/      # Vue 3 前端
├── PaperQuery_Backend/       # FastAPI 后端和向量化任务
├── chat_highlight.md         # Chat / Library 优化记录
└── README.md
```

## 本地运行

### 1. 后端配置

```powershell
cd PaperQuery_Backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirement.txt
copy .env.example .env
```

编辑 `.env`，填入模型和翻译服务配置：

```env
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://api.deepseek.com
KIMI_API_KEY=
KIMI_API_BASE=https://api.moonshot.cn/v1
OPENAI_API_KEY=
OPENAI_API_BASE=
TENCENT_SECRET_ID=
TENCENT_SECRET_KEY=
```

启动后端 API：

```powershell
python main.py
```

默认监听：

```text
http://127.0.0.1:8001
```

### 2. 启动文档向量化后台任务

另开一个终端：

```powershell
cd PaperQuery_Backend
.\.venv\Scripts\activate
python vector.py
```

`vector.py` 不监听端口，它会持续扫描数据库中 `documentStatus=0` 的文档并进行 PDF 解析、向量化和状态更新。

### 3. 前端配置

```powershell
cd PaperQuery_Frontend
npm install
copy config\.env.example config\.env.dev
npm run dev -- --host 127.0.0.1
```

如果 `8080` 被占用，Vite 会自动切换到其他端口，例如：

```text
http://127.0.0.1:8081
```

## 运行说明

- 本项目不需要本地部署聊天大模型。
- 本地负责 PDF 解析、向量检索、RAG 上下文构建和接口编排。
- DeepSeek、Kimi K3、OpenAI 的回答由远程 API 生成。
- ChromaDB 会在本地缓存一个 ONNX embedding 模型，用于论文向量检索，这不是聊天大模型。
- 上传 PDF 后，必须保持 `vector.py` 运行，否则 Library 页面会停留在“排队中”。

## 核心流程

```text
上传 PDF
  -> 写入 SQLite 文档记录
  -> vector.py 异步解析 PDF
  -> 文本切分与 embedding
  -> 写入 ChromaDB
  -> 更新文档状态为完成
  -> Chat / Reader 问答按 documentID 检索相关片段
  -> 拼接上下文调用大模型
  -> SSE 流式返回答案
```

## 已优化内容

- 修复 Kimi K3 `temperature` 参数兼容问题。
- 为多模型 Chat 增加模型切换提示和系统消息。
- 增加 Chat 顶部当前论文上下文提示。
- 删除无实际功能的导出按钮。
- 增加右侧历史会话面板。
- 增加模型切换时的上下文压缩。
- 修复 Reader 问答 SSE 半包解析导致的空白回答。
- 限制 Library 只有处理完成的文档才能进入 View 问答。
- 将 ChromaDB ONNX 缓存移动到项目目录，避免 Windows 用户目录权限问题。
- 移除硬编码密钥，统一改为 `.env` 配置。

## 简历描述

设计并优化 PaperQuery 多模型论文问答 Agent，基于 Vue3 + Pinia + FastAPI + SSE + LangChain + ChromaDB 实现多论文 RAG、流式问答、多模型路由、上下文压缩和历史会话管理；修复 Kimi K3 API 参数兼容、文档向量化后台任务稳定性和 SSE 流式解析问题，提升论文问答系统的可用性、可解释性和工程稳定性。
