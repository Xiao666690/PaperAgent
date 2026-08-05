PaperAgent
<p align="center"> <b>An Intelligent Multi-Agent System for Academic Paper Understanding and Research Assistance</b> </p>
📖 Overview

PaperAgent is an intelligent academic research assistant built on top of LangGraph + LangChain + Large Language Models (LLMs).

The system aims to solve the limitations of traditional LLM-based paper analysis systems, including:

Hallucinated academic knowledge
Lack of citation verification
Difficulty in understanding long-context papers
Weak reasoning ability over complex research content

By integrating Retrieval-Augmented Generation (RAG), Multi-Agent Collaboration, and Tool Calling, PaperAgent builds an end-to-end research workflow from:

Paper retrieval → Knowledge extraction → Understanding → Reasoning → Verification → Research assistance

Unlike traditional chat-based LLM applications, PaperAgent introduces specialized agents responsible for different research tasks, enabling reliable and interpretable academic analysis.

✨ Features
1. Multi-Agent Research Workflow

PaperAgent adopts a LangGraph-based Agent orchestration architecture.

A supervisor agent dynamically decomposes user queries and routes tasks to specialized agents.

Architecture:

                    User Query
                        |
                        |
                Supervisor Agent
                        |
        --------------------------------
        |              |               |
 Paper Retrieval   Paper Reader   Verification
    Agent             Agent          Agent
        |              |               |
        --------------------------------
                        |
                Final Research Answer
Supported Agents
Agent	Function
Paper Retrieval Agent	Retrieve related papers and knowledge
Paper Understanding Agent	Analyze paper structure and methodology
Citation Verification Agent	Verify factual consistency
Experiment Analysis Agent	Understand experiments and results
Research Assistant Agent	Generate summaries and insights
2. Retrieval-Augmented Generation (RAG)

To reduce LLM hallucination in academic scenarios, PaperAgent integrates a complete RAG pipeline.

Workflow:

PDF Paper

↓

Document Parser

↓

Chunk Segmentation

↓

Embedding Model

↓

Vector Database

↓

Retriever

↓

LLM Reasoning
Knowledge Processing
Document Parsing

Supports:

PDF papers
Markdown documents
Technical reports

Technology:

PyPDF
LangChain Document Loader
Semantic Chunking

Long papers are split into meaningful chunks:

Paper

|
|-- Abstract
|
|-- Introduction
|
|-- Method
|
|-- Experiment
|
|-- Conclusion

Technology:

LangChain Text Splitter
Embedding Representation

Paper chunks are transformed into semantic vectors using:

BGE-M3 Embedding Model

Advantages:

Multilingual support
Long-context representation
Academic semantic retrieval
Vector Database

Paper knowledge is stored using:

ChromaDB

Stored information:

{
 text_chunk,
 embedding_vector,
 paper_metadata,
 citation_information
}
3. Academic Knowledge Grounding

Traditional LLM:

Question

↓

LLM Memory

↓

Answer

Problem:

Outdated knowledge
Hallucinated references
Incorrect claims

PaperAgent:

Question

↓

Retrieve Relevant Paper Evidence

↓

Reasoning

↓

Evidence-based Answer

The generated response is grounded on retrieved academic sources.

4. Tool Calling Framework

PaperAgent enables agents to actively invoke external tools.

Example:

User:

Find papers about diffusion model editing

Agent reasoning:

Need external knowledge

↓

Call Paper Search Tool

↓

Retrieve papers

↓

Analyze results

↓

Generate response

Tool examples:

Paper Search Tool
Vector Retrieval Tool
Citation Checker
Metadata Query Tool
5. Long Paper Understanding

Large academic papers contain:

Complex mathematical formulations
Multiple experiments
Extensive references

PaperAgent uses:

Hierarchical retrieval
Chunk-level reasoning
Multi-step analysis

to support:

Paper summary
Method explanation
Innovation analysis
Experiment comparison
Reviewer-style critique
6. Streaming Interaction

Backend provides real-time response through:

FastAPI + Server Sent Events (SSE)

Workflow:

Agent generates token

↓

SSE Stream

↓

Frontend receives token

↓

Real-time display

Similar to ChatGPT streaming experience.

🏗 System Architecture
                 Frontend
              Next.js + React
                    |
                    |
              FastAPI Backend
                    |
                    |
             LangGraph Workflow
                    |
        ----------------------------
        |                          |
 Supervisor Agent              Memory
        |
 ------------------------------
 |             |               |
Retriever   Analyzer     Validator
 Agent       Agent        Agent

        |
        |
   LangChain Framework

        |
 -------------------
 |                 |
DeepSeek        Tools
LLM             Calling

        |
        |
 RAG Knowledge Base

        |
 -------------------
 |                 |
BGE-M3          ChromaDB
Embedding       Vector Store

🛠 Technology Stack
LLM & Agent Framework
LangGraph
LangChain
Multi-Agent Architecture
Agent Tool Calling
Large Language Models
DeepSeek API
OpenAI Compatible API
Ollama Local Models
Retrieval-Augmented Generation
RAG
BGE-M3 Embedding
ChromaDB
Semantic Retrieval
Backend
FastAPI
Uvicorn
Pydantic
AsyncIO
Frontend
Next.js
React
TypeScript
Ant Design
Tailwind CSS
Database
SQLite
SQLAlchemy
LangGraph Checkpoint
🚀 Quick Start
1. Clone Repository
git clone https://github.com/xxx/PaperAgent.git

cd PaperAgent
Backend Setup

Create environment:

cd backend

uv sync

Activate:

source .venv/bin/activate

Configure:

.env

Example:

DEEPSEEK_API_KEY=your_key

DEFAULT_MODEL=deepseek-chat

EMBEDDING_MODEL=bge-m3

CHROMA_PATH=resource/chroma_db

Run:

cd app

python run_server.py

Backend:

http://localhost:8000
Frontend Setup

Install:

cd frontend

pnpm install

Run:

pnpm dev

Frontend:

http://localhost:3000
📚 Example Usage
Paper Understanding

Input:

Explain the core innovation of this paper.

Output:

1. Problem Definition

2. Method Overview

3. Technical Innovation

4. Experimental Results

5. Limitations
Paper Comparison

Input:

Compare this paper with RAG.

Agent:

Retrieval Agent
        +
Analysis Agent
        +
Reasoning Agent

Generate:

Method difference
Advantage
Limitation
Future direction
🔬 Future Improvements
1. Research Memory

Introduce long-term research memory:

User Research Interest

↓

Knowledge Graph

↓

Personal Research Assistant
2. Citation Graph Reasoning

Build:

Paper

↓

Citation Network

↓

Research Evolution Analysis
3. Autonomous Research Agent

Future:

Research Goal

↓

Paper Search

↓

Literature Review

↓

Experiment Design

↓

Research Report Generation
🏆 Project Highlights
Built a complete LLM Agent engineering system
Implemented LangGraph multi-agent orchestration
Designed RAG-based academic knowledge enhancement
Integrated tool calling and external knowledge retrieval
Developed FastAPI + SSE real-time interaction framework
Reduced LLM hallucination through evidence-grounded generation
📌 Project Status

🚧 Under active development

Current Version:

v0.1

Implemented:

✅ Agent Framework
✅ RAG Pipeline
✅ Vector Retrieval
✅ LLM Integration
✅ Streaming Chat Interface

Developing:

🚧 Paper Retrieval Agent
🚧 Citation Verification Agent
🚧 Academic Knowledge Graph
🚧 Automated Literature Review
