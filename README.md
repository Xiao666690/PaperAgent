# 🚀 AgentHub

<p align="center">
<b>Enterprise Multi-Agent Intelligence Platform</b>
</p>

<p align="center">
基于 LangGraph 的企业级多智能体智能应用平台
</p>

<p align="center">

LangGraph · LangChain · RAG · Tool Calling · LLM Agent

</p>


---

# 中文介绍


# 📖 项目简介


**AgentHub** 是一个基于大语言模型（Large Language Model, LLM）的企业级多智能体智能应用平台。

项目基于 **LangGraph + LangChain** 构建统一 Agent Runtime，通过多智能体协同（Multi-Agent Collaboration）、知识增强检索（Retrieval-Augmented Generation, RAG）、工具调用（Tool Calling）以及记忆管理（Memory System）等核心技术，实现面向企业和个人用户的智能应用开发平台。


AgentHub 提供两种核心运行模式：

```
Chat Mode
开放领域智能助手

Work Mode
企业内部智能工作空间
```


其中：

- **Chat Mode** 面向开放领域智能交互，提供类似 ChatGPT 的通用智能助手能力。
- **Work Mode** 面向企业内部业务场景，结合企业知识库和业务工具，实现企业级智能办公。


AgentHub 致力于构建一个：

> 可扩展、可部署、可定制的企业级 AI Agent 基础设施平台。


---

# ✨ 核心功能


# 1. 双模式智能 Agent 系统


## 💬 Chat Mode


Chat Mode 是面向外部用户的通用智能助手模式。


主要能力：

- 通用知识问答
- 代码生成
- 学术研究辅助
- 外部知识检索
- 多轮智能对话


系统架构：

```
User

 ↓

Chat Supervisor Agent

 ↓

Specialized Agents

 ↓

LLM + Tools

 ↓

Final Response
```


支持扩展 Agent：

- QA Agent
- Code Agent
- Research Agent
- Search Agent


---

# 🏢 Work Mode


Work Mode 是面向企业内部员工的智能工作空间。


主要能力：

- 企业知识库问答
- 员工手册查询
- 企业文档分析
- HR 智能助手
- OA 流程助手
- 企业业务自动化


系统架构：

```
Employee

 ↓

Work Supervisor Agent

 ↓

Enterprise Agents

 ↓

Enterprise Knowledge Base

 ↓

Answer
```


支持扩展 Agent：

- OA Agent
- HR Agent
- Document Agent
- Workflow Agent


---

# 2. Multi-Agent 智能体协同


AgentHub 基于 **LangGraph** 构建多智能体工作流。


通过 Supervisor Agent 实现：

- 用户意图理解
- 复杂任务拆解
- Agent 动态选择
- 工作流调度
- 多 Agent 结果融合


示例：

```
User Request

      |

Supervisor Agent

      |

----------------------

|          |           |

Search   Code     Research

Agent    Agent      Agent

      |

Final Answer

```


---

# 3. RAG 知识增强系统


为了降低大语言模型幻觉问题，AgentHub 集成完整的 Retrieval-Augmented Generation Pipeline。


整体流程：

```
Documents

    |

Document Parser

    |

Chunk Splitter

    |

Embedding Model

    |

Vector Database

    |

Retriever

    |

LLM Generation

```


支持：

- PDF 文档解析
- 企业知识库构建
- 文档语义检索
- 基于知识证据的回答生成


核心技术：

- BGE-M3 Embedding
- ChromaDB
- LangChain Retriever


---

# 4. Agent Tool Calling


AgentHub 支持智能体主动调用外部工具完成复杂任务。


工作流程：

```
User

 ↓

LLM Reasoning

 ↓

Tool Selection

 ↓

Tool Execution

 ↓

Observation

 ↓

Final Answer
```


支持工具：

- 搜索工具
- 数据库查询
- 文档检索
- 企业业务接口
- 自动化工作流


---

# 5. Memory 系统


AgentHub 支持多层级智能体记忆。


## Short-term Memory


用于保存：

- 当前对话上下文
- 当前任务状态


技术：

- LangGraph Checkpoint


---

## Long-term Memory


用于保存：

- 用户偏好
- 历史任务
- 企业知识


提升长期智能交互能力。


---

# 🏗 系统架构


```
                         AgentHub


                            |

                 LangGraph Agent Runtime


                            |

          -----------------------------------

          |                                 |

      Chat Mode                        Work Mode


          |                                 |

  Chat Supervisor              Work Supervisor


          |                                 |

 ----------------          ---------------------

 |       |       |          |        |         |

QA    Code   Research      OA      HR     Document

Agent Agent    Agent      Agent  Agent    Agent


          |

          |

     Tool System + RAG + Memory


          |

          |

        LLM Gateway


 DeepSeek / GPT / Qwen / Ollama

```


---

# 🛠 技术栈


## Agent Framework

- LangGraph
- LangChain
- Multi-Agent Architecture
- Supervisor Agent


## Large Language Model

- DeepSeek API
- OpenAI API
- Qwen
- Ollama


## Retrieval-Augmented Generation

- RAG
- BGE-M3 Embedding
- ChromaDB
- Vector Retrieval


## Backend

- FastAPI
- Uvicorn
- AsyncIO
- Pydantic


## Frontend

- Next.js
- React
- TypeScript
- Ant Design
- Tailwind CSS


## Database

- SQLite
- SQLAlchemy


---

# 🚀 快速开始


## Backend


进入后端目录：

```bash
cd backend
```


安装依赖：

```bash
uv sync
```


启动虚拟环境：

```bash
source .venv/bin/activate
```


启动服务：

```bash
cd app

python run_server.py
```


默认：

