"""V2 Ask Mode 可信问答路由。

流程：Intent → Retrieval → Evidence Judge → Answer → Grounding → SSE 分片输出。
旧 /chat/* 作为兼容接口保留，新前端走 /qa/stream。
"""
from __future__ import annotations

import asyncio
import json
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.backend.db.models import ActivityEvent, Document, TMPDocument
from core.backend.router.dependencies import get_db
from core.backend.utils.utils import get_current_user
from core.backend.router.req_res_schema import QARequest
from core.decision.engine import DecisionEngine, is_obvious_general_chat
from core.decision.external_search import (
    classify_external_request,
    is_broad_paper_recommendation,
    make_research_prompt,
    make_search_keywords,
    normalize_papers,
    wants_recent_papers,
)
from core.decision.prompts import ANSWER_PROMPT, GENERAL_CHAT_PROMPT
from core.decision.schemas import EvidenceDecision, IntentDecision, IntentType
from core.evidence.formatter import build_citations, format_evidence
from core.skills.paper_search import PaperSearchSkill
from core.backend.services.account_research_profile import account_evidence, computer_research_profile
from core.decision.external_search import filter_computer_papers

router = APIRouter()

_PAPER_REFERENCE = re.compile(
    r"这(?:篇|些|两篇|几篇|多篇)(?:论文|文章|文献)|该(?:篇)?(?:论文|文章|文献)|"
    r"本(?:篇|文|论文)|所选(?:论文|文献)|当前(?:论文|文献)|上述(?:论文|文献)|"
    r"(?:选中|选定|上传|绑定)(?:的)?(?:论文|文章|文献|PDF)|"
    r"(?:这|当前)(?:个|份)?PDF|"
    r"(?:论文|文章|文献)(?:的|中|里|讲|介绍|总结|主要|核心)|"
    r"\b(?:this|selected|attached|uploaded|current)\s+papers?\b",
    re.IGNORECASE,
)
_PAPER_OVERVIEW = re.compile(
    r"讲一下|介绍|概述|概括|总结|摘要|主要内容|核心内容|解读|逐篇|分别说明|"
    r"(?:overview|summari[sz]e|introduce|explain)\b",
    re.IGNORECASE,
)


def _targets_selected_paper(question: str, names: list[str]) -> bool:
    query = question.strip()
    if _PAPER_REFERENCE.search(query):
        return True
    if any(name.casefold() in query.casefold() for name in names if name):
        return True
    # A short deictic prompt after the user bound a PDF also targets that PDF.
    return bool(re.fullmatch(r"(?:帮我|请|先)?(?:讲一下|介绍一下|总结一下|概括一下|解读一下)[。！？?\s]*", query))


def _is_paper_overview(question: str) -> bool:
    if re.search(r"实验|消融|公式|参数|数据集|评估|指标|具体结果|局限|缺点|细节", question):
        return False
    return bool(_PAPER_OVERVIEW.search(question))


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _stream_model_text(agent, prompt: str, *, continue_on_length: bool = False):
    """Preserve the provider's finish reason and resume length-limited answers."""
    accumulated = ""
    current_prompt = prompt
    for attempt in range(3 if continue_on_length else 1):
        stream = (agent.chat_simple(current_prompt) if hasattr(agent, "chat_simple")
                  else agent.get_llm().stream(current_prompt))
        finish_reason = None
        received = False
        for chunk in stream:
            metadata = getattr(chunk, "response_metadata", {}) or {}
            finish_reason = metadata.get("finish_reason") or finish_reason
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            if isinstance(content, str) and content:
                received = True
                accumulated += content
                yield content
        if not continue_on_length or finish_reason != "length" or not received:
            break
        if attempt == 2:
            yield "\n\n> 模型连续达到输出长度限制，以上回答尚未完整，请缩小论文范围后继续提问。"
            break
        current_prompt = (
            prompt + "\n\n下面是你已输出的回答：\n" + accumulated +
            "\n\n上次因输出长度限制中断。请从最后一句未完成处继续，"
            "不要重复已有内容，补全剩余论文及结论，保留原有引用编号。"
        )


