from contextlib import asynccontextmanager

import dotenv

dotenv.load_dotenv()

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
from langchain_core.embeddings import Embeddings

from core.agent.chatAgent import *
from core.agent.dataprocessAgent import *
from core.backend.crud.crud_document import *
from core.backend.crud.crud_knowledge import *
from core.backend.crud.crud_user import *
from core.backend.db.database import engine
from core.backend.db.models import Base
from core.backend.router import (
    router_document,
    router_knowledge,
    router_llm,
    router_translate,
    router_user,
    router_note,
    router_post,
    router_commit
)
from core.backend.schema.schema import *
from core.llm.LLM import LLM
from core.vectordb.chromadb import *


Base.metadata.create_all(bind=engine)


class ONNXEmbeddings(Embeddings):
    """使用 ChromaDB 内置 ONNX 模型，无需 API key，不依赖 sentence-transformers"""
    def __init__(self):
        cache_dir = os.getenv("CHROMA_ONNX_CACHE_DIR")
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
            ONNXMiniLM_L6_V2.DOWNLOAD_PATH = cache_dir
        self._ef = ONNXMiniLM_L6_V2()

    def embed_documents(self, texts):
        return self._ef(texts)

    def embed_query(self, text):
        return self._ef([text])[0]


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.llm = LLM()
    app.chroma_db = AcadeChroma(
        os.getenv("CHROMA_LAYER1_DIR"),
        os.getenv("CHROMA_LAYER2_DIR"),
        ONNXEmbeddings(),
        app.llm
    )

    # 为每个模型创建 ChatAgent
    # 非流式 LLM 使用 deepseek 作为默认
    app.chat_agent = ChatAgent(
        app.llm.get_llm('deepseek'),
        app.llm.get_stream_llm('deepseek'),
        app.chroma_db
    )

    # 存储各模型的流式 chat agent
    app.chat_agents = {
        'deepseek': app.chat_agent,
        'kimi': ChatAgent(
            app.llm.get_llm('kimi'),
            app.llm.get_stream_llm('kimi'),
            app.chroma_db
        ),
        'openai': ChatAgent(
            app.llm.get_llm('openai'),
            app.llm.get_stream_llm('openai'),
            app.chroma_db
        ),
    }

    yield
    # Clean up the ML models and release resources
    print("shoutdown!")


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(router_user.router, tags=["router_user"])
app.include_router(router_knowledge.router, tags=["knowledge"])
app.include_router(router_document.router, tags=["router_document"])
app.include_router(router_llm.router, tags=["router_llm"])
app.include_router(router_translate.router, tags=["router_translate"])
app.include_router(router_note.router, tags=["router_note"])
app.include_router(router_post.router, tags=["router_post"])
app.include_router(router_commit.router, tags=["router_commit"])
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
