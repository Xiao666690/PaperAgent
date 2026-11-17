"""paper_reader：按 documentID / page 读取论文原文。"""
from __future__ import annotations

import os
import re
from contextlib import contextmanager

import fitz

from pydantic import BaseModel, ConfigDict

from core.skills.base import BaseSkill, SkillResult


@contextmanager
def open_research_pdf(document_id: str, ctx: dict):
    if document_id not in ctx.get("allowed_document_ids", []):
        raise ValueError("FORBIDDEN_DOCUMENT")
    db_factory = ctx.get("db_factory")
    if db_factory is None:
        raise ValueError("NO_DB")
    from core.backend.db.models import Document

    with db_factory() as db:
        query = db.query(Document).filter(Document.uid == document_id)
        if ctx.get("workspace_lid"):
            query = query.filter(Document.lid == ctx["workspace_lid"])
        doc = query.first()
        if doc is None:
            raise ValueError("NOT_FOUND")
        path = doc.documentPath
    if not os.path.exists(path):
        path = os.getenv("AcadeAgent_DIR", ".") + path
    if not os.path.exists(path):
        raise ValueError("FILE_NOT_FOUND")
    with fitz.open(path) as pdf:
        yield pdf


def find_excerpts(document_id: str, query: str, ctx: dict) -> list[dict]:
    """Rank small original-text windows in a single selected PDF."""
    words = {word for word in re.findall(r"[a-z][a-z0-9-]+|\d+(?:\.\d+)?", query.casefold()) if word not in {"the", "and", "for", "pdf"}}
    for segment in re.findall(r"[\u3400-\u9fff]+", query):
        words.update(segment[index:index + 2] for index in range(len(segment) - 1))
    ranked = []
    try:
        with open_research_pdf(document_id, ctx) as pdf:
            for index, page in enumerate(pdf):
                if index >= 80:
                    break
                text = page.get_text("text")
                if not text.strip():
                    continue
                lines = text.splitlines(keepends=True)
                scores = [
                    sum(word in line.casefold() for word in words)
                    for line in lines
                ]
                if not scores:
                    continue
                best = max(range(len(lines)), key=scores.__getitem__)
                if index >= 2 and scores[best] == 0:
                    continue
                center = sum(map(len, lines[:best]))
                start = max(0, center - 450)
                excerpt = text[start:start + 1800].strip()
                ranked.append((scores[best], index, {
                    "document_id": document_id, "page_number": index + 1,
                    "chunk_id": f"pdf:{index + 1}:{start}", "text": excerpt,
                }))
    except (ValueError, RuntimeError, OSError):
        return []
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [record for _, _, record in ranked[:5]]


class PaperReaderInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    document_id: str
    page: int = 1


class PaperReaderSkill(BaseSkill):
    name = "paper_reader"
    description = "按 documentID 与页码读取论文原文"
    input_model = PaperReaderInput

    async def execute(self, data: PaperReaderInput, ctx: dict) -> SkillResult:
        try:
            with open_research_pdf(data.document_id, ctx) as pdf:
                if data.page < 1 or data.page > len(pdf):
                    return SkillResult(ok=False, error_code="BAD_PAGE", error_message=f"页码越界: {data.page}")
                text = pdf.load_page(data.page - 1).get_text("text")
        except ValueError as exc:
            reasons = {
                "FORBIDDEN_DOCUMENT": "论文不在当前任务允许的范围内",
                "NO_DB": "数据库未注入",
                "NOT_FOUND": "文档不存在",
                "FILE_NOT_FOUND": "文件不存在",
            }
            if str(exc) not in reasons:
                raise
            return SkillResult(ok=False, error_code=str(exc), error_message=reasons[str(exc)])

        return SkillResult(
            ok=True,
            output={"text": text, "page": data.page, "document_id": data.document_id},
        )
