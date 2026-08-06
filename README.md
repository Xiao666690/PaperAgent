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

# 🇨🇳 中文介绍 | Chinese Introduction


## 📖 项目简介


**AgentHub** 是一个基于大语言模型（LLM）的企业级多智能体应用平台。

项目基于 **LangGraph + LangChain** 构建统一 Agent Runtime，通过多智能体协同、知识增强检索（RAG）、工具调用（Tool Calling）以及记忆管理（Memory）等技术，实现面向企业和个人用户的智能应用开发平台。


AgentHub 提供两种核心工作模式：


Chat Mode
开放领域智能助手

Work Mode
企业内部智能工作空间



其中：

- Chat Mode 面向外部通用智能交互
- Work Mode 面向企业内部知识管理和业务自动化


目标是构建一个可扩展、可部署、可定制的企业级 AI Agent 基础设施。


---

# ✨ 核心功能


## 1. 双模式智能 Agent 系统


## 💬 Chat Mode


面向开放领域的通用 AI 助手。


支持：

- 通用知识问答
- 代码生成
- 学术研究辅助
- 外部知识检索
- 多轮智能对话


架构：


User

↓

Chat Supervisor Agent

↓

Specialized Agents

↓

LLM + Tools

↓

Final Response




---

## 🏢 Work Mode


面向企业内部场景的智能工作空间。


支持：

- 企业知识库问答
- 员工手册查询
- 企业文档分析
- HR智能助手
- OA流程助手


架构：


Employee

↓

Work Supervisor Agent

↓

Enterprise Agents

↓

Enterprise Knowledge Base

↓

Answer



---

# 2. Multi-Agent 智能体协同


AgentHub 基于 **LangGraph** 构建多智能体工作流。


通过 Supervisor Agent 实现：

- 用户意图识别
- 任务拆解
- Agent选择
- 工作流调度
- 结果整合


示例：



User Request

  |

Supervisor Agent

  |

| | |

Search Code Research

Agent Agent Agent

  |

Final Answer



---

# 3. RAG 知识增强系统


为了降低大语言模型幻觉问题，AgentHub 集成完整 RAG Pipeline。


流程：


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



支持：

- PDF文档解析
- 企业知识库构建
- 语义检索
- 基于知识证据的回答生成


技术：

- BGE-M3 Embedding
- ChromaDB
- LangChain Retriever


---

# 4. Agent Tool Calling


AgentHub 支持智能体主动调用外部工具。


工作流程：


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



支持扩展：

- 搜索工具
- 数据库查询
- 文档检索
- 企业业务接口
- 自动化工作流


---

# 5. Memory 系统


AgentHub 支持多层级智能体记忆。


## Short-term Memory

短期上下文：

- 当前对话
- 当前任务状态


技术：

- LangGraph Checkpoint


---

## Long-term Memory

长期用户记忆：

- 用户偏好
- 历史任务
- 企业知识


用于提升长期交互体验。


---

# 🏗 系统架构


                     AgentHub


                        |

             LangGraph Agent Runtime


                        |

      -----------------------------------

      |                                 |

  Chat Mode                        Work Mode


      |                                 |

Chat Supervisor Work Supervisor

      |                                 |

| | | | | |

QA Code Research OA HR Document

Agent Agent Agent Agent Agent Agent

      |

      |

 Tool System + RAG + Memory


      |

      |

    LLM Gateway

DeepSeek / GPT / Qwen / Ollama




---

# 🛠 技术栈


## Agent Framework

- LangGraph
- LangChain
- Multi-Agent Architecture


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

安装依赖：

uv sync

启动环境：

source .venv/bin/activate

启动服务：

cd app

python run_server.py

默认：

http://localhost:8000
Frontend

进入前端目录：

cd frontend

安装依赖：

pnpm install

启动：

pnpm dev

默认：

http://localhost:3000
🗺 Roadmap
Phase 1

✅ LangGraph Agent Runtime

✅ Multi-Agent Workflow

✅ LLM Integration

Phase 2

🚧 Chat Mode Enhancement

Search Agent
Code Agent
Research Agent
Phase 3