```
http://localhost:8000
```


---

# Frontend


进入前端目录：

```bash
cd frontend
```


安装依赖：

```bash
pnpm install
```


启动：

```bash
pnpm dev
```


默认：

```
http://localhost:3000
```


---

# 🗺 Roadmap


## Phase 1：Agent Runtime

完成：

- LangGraph Agent Runtime
- Multi-Agent Workflow
- LLM Integration


---

## Phase 2：Chat Mode


计划：

- Search Agent
- Code Agent
- Research Agent
- External Knowledge Retrieval


---

## Phase 3：Work Mode


计划：

- Enterprise Knowledge Base
- OA Agent
- HR Agent
- Document Agent
- Workflow Automation


---

## Phase 4：Enterprise Platform


计划：

- Agent Marketplace
- Permission Management
- Workflow Builder
- Agent Evaluation System


---

# 🌟 项目愿景


AgentHub 希望成为企业级 AI Agent 基础设施平台。


通过连接：

```
LLM

+

Knowledge

+

Tools

+

Workflow

+

Memory

```


帮助企业快速构建：

- 可靠的智能助手
- 自动化业务流程
- 企业知识管理系统
- 个性化 AI 应用


---

<br>

<br>


#  English Introduction


# 🚀 AgentHub

## Enterprise Multi-Agent Intelligence Platform


AgentHub is an enterprise-oriented AI Agent platform built with **LangGraph and LangChain**.


It provides a unified runtime for building intelligent applications by integrating:


- Large Language Models
- Multi-Agent Collaboration
- Retrieval-Augmented Generation
- Tool Calling
- Memory Management


AgentHub supports two major operation modes:


```
Chat Mode

Open-domain AI Assistant


Work Mode

Enterprise AI Workspace
```


---

# ✨ Features


# 1. Dual Agent Modes


## Chat Mode


A general-purpose AI assistant for open-domain tasks.


Capabilities:

- Knowledge Q&A
- Code generation
- Research assistance
- External knowledge retrieval
- Multi-turn conversation


Architecture:


```
User

 ↓

Chat Supervisor Agent

 ↓

Specialized Agents

 ↓

LLM + Tools

 ↓

Response
```


---

## Work Mode


An enterprise AI workspace designed for internal business scenarios.


Capabilities:

- Employee handbook QA
- Enterprise document understanding
- HR assistant
- OA workflow assistant
- Internal knowledge management


Architecture:


```
Employee

 ↓

Work Supervisor Agent

 ↓

Enterprise Agents

 ↓

Enterprise Knowledge Base

 ↓

Answer
```


---

# 2. Multi-Agent Collaboration


AgentHub uses LangGraph to orchestrate multiple specialized agents.


Supervisor Agent handles:


- Intent understanding
- Task decomposition
- Agent routing
- Workflow execution
- Result aggregation


---

# 3. Retrieval-Augmented Generation


AgentHub integrates RAG pipeline to reduce LLM hallucination.


Pipeline:


```
Documents

 ↓

Parsing

 ↓

Chunking

 ↓

Embedding

 ↓

Vector Database

 ↓

Retrieval

 ↓

LLM Generation
```


Technologies:

- BGE-M3 Embedding
- ChromaDB
- LangChain Retriever


---

# 4. Agent Tool Calling


Agents can dynamically invoke external tools.


Workflow:


```
User

 ↓

LLM Reasoning

 ↓

Tool Selection

 ↓

Tool Execution

 ↓

Observation

 ↓

Final Answer
```


Supported tools:

- Search
- Database Query
- Document Retrieval
- Enterprise APIs
- Workflow Automation


---

# 5. Memory System


AgentHub supports intelligent memory management.


## Short-term Memory

Maintains:

- Conversation context
- Task states


Powered by:

- LangGraph Checkpoint


---

## Long-term Memory

Stores:

- User preferences
- Historical interactions
- Enterprise knowledge


---

# 🏗 Architecture


```
                        AgentHub


                           |

              LangGraph Agent Runtime


                           |

        ---------------------------------

        |                               |

    Chat Mode                      Work Mode


        |                               |

Chat Supervisor              Work Supervisor


        |                               |

 Specialized Agents        Enterprise Agents


        |

 Tool System + RAG + Memory


        |

 LLM Gateway

DeepSeek / GPT / Qwen / Ollama

```


---

# 🛠 Technology Stack


## Agent Framework

- LangGraph
- LangChain


## LLM

- DeepSeek
- OpenAI
- Qwen
- Ollama


## RAG

- BGE-M3
- ChromaDB
- Vector Retrieval


## Backend

- FastAPI
- AsyncIO
- Pydantic


## Frontend

- Next.js
- React
- TypeScript


## Database

- SQLite
- SQLAlchemy


---

# 🚀 Quick Start


## Backend


```bash
cd backend

uv sync

source .venv/bin/activate

cd app

python run_server.py
```


## Frontend


```bash
cd frontend

pnpm install

pnpm dev
```


---

# 🗺 Roadmap


## Phase 1

- LangGraph Runtime
- Multi-Agent Workflow
- LLM Integration


## Phase 2

Chat Mode:

- Search Agent
- Code Agent
- Research Agent


## Phase 3

Work Mode:

- Enterprise Knowledge Base
- OA Agent
- HR Agent
- Document Agent


## Phase 4

Enterprise Platform:

- Agent Marketplace
- Permission Management
- Workflow Automation
- Agent Evaluation


---

# 🌟 Vision


AgentHub aims to become an enterprise AI Agent infrastructure platform by connecting:


```
LLM

+

Knowledge

+

Tools

+

Workflow

+

Memory

```


to build reliable and scalable intelligent applications.
