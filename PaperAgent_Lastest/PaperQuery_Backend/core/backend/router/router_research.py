"""V2 Research Mode 路由：创建/执行/查询科研任务并持久化。"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from langchain_core.callbacks import BaseCallbackHandler
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.dialects.sqlite import insert

from core.backend.db.models import Artifact, Document, GuidedResearch, ResearchFeedback, ResearchStep, ResearchTask
from core.backend.services import guided_research as guided
from core.backend.utils.utils import authenticate_access_token, get_db, oauth2_scheme
from core.research.guided import Difficulty, Question, ResearchPreference, event, normalized

router = APIRouter()
logger = logging.getLogger(__name__)
_research_slots = threading.BoundedSemaphore(2)


class ResearchTaskCreate(BaseModel):
    goal: str
    mode: str = "research"
    document_ids: list[str] = Field(default_factory=list)
    parent_task_id: str | None = None
    source: Literal["auto", "library", "discovery"] | None = None


class ResearchReview(BaseModel):
    revision: int
    action: Literal["continue", "revise", "repair", "cancel", "resume", "rewind"]
    questions: list[Question] | None = Field(default=None, max_length=30)
    query: str | None = Field(default=None, max_length=300)
    step_id: str | None = None
    difficulty: Difficulty | None = None
    review_policy: Literal["all", "checkpoints"] | None = None
    objective: str | None = Field(default=None, min_length=1, max_length=4000, pattern=r"\S")


class ResearchFeedbackInput(BaseModel):
    plan_version: int = Field(ge=1)
    rating: Literal["satisfied", "unsatisfied"]
    reason: Literal["answer_quality", "missing_evidence", "incomplete", "off_topic", "too_verbose"] | None = None
    note: str = Field(default="", max_length=1000)
    preference: ResearchPreference | None = None


def feedback_summary(feedback: ResearchFeedback | None) -> dict | None:
    if feedback is not None:
        return {key: getattr(feedback, key) for key in ("rating", "reason", "note", "preference")}
    return None


@router.put("/research/tasks/{task_id}/feedback")
def save_research_feedback(
    task_id: str, req: ResearchFeedbackInput,
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db),
):
    user = authenticate_access_token(token, db)
    task = db.query(ResearchTask).filter_by(task_id=task_id, lid=user.workspace_lid).first()
    row = db.get(GuidedResearch, task_id) if task else None
    if not row:
        raise HTTPException(status_code=404, detail="找不到研究结果")
    state = guided.load(row)
    if not guided.sources_available(db, user.workspace_lid, state):
        raise HTTPException(status_code=403, detail="研究资料权限已变化")
    if (task.status not in {"SUCCESS", "PARTIAL", "FAILED", "CANCELLED"}
            or state["plan_version"] != req.plan_version
            or (task.status == "CANCELLED" and not guided.report_artifacts(state, task_id))):
        raise HTTPException(status_code=409, detail="研究结果或报告版本已变化，请刷新")
    values = req.model_dump() | {
        "workspace_lid": user.workspace_lid, "updated_at": _utc_now(),
    }
    statement = insert(ResearchFeedback).values(task_id=task_id, username=user.username, **values)
    db.execute(statement.on_conflict_do_update(
        index_elements=["task_id", "plan_version", "username"], set_=values,
    ))
    db.commit()
    return {"data": req.model_dump()}


def _wake_worker(request: Request):
    worker = getattr(request.app, "guided_research_worker", None)
    if worker:
        worker.wake.set()


@router.get("/research/documents")
def list_research_documents(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user = authenticate_access_token(token, db)
    return {"data": [
        {"id": doc["id"], "title": doc["title"]}
        for doc in guided.documents(db, user.workspace_lid)
    ]}


def _create_guided_task(req, request, db, user):
    workspace = user.workspace_lid
    goal = req.goal.strip()
    if not goal or len(goal) > 4000:
        raise HTTPException(status_code=422, detail="请输入 1–4000 字的研究目标")
    if req.parent_task_id and not db.query(ResearchTask).filter_by(task_id=req.parent_task_id, lid=workspace).first():
        raise HTTPException(status_code=404, detail="上一轮研究任务不存在")
    requested = set(req.document_ids)
    source = req.source
    if source == "auto":
        external = r"联网|网上|外部文献|公开文献|公开论文|arxiv|openalex|web search"
        local_only = re.search(
            rf"(?:仅|只)(?:使用|用|查|检索)本地|"
            rf"(?:禁止|避免|无需|不(?:要|用|需要|允许)?)\s*(?:使用|进行|搜索|检索|查找)?\s*(?:{external})",
            goal, re.IGNORECASE,
        )
        if local_only and not requested:
            raise HTTPException(status_code=422, detail="深度研究使用公开学术搜索。仅分析本地论文时，请在论文阅读功能中提问。")
        source = "library" if requested else "discovery"
    documents = guided.documents(db, workspace) if requested or source == "library" else []
    if requested - {doc["id"] for doc in documents}:
        raise HTTPException(status_code=403, detail="部分论文不在当前资料库")
    if source == "discovery":
        selected = []
    else:
        selected = [doc for doc in documents if not requested or doc["id"] in requested]
        if not selected:
            raise HTTPException(status_code=422, detail="论文库没有可用论文，请先上传 PDF")
    task_id = uuid.uuid4().hex[:12]
    state = guided.initial_state(source, selected)
    state["goal"] = goal
    if req.parent_task_id:
        parent = db.get(GuidedResearch, req.parent_task_id)
        if parent:
            parent_state = guided.load(parent)
            visible_ids = {doc["id"] for doc in selected}
            same_source = source == parent_state["source"]
            if same_source and guided.sources_available(db, workspace, parent_state):
                context = [
                    finding["text"][:250]
                    for step in parent_state["steps"] for finding in step["findings"]
                    if finding["references"]
                    and all(ref.get("url") if source == "discovery" else ref["document_id"] in visible_ids
                            for ref in finding["references"])
                ][:6]
                if context:
                    state["parent_context"] = context
                    event(state, "已关联上一轮结果", "用于理解后续目标，当前任务会重新检索")
    latest_preference = db.query(ResearchFeedback.preference).filter(
        ResearchFeedback.workspace_lid == workspace, ResearchFeedback.username == user.username,
        ResearchFeedback.preference.is_not(None),
    ).order_by(ResearchFeedback.updated_at.desc()).first()
    if latest_preference:
        state["preference"] = latest_preference.preference
        event(state, "应用已选择的输出偏好")
    db.add(ResearchTask(
        task_id=task_id, lid=workspace, goal=goal, mode=req.mode,
        parent_task_id=req.parent_task_id, status="QUEUED",
    ))
    db.add(GuidedResearch(task_id=task_id, revision=0, state_json=_json_dumps(state)))
    db.commit()
    _wake_worker(request)
    return {"status_code": 200, "data": {"task_id": task_id, "status": "QUEUED"}}


@router.post("/research/tasks/{task_id}/review")
def review_research_task(
    task_id: str, req: ResearchReview, request: Request,
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db),
):
    user = authenticate_access_token(token, db)
    task = db.query(ResearchTask).filter_by(task_id=task_id, lid=user.workspace_lid).first()
    row = db.get(GuidedResearch, task_id) if task else None
    if not row:
        raise HTTPException(status_code=404, detail="找不到可审阅的任务")
    if row.revision != req.revision:
        raise HTTPException(status_code=409, detail="任务状态已更新，请刷新后重试")
    state = guided.load(row)
    status = task.status
    state.setdefault("goal", task.goal)
    if req.action != "cancel" and not guided.sources_available(db, user.workspace_lid, state):
        raise HTTPException(status_code=409, detail="原论文范围已变化，请重新创建任务")

    previous_difficulty = state.get("difficulty", "standard")
    previous_policy = state.get("review_policy", "all")
    if req.action == "rewind":
        if status not in {"RUNNING", "QUEUED", "AWAITING_INPUT", "WAITING_RETRY", "SUCCESS", "PARTIAL", "NO_RESULTS", "FAILED", "CANCELLED"}:
            raise HTTPException(status_code=409, detail="当前状态无法回退")
        difficulty = req.difficulty or previous_difficulty
        if not req.step_id or not req.questions or not guided.rewind(state, req.step_id, req.questions):
            raise HTTPException(status_code=422, detail="请选择已执行的节点，并保留至少一个研究问题")
        state["difficulty"] = difficulty
        status = guided.next_status(state)
    elif req.action == "cancel":
        if status not in {"QUEUED", "RUNNING", "AWAITING_APPROVAL", "AWAITING_INPUT", "WAITING_RETRY"}:
            raise HTTPException(status_code=409, detail="该任务已结束")
        status = "CANCELLED"
        event(state, "用户停止任务", "已保存完成的节点")
        for step in state["steps"]:
            if step["status"] == "RUNNING":
                step["status"] = "PENDING"
    elif req.action == "resume":
        retry_planning = status == "FAILED" and state["phase"] == "plan" and state["operations"] < guided.MAX_OPERATIONS
        if status != "WAITING_RETRY" and not retry_planning:
            raise HTTPException(status_code=409, detail="当前任务不能从此处重试")
        status = "QUEUED"
        event(state, "用户重试计划生成" if retry_planning else "用户恢复研究")
    else:
        if status not in {"AWAITING_APPROVAL", "AWAITING_INPUT"}:
            raise HTTPException(status_code=409, detail="当前没有待审阅的计划或节点")
        if status == "AWAITING_INPUT" and task.updated_at + timedelta(seconds=guided.NODE_REVIEW_SECONDS) <= _utc_now():
            raise HTTPException(status_code=409, detail="节点审阅已超时，请回退到需要调整的节点")
        current = next((step for step in state["steps"] if step["step_id"] == state["review_step_id"]), None)
        if req.action == "repair":
            query = (req.query or "").strip()
            if not current or not query or len(current["attempts"]) >= guided.MAX_ATTEMPTS:
                raise HTTPException(status_code=422, detail="请输入新查询，或当前节点的尝试额度已用完")
            if normalized(query) in {normalized(item["query"]) for item in current["attempts"]}:
                raise HTTPException(status_code=422, detail="该查询已经尝试过，请输入不同的查询")
            current.update(retry_query=query, status="PENDING", quality="PENDING")
            event(state, "用户要求重新检索" if state["source"] == "discovery" else "用户要求补证", query, current["step_id"])
        else:
            if req.difficulty is not None:
                state["difficulty"] = req.difficulty
            objective_changed = False
            if status == "AWAITING_APPROVAL":
                policy = req.review_policy or previous_policy
                objective = req.objective.strip() if req.objective else state.get("objective")
                objective_changed = objective != state.get("objective")
                state.update(review_policy=policy, objective=objective)
            if current:
                guided.accept_node(state, current)
            if req.action == "revise":
                if req.questions is None or not (req.questions or current):
                    raise HTTPException(status_code=422, detail="请至少保留一个研究节点")
                if not guided.replace_future(state, req.questions, "用户调整研究计划", objective_changed=objective_changed):
                    event(state, "用户按原计划继续", "节点内容未变，保留当前计划版本")
            elif objective_changed:
                guided.record_plan_change(state, "用户修正研究目标")
            else:
                event(state, "用户按原计划继续", "保留当前计划版本")
        status = guided.next_status(state)

    if previous_difficulty != state.get("difficulty", "standard"):
        labels = {"quick": "快速", "standard": "标准", "deep": "深入"}
        event(state, "用户调整执行难度", f"{labels[previous_difficulty]} → {labels[state['difficulty']]}")
    if previous_policy != state.get("review_policy", "all"):
        event(state, "用户调整审批方式", "仅在关键节点暂停" if state["review_policy"] == "checkpoints" else "逐步审阅")
    if not guided.save(db, task, row, state, status):
        raise HTTPException(status_code=409, detail="任务状态已更新，请刷新后重试")
    _wake_worker(request)
    return {"data": {"task_id": task_id, "status": status}}


def _json_safe(value: Any) -> Any:
    """把 Skill/第三方库结果递归转换成可持久化的 JSON 数据。"""
    if isinstance(value, Enum):
        return _json_safe(value.value)
    if isinstance(value, BaseModel):
        return _json_safe(value.model_dump())
    if isinstance(value, dict):
        return {
            str(key.value if isinstance(key, Enum) else key): _json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def _json_dumps(value: Any) -> str:
    # default=str 是最后一道保护，避免某个新 Skill 返回第三方自定义对象时整项任务丢失。
    return json.dumps(_json_safe(value), ensure_ascii=False, default=str)


def _utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None
            else value.astimezone(timezone.utc)).isoformat()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class _ResearchTokenHeartbeat(BaseCallbackHandler):
    """Streaming tokens refresh task activity without imposing a total deadline."""

    def __init__(self, touch):
        self.touch = touch
        self.last_touch = 0.0

    def on_llm_new_token(self, token: str, **kwargs):
        if not token or time.monotonic() - self.last_touch < 8:
            return
        self.last_touch = time.monotonic()
        try:
            self.touch()
        except Exception:
            logger.warning("Could not save research heartbeat", exc_info=True)


def _run_research_task(task_id: str, planning_goal: str, allowed_ids: list[str],
                       parent_task_id: str | None, prior_artifacts: list[dict],
                       orchestrator, llm_provider, db_factory,
                       workspace_lid: str | None = None,
                       available_documents: list[dict] | None = None):
    def touch():
        with db_factory() as session:
            task = session.query(ResearchTask).filter_by(task_id=task_id).first()
            if task and task.status == "RUNNING":
                task.updated_at = _utc_now()
                session.commit()

    def on_plan(plan):
        with db_factory() as session:
            task = session.query(ResearchTask).filter_by(task_id=task_id).one()
            task.plan_json = plan.model_dump_json()
            task.updated_at = _utc_now()
            session.commit()

    def on_step_start(step):
        with db_factory() as session:
            session.add(ResearchStep(
                step_id=step.step_id, task_id=task_id, skill_name=step.skill,
                status="RUNNING",
            ))
            task = session.query(ResearchTask).filter_by(task_id=task_id).one()
            task.updated_at = _utc_now()
            session.commit()

    def on_step(step, result):
        with db_factory() as session:
            row = session.query(ResearchStep).filter_by(task_id=task_id, step_id=result.step_id).first()
            if row is None:
                row = ResearchStep(step_id=result.step_id, task_id=task_id, skill_name=step.skill)
                session.add(row)
            row.status = result.status
            row.output_json = _json_dumps(result.output)
            row.error = result.error
            row.duration_ms = result.duration_ms
            task = session.query(ResearchTask).filter_by(task_id=task_id).one()
            task.updated_at = _utc_now()
            session.commit()

    with _research_slots:
        try:
            with db_factory() as session:
                task = session.query(ResearchTask).filter_by(task_id=task_id).one()
                task.status = "RUNNING"
                task.updated_at = _utc_now()
                session.commit()

            context = {
                "allowed_document_ids": allowed_ids,
                "workspace_lid": workspace_lid,
                "available_documents": available_documents,
                "parent_task_id": parent_task_id,
                "prior_artifacts": prior_artifacts,
                "_task_id": task_id,
                "_on_plan": on_plan,
                "_on_step_start": on_step_start,
                "_on_step": on_step,
            }
            if llm_provider is not None:
                research_llm = llm_provider.get_stream_llm("deepseek").with_config(
                    callbacks=[_ResearchTokenHeartbeat(touch)]
                )
                context["_research_llm"] = research_llm
                context["llm"] = research_llm
            state = orchestrator.run(planning_goal, context=context)

            with db_factory() as session:
                task = session.query(ResearchTask).filter_by(task_id=task_id).one()
                task.plan_json = state.plan.model_dump_json()
                for result in state.step_results:
                    if not session.query(ResearchStep).filter_by(task_id=task_id, step_id=result.step_id).first():
                        session.add(ResearchStep(
                            step_id=result.step_id, task_id=task_id,
                            skill_name=next((s.skill for s in state.plan.steps if s.step_id == result.step_id), ""),
                            status=result.status, output_json=_json_dumps(result.output),
                            error=result.error, duration_ms=result.duration_ms,
                        ))
                for artifact in state.artifacts:
                    safe_artifact = _json_safe(artifact)
                    artifact_id = safe_artifact.get("artifact_id") or uuid.uuid4().hex
                    safe_artifact["artifact_id"] = artifact_id
                    session.add(Artifact(
                        artifact_id=artifact_id, task_id=task_id,
                        type=safe_artifact.get("type", ""), title=safe_artifact.get("title", ""),
                        data_json=_json_dumps(safe_artifact),
                    ))
                task.status = state.status
                task.updated_at = _utc_now()
                session.commit()
        except Exception as exc:
            logger.exception("Research task %s failed", task_id)
            with db_factory() as session:
                task = session.query(ResearchTask).filter_by(task_id=task_id).first()
                if task:
                    task.status = "FAILED"
                    task.updated_at = _utc_now()
                    session.add(ResearchStep(
                        step_id="system_error", task_id=task_id, skill_name="research",
                        status="FAILED", error=str(exc)[:1200], duration_ms=0,
                    ))
                    session.commit()


@router.post("/research/tasks")
def create_task(
    req: ResearchTaskCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    user = authenticate_access_token(token, db)
    orchestrator = getattr(request.app, "research_orchestrator", None)
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Research 编排组件未初始化")
    if req.source is not None:
        return _create_guided_task(req, request, db, user)

    owned_ids = {
        row.uid for row in db.query(Document.uid).filter(Document.lid == user.workspace_lid).all()
    }
    if req.document_ids and not set(req.document_ids).issubset(owned_ids):
        raise HTTPException(status_code=403, detail="部分论文不在当前账号的资料库中")
    allowed_ids = list(dict.fromkeys(req.document_ids)) if req.document_ids else list(owned_ids)
    available_documents = [
        {"document_id": row.uid, "title": row.documentName}
        for row in db.query(Document.uid, Document.documentName).filter(Document.lid == user.workspace_lid).all()
        if row.uid in allowed_ids
    ]

    parent = None
    prior_artifacts = []
    if req.parent_task_id:
        parent = db.query(ResearchTask).filter(ResearchTask.task_id == req.parent_task_id, ResearchTask.lid == user.workspace_lid).first()
        if parent is None:
            raise HTTPException(status_code=404, detail="上一轮研究任务不存在")
        prior_artifacts = [json.loads(item.data_json) for item in db.query(Artifact).filter(Artifact.task_id == parent.task_id).all() if item.data_json]
    prior_digest = "\n".join(f"- {item.get('title', '')}: {str(item.get('markdown') or item.get('report') or item.get('papers') or item.get('raw') or '')[:500]}" for item in prior_artifacts[:4])
    planning_goal = req.goal if not parent else f"{req.goal}\n\n上一轮研究目标：{parent.goal}\n上一轮结果：\n{prior_digest[:1800]}"

    task_id = uuid.uuid4().hex[:12]
    task = ResearchTask(
        task_id=task_id,
        lid=user.workspace_lid,
        goal=req.goal,
        mode=req.mode,
        parent_task_id=req.parent_task_id,
        status="PENDING",
    )
    try:
        db.add(task)

        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Research 任务保存失败: {exc}") from exc
    db_factory = sessionmaker(bind=db.get_bind())
    background_tasks.add_task(
        _run_research_task, task_id, planning_goal, allowed_ids,
        req.parent_task_id, prior_artifacts, orchestrator,
        getattr(request.app, "llm", None), db_factory,
        user.workspace_lid, available_documents,
    )
    return {
        "status_code": 200,
        "msg": "Research task created",
        "data": {"task_id": task_id, "status": "PENDING"},
    }


@router.get("/research/tasks")
def list_tasks(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    user = authenticate_access_token(token, db)
    tasks = (
        db.query(ResearchTask)
        .filter(ResearchTask.lid == user.workspace_lid)
        .order_by(ResearchTask.created_at.desc())
        .all()
    )
    return {
        "status_code": 200,
        "msg": "ok",
        "data": [
            {
                "task_id": t.task_id,
                "goal": t.goal,
                "status": t.status,
                "mode": t.mode,
                "parent_task_id": t.parent_task_id,
                "created_at": _utc_iso(t.created_at),
                "updated_at": _utc_iso(t.updated_at),
                "review_deadline": _utc_iso(t.updated_at + timedelta(seconds=guided.NODE_REVIEW_SECONDS))
                if t.status == "AWAITING_INPUT" and t.updated_at else None,
            }
            for t in tasks
        ],
    }


def saved_deliverables(db: Session, task_id: str, *, include_report: bool = True) -> list[dict]:
    records = db.query(Artifact).filter_by(task_id=task_id)
    if not include_report:
        records = records.filter(Artifact.type != "research_report")
    artifacts = [
        {"artifact_id": item.artifact_id, "type": item.type, "title": item.title,
         "data": json.loads(item.data_json) if item.data_json else {}}
        for item in records.order_by(Artifact.id)
    ]
    reports = [item for item in artifacts if item["type"] == "research_report"]
    if not reports:
        return artifacts
    primary = next(
        (item for item in reports if (item["data"] or {}).get("origin") == "reviewed_defense_version"),
        reports[0],
    )
    return [primary, *(item for item in artifacts if item["type"] != "research_report")]


@router.get("/research/tasks/{task_id}")
def get_task(
    task_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    user = authenticate_access_token(token, db)
    task = db.query(ResearchTask).filter(
        ResearchTask.task_id == task_id, ResearchTask.lid == user.workspace_lid
    ).first()
    if task is None:
        return {"status_code": 404, "msg": "任务不存在"}
    row = db.get(GuidedResearch, task_id)
    if row:
        state = guided.load(row)
        data = {
            "task_id": task_id, "goal": task.goal, "status": task.status,
            "parent_task_id": task.parent_task_id,
            "created_at": _utc_iso(task.created_at), "updated_at": _utc_iso(task.updated_at),
            "review_deadline": _utc_iso(task.updated_at + timedelta(seconds=guided.NODE_REVIEW_SECONDS))
            if task.status == "AWAITING_INPUT" and task.updated_at else None,
        }
        if not guided.sources_available(db, user.workspace_lid, state):
            data.update(guided=True, revision=row.revision, source_unavailable=True, steps=[], artifacts=[])
        else:
            state.setdefault("goal", task.goal)
            saved = saved_deliverables(db, task_id, include_report=not state.get("saved_report_superseded"))
            data.update(guided.task_detail(
                state, task_id, row.revision, task.status,
                has_saved_report=bool(saved and saved[0]["type"] == "research_report"),
            ))
            data["artifacts"] = saved + data["artifacts"]
            if (data["artifacts"] and task.status in {"SUCCESS", "PARTIAL", "FAILED", "CANCELLED"}
                    or task.status == "FAILED" and state["plan_version"]):
                feedback = db.get(ResearchFeedback, (task_id, state["plan_version"], user.username))
                archived_runs = state.get("archived_runs", [])
                rewound_at = archived_runs[-1].get("rewound_at") if archived_runs else None
                if feedback and (not rewound_at or feedback.updated_at >= datetime.fromisoformat(rewound_at)):
                    data["feedback"] = feedback_summary(feedback)
        return {"status_code": 200, "data": data}
    steps = db.query(ResearchStep).filter(ResearchStep.task_id == task_id).all()
    return {
        "status_code": 200,
        "msg": "ok",
        "data": {
            "task_id": task.task_id,
            "goal": task.goal,
            "status": task.status,
            "parent_task_id": task.parent_task_id,
            "created_at": _utc_iso(task.created_at),
            "updated_at": _utc_iso(task.updated_at),
            "plan": json.loads(task.plan_json) if task.plan_json else None,
            "steps": [
                {
                    "step_id": s.step_id,
                    "skill_name": s.skill_name,
                    "status": s.status,
                    "error": s.error,
                    "duration_ms": s.duration_ms,
                }
                for s in steps
            ],
            "artifacts": saved_deliverables(db, task_id),
        },
    }