🚧 Work Mode

Enterprise Knowledge Base
OA Agent
HR Agent
Document Agent
Phase 4

🚧 Enterprise Platform

Agent Marketplace
Permission System
Workflow Automation
Agent Evaluation
🌟 项目愿景

AgentHub 希望成为企业级 AI Agent 基础设施平台。

通过连接：

LLM

+

Knowledge

+

Tools

+

Workflow

+

Memory


帮助企业快速构建可靠、可扩展的智能应用。

<br> <br>
🇺🇸 English Introduction
🚀 AgentHub
Enterprise Multi-Agent Intelligence Platform

AgentHub is an enterprise-oriented AI Agent platform built with LangGraph and LangChain.

It provides a unified runtime for developing intelligent applications by integrating:

Large Language Models
Multi-Agent Collaboration
Retrieval-Augmented Generation
Tool Calling
Memory Management

AgentHub supports two major operation modes:

Chat Mode

Open-domain AI Assistant


Work Mode

Enterprise AI Workspace

✨ Features
1. Dual Agent Modes
Chat Mode

A general-purpose AI assistant for open-domain tasks.

Capabilities:

Knowledge Q&A
Code generation
Research assistance
External knowledge retrieval
Multi-turn conversations

Architecture:

User

 ↓

Chat Supervisor Agent

 ↓

Specialized Agents

 ↓

LLM + Tools

 ↓

Response

Work Mode

An enterprise AI workspace designed for internal business scenarios.

Capabilities:

Employee handbook QA
Enterprise document understanding
HR assistant
OA workflow assistant
Internal knowledge management

Architecture:

Employee

 ↓

Work Supervisor Agent

 ↓

Enterprise Agents

 ↓

Enterprise Knowledge Base

 ↓

Answer

2. Multi-Agent Collaboration

AgentHub uses LangGraph to orchestrate multiple specialized agents.

Supervisor Agent handles:

Intent understanding
Task decomposition
Agent routing
Workflow execution
Result aggregation

Example:

User Request

      |

Supervisor Agent

      |

----------------------

Search Agent

Code Agent

Research Agent

      |

Final Response

3. Retrieval-Augmented Generation

AgentHub integrates a complete RAG pipeline to reduce LLM hallucination.

Pipeline:

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


Technologies:

BGE-M3 Embedding
ChromaDB
LangChain Retriever
4. Agent Tool Calling

Agents can dynamically invoke external tools.

Workflow:

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


Supported tools:

Search
Database Query
Document Retrieval
Enterprise APIs
Workflow Automation
5. Memory System

AgentHub supports intelligent memory management.

Short-term Memory

Maintains:

Conversation context
Task states

Powered by:

LangGraph Checkpoint
Long-term Memory

Stores:

User preferences
Historical interactions
Enterprise knowledge
🏗 Architecture
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

🛠 Technology Stack
Agent Framework
LangGraph
LangChain
Multi-Agent Architecture
LLM
DeepSeek
OpenAI
Qwen
Ollama
RAG
BGE-M3
ChromaDB
Vector Retrieval
Backend
FastAPI
Uvicorn
AsyncIO
Pydantic
Frontend
Next.js
React
TypeScript
Ant Design
Tailwind CSS
Database
SQLite
SQLAlchemy
🚀 Quick Start
Backend
cd backend

uv sync

source .venv/bin/activate

cd app

python run_server.py
Frontend
cd frontend

pnpm install

pnpm dev
🗺 Roadmap
Phase 1
LangGraph Runtime
Multi-Agent Workflow
LLM Integration
Phase 2

Chat Mode:

Search Agent
Code Agent
Research Agent
Phase 3

Work Mode:

Enterprise Knowledge Base
OA Agent
HR Agent
Document Agent
Phase 4

Enterprise Platform:

Agent Marketplace
Permission Management
Workflow Automation
Agent Evaluation
🌟 Vision

AgentHub aims to become an enterprise AI Agent infrastructure platform by connecting:

LLM

+

Knowledge

+

Tools

+

Workflow

+

Memory


to build reliable and scalable intelligent applications.