def _paper_support_response(agent, question, selected_papers):
    prompt = GENERAL_CHAT_PROMPT.format(question=question, selected_papers=selected_papers, conversation_context='（暂无）')
    prompt += (
        '\n用户在讨论所选论文，但正文解析或检索片段暂未就绪。不要猜测这篇论文的内容或称用户未上传文件。'
        '先回应问题能确定的部分：若是概念、分析方法或写作任务，给出明确标为通用知识的解释或操作步骤；'
        '若要求具体论文事实，指出需要核查的章节、表格或字段，并提示可选择原文段落继续。'
        '不要编造论文结论，不用“无法回答”“当前证据不足”作结。'
    )
    produced = False
    if agent is not None:
        try:
            for text in _stream_model_text(agent, prompt, continue_on_length=True):
                produced = True
                yield text
        except Exception:
            yield '\n\n这轮连接中断，已保留生成内容。可切换模型继续，或提供需要分析的原文段落。'
            produced = True
    if not produced:
        yield (f'已选定 {selected_papers}。你可以先在阅读窗口选中相关段落继续提问；'
               '核查方法看方法章节，核查数值看实验表格和附录。正文解析完成后可继续结合全文讨论。')


@router.post("/qa/stream")
def qa_stream(
    qa: QARequest,
    request: Request,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    selected_papers = []
    if qa.document_ids:
        selected_ids = set(qa.document_ids)
        owned_papers = {
            row.uid: row for row in db.query(Document).filter(
                Document.lid == user.workspace_lid, Document.uid.in_(selected_ids)
            ).all()
        }
        owned_papers.update(
            (row.uid, row) for row in db.query(TMPDocument).filter(
                TMPDocument.lid == user.workspace_lid, TMPDocument.uid.in_(selected_ids)
            ).all()
        )
        if not selected_ids.issubset(owned_papers):
            raise HTTPException(status_code=403, detail="部分论文不在当前账号的资料库中")
        selected_papers = [owned_papers[document_id] for document_id in dict.fromkeys(qa.document_ids)]
    citation_destinations = {paper.uid: paper.knowledgeID for paper in selected_papers}
    document_names = {paper.uid: paper.documentName for paper in selected_papers}
    selected_names = list(document_names.values())
    selected_paper_text = "、".join(selected_names) if selected_names else "无"
    profile = computer_research_profile(account_evidence(db, user, remember=qa.question))

    # Count submitted Ask requests for this account. The event contains no question text.
    db.add(ActivityEvent(lid=user.workspace_lid, event_type="ask"))
    db.commit()

    trace_id = uuid.uuid4().hex[:12]
    agent = getattr(request.app, "chat_agents", {}).get(qa.model)
    if agent is None:
        agent = getattr(request.app, "chat_agents", {}).get("deepseek")
    decision_engine = (
        DecisionEngine(agent.get_llm())
        if agent is not None
        else getattr(request.app, "decision_engine", None)
    )
    chroma_db = getattr(request.app, "chroma_db", None)

    def generate():
        # 1. Intent 判断
        external_kind = classify_external_request(qa.question)
        if external_kind == 'transfer' and not qa.document_ids and not re.search(r'论文|文献|paper|literature', qa.question, re.I):
            external_kind = None
        intent = None
        if external_kind:
            yield _sse("meta", {
                "trace_id": trace_id,
                "route": "EXTERNAL_RESEARCH",
                "intent": IntentType.RESEARCH_TASK.value,
            })
        elif not qa.document_ids:
            yield _sse("meta", {
                "trace_id": trace_id,
                "route": "GENERAL_CHAT",
                "intent": IntentType.GENERAL_CHAT.value,
            })
        elif is_obvious_general_chat(qa.question):
            intent = IntentDecision(intent=IntentType.GENERAL_CHAT, confidence=1.0, reason_code='DIRECT_GENERAL_REQUEST')
            yield _sse('meta', {'trace_id': trace_id, 'route': 'GENERAL_CHAT', 'intent': IntentType.GENERAL_CHAT.value})
        elif _targets_selected_paper(qa.question, selected_names):
            yield _sse("meta", {
                "trace_id": trace_id,
                "route": "LOCAL_RAG",
                "intent": IntentType.MULTI_PAPER_QA.value if len(selected_papers) > 1 else IntentType.PAPER_QA.value,
            })
        elif decision_engine is not None:
            intent = decision_engine.decide_intent(
                qa.question,
                f"当前已选论文：{selected_paper_text}\n{qa.conversation_context}",
            )
            route = "GENERAL_CHAT" if intent.intent == IntentType.GENERAL_CHAT else "LOCAL_RAG"
            yield _sse("meta", {
                "trace_id": trace_id,
                "route": route,
                "intent": intent.intent.value,
            })
        else:
            intent = IntentDecision(intent=IntentType.GENERAL_CHAT, confidence=0.0, reason_code='NO_CLASSIFIER')
            yield _sse("meta", {
                "trace_id": trace_id,
                "route": "GENERAL_CHAT",
                "intent": IntentType.GENERAL_CHAT.value,
            })

        # 普通聊天不需要论文证据，直接交给当前模型自然回答。
        if not external_kind and (not qa.document_ids or (intent is not None and intent.intent == IntentType.GENERAL_CHAT)):
            fallback_answer = "这轮模型连接未建立，你的问题已保留。可以切换上方模型继续提问；若问题较长，也可以分成几个步骤逐项处理。"
            if agent is not None:
                prompt = GENERAL_CHAT_PROMPT.format(
                    question=qa.question,
                    conversation_context=qa.conversation_context or "（暂无）",
                    selected_papers=selected_paper_text,
                )
                prompt += '\n科研推荐偏好：' + profile['summary'] + '\n这些偏好只用于科研推荐；普通问题直接按用户需求回答，不能强行转向计算机论文。'
            yield _sse("decision", {
                "decision": "GENERAL_CHAT",
                "evidence_score": 1.0,
                "confidence": intent.confidence if intent is not None else 1.0,
            })
            streamed = False
            if agent is not None:
                try:
                    for text in _stream_model_text(agent, prompt, continue_on_length=True):
                        streamed = True
                        yield _sse("delta", {"text": text})
                except Exception:
                    if streamed:
                        yield _sse('delta', {'text': '\n\n这轮连接中断，已保留生成内容。可切换模型继续完成剩余部分。'})
            if not streamed:
                yield _sse("delta", {"text": fallback_answer})
            yield _sse("grounding", {
                "passed": True,
                "confidence": 1.0,
                "skipped": True,
                "reason": "GENERAL_CHAT",
            })
            yield _sse("citations", {"items": []})
            return

        # 2. 检索
        evidence = []
        if chroma_db is not None and qa.document_ids:
            overview = _is_paper_overview(qa.question)
            try:
                if overview and hasattr(chroma_db, "get_opening_evidence"):
                    evidence.extend(chroma_db.get_opening_evidence(qa.document_ids))
                retrieved = chroma_db.search_evidence(
                    "paper abstract introduction main method contributions and results" if overview else qa.question,
                    {"documentID": {"$in": qa.document_ids}},
                    k=4 if overview else 8,
                )
            except Exception:
                retrieved = []
            seen_chunks = {item.chunk_id for item in evidence}
            seen_texts = {(item.document_id, item.text) for item in evidence}
            for item in retrieved:
                if item.chunk_id not in seen_chunks and (item.document_id, item.text) not in seen_texts:
                    evidence.append(item)
                    seen_chunks.add(item.chunk_id)
                    seen_texts.add((item.document_id, item.text))
            # Overview evidence is grouped by paper. A fixed global cap silently
            # discarded every paper after the fourth in multi-paper requests.
            evidence = evidence[:max(8, 2 * len(set(qa.document_ids)) + 4) if overview else 12]

        if qa.document_ids and not evidence and not external_kind:
            yield _sse("decision", {"decision": "PARTIAL_GUIDANCE", "evidence_score": 0.0, "confidence": 1.0})
            for text in _paper_support_response(agent, qa.question, selected_paper_text):
                yield _sse('delta', {'text': text})
            yield _sse('grounding', {'passed': False, 'reason': 'GENERAL_GUIDANCE_WITHOUT_PAPER_TEXT'})
            yield _sse("citations", {"items": []})
            return

        # Use the authorized SQL record as the canonical citation destination.
        # The same PDF may also have an older temporary-upload vector scope.
        evidence = [item for item in evidence if item.document_id in citation_destinations]
        for item in evidence:
            item.knowledge_id = citation_destinations[item.document_id]

        # 3. 证据格式化 + 引用映射
        evidence_text, citation_map = format_evidence(evidence, document_names=document_names)

        # 4. Evidence Judge
        if decision_engine is not None or external_kind:
            if external_kind:
                ev = EvidenceDecision(decision="SEARCH_EXTERNAL", confidence=1.0, evidence_score=0.0)
            elif _is_paper_overview(qa.question) and evidence:
                ev = EvidenceDecision(decision="ANSWER", confidence=1.0, evidence_score=1.0)
            else:
                ev = decision_engine.decide_evidence(qa.question, evidence_text)
            search_external = ev.decision == "SEARCH_EXTERNAL"
            yield _sse("decision", {
                "decision": "SEARCH_EXTERNAL" if search_external else ev.decision,
                "evidence_score": ev.evidence_score,
                "confidence": ev.confidence,
            })
            if search_external:
                broad_request = is_broad_paper_recommendation(qa.question)
                yield _sse("search_status", {
                    "state": "preparing",
                    "text": "按当前账户科研画像检索；" + profile['summary'],
                })
                keywords = (
                    make_search_keywords(
                        decision_engine.llm if decision_engine is not None else None,
                        qa.question,
                        evidence_text,
                        kind=external_kind or "literature",
                        profile=profile,
                    )
                    if broad_request or not ev.search_keywords
                    else ev.search_keywords[:3]
                )
                yield _sse("search_status", {
                    "state": "searching",
                    "text": "正在检索 arXiv / OpenAlex：" + "、".join(keywords),
                })
                result = asyncio.run(PaperSearchSkill().run(
                    {"keywords": keywords, "max_results": 8, "recent": wants_recent_papers(qa.question), "computer_science": True}
                ))
                papers = normalize_papers(filter_computer_papers(result.output.get("papers", []), keywords)) if result.ok else []
                yield _sse("external_papers", {
                    "items": papers,
                    "keywords": keywords,
                    "provider": result.output.get("provider", "") if result.ok else "",
                    "warning": result.output.get("warning", "") if result.ok else result.error_message,
                })
                if papers:
                    yield _sse("search_status", {
                        "state": "answering",
                        "text": f"从 {result.output.get('provider', '学术来源')} 找到 {len(papers)} 篇论文，正在对照摘要整理建议…",
                    })
                    if agent is not None:
                        prompt = make_research_prompt(
                            qa.question, profile['summary'] + '\n' + evidence_text, papers, kind=external_kind or "literature"
                        )
                        try:
                            for text in _stream_model_text(agent, prompt):
                                yield _sse("delta", {"text": text})
                        except Exception:
                            yield _sse("delta", {"text": "已找到相关论文，请先查看下方题目和摘要，再选择需要核查的 PDF。"})
                    else:
                        yield _sse("delta", {"text": "已找到相关论文，请查看下方结果并选择需要进一步阅读的 PDF。"})
                else:
                    yield _sse("search_status", {
                        "state": "answering", "text": "学术来源暂未返回可核实的论文，正在整理下一步建议…",
                    })
                    fallback = (
                        "当前计算机领域与账户研究兴趣范围内，没有找到可核实的匹配论文，因此不会用其他领域论文填充。"
                        "你想关注哪个方向？例如大模型、计算机视觉、联邦学习或医学影像。"
                        "指定领域后，我会重新检索并列出真实论文供你选择。"
                    ) if broad_request else (
                        "目前外部学术检索没有返回可核实的论文题录。"
                        "我可以先帮你梳理这个问题的研究关键词和筛选思路；"
                        "如果你给出更具体的领域、方法或时间范围，我会继续检索。"
                    )
                    streamed = False
                    if agent is not None:
                        prompt = (
                            "你是 PaperAgent 学术助手。用户提出了下面的问题，但实时学术搜索没有返回可核实的论文题录。"
                            "请先直接回应用户能做什么，给出简短、有用的研究方向或筛选建议，"
                            "仅讨论计算机领域及技术应用，使用用户画像，不可推荐教育、文学或历史等无关论文。不可编造具体论文标题、作者或最新发表事实；"
                            "明确说明当前未取得可核实题录。\n用户兴趣：" + profile['summary'] + "\n用户问题：" + qa.question[:1000]
                        )
                        try:
                            for text in _stream_model_text(agent, prompt):
                                streamed = True
                                yield _sse("delta", {"text": text})
                        except Exception:
                            pass
                    if not streamed:
                        yield _sse("delta", {"text": fallback})
                yield _sse("search_status", {"state": "done", "text": "外部学术检索已完成"})
                yield _sse("grounding", {"passed": False, "confidence": ev.confidence, "reason": "EXTERNAL_METADATA_ONLY"})
                yield _sse("citations", {
                    "items": [
                        {
                            "id": c.citation_id,
                            "documentID": c.document_id,
                            "documentName": document_names.get(c.document_id, "论文"),
                            "knowledgeID": c.knowledge_id,
                            "page": c.page_number,
                            "chunk_id": c.chunk_id,
                        }
                        for c in build_citations(citation_map)
                    ]
                })
                return
            if ev.decision == "ABSTAIN":
                # Continue with supported facts plus clearly separated explanation,
                # rather than terminating the conversation with a refusal sentence.
                evidence_text += '\n回答要求：所问具体信息可能未被论文披露。指出未报告的字段，解释已知部分与核查方法，不能编造该信息。'

        # 5. Answer 生成（带引用）
        answer = ""
        if agent is not None:
            prompt = ANSWER_PROMPT.format(
                question=qa.question,
                evidence=evidence_text,
                selected_papers=selected_paper_text,
            )
            prompt += '\n最近对话（仅用于理解追问对象，不作为论文事实来源）：\n' + (qa.conversation_context or '（暂无）')
            if _is_paper_overview(qa.question) and len(selected_papers) > 1:
                prompt += (
                    f"\n请逐篇覆盖全部 {len(selected_papers)} 篇论文。每篇先用 2–3 句概述"
                    "主要问题、方法和贡献并附引用，避免前几篇过长而遗漏后面的论文。"
                    "没有证据的论文明确说明，不得凭标题编造。"
                )
            try:
                for text in _stream_model_text(agent, prompt, continue_on_length=True):
                    answer += text
                    yield _sse("delta", {"text": text})
            except Exception:
                yield _sse('delta', {'text': '\n\n这轮模型连接中断，已保留内容和来源。可切换模型继续讨论，或选中目标段落缩小分析范围。'})
        else:
            yield _sse('delta', {'text': '已找到相关论文片段。可先查看来源页的原文，或切换上方模型继续分析方法、实验与结论。'})

        # 6. Grounding Verify
        citations = build_citations(citation_map)
        if decision_engine is not None:
            from core.evidence.grounding import GroundingVerifier
            verifier = GroundingVerifier(decision_engine)
            grounding_passed, report = verifier.verify(
                qa.question, answer, citations, citation_map
            )
            yield _sse("grounding", {"passed": grounding_passed, "confidence": report["confidence"]})

        # 7. Citations
        yield _sse("citations", {
            "items": [
                {
                    "id": c.citation_id,
                    "documentID": c.document_id,
                            "documentName": document_names.get(c.document_id, "论文"),
                    "knowledgeID": c.knowledge_id,
                    "page": c.page_number,
                    "chunk_id": c.chunk_id,
                }
                for c in citations
            ]
        })

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
