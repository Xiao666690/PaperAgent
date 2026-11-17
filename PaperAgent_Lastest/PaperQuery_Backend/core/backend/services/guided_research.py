"""Durable guided research state transitions and worker."""
from __future__ import annotations

import json
import logging
import os
import threading
from time import monotonic
from datetime import datetime, timedelta, timezone

from openai import APITimeoutError
from sqlalchemy import and_, or_, select, update

from core.backend.db.models import Document, GuidedResearch, ResearchTask
from core.research.guided import (
    RESEARCH_BUDGETS, GuidedOperations, Question, ResearchResponseError, ResearchStreamInterrupted, ResearchStreamTimeout,
    event, execution_query, new_step, normalized, plan_node, report, save_plan, survey_findings, wants_structured_report, wants_survey,
)
from core.skills.web_search import WebSearchSkill

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 5
MAX_OPERATIONS = 30
NODE_REVIEW_SECONDS = 60
LEGACY_REPAIR_REASONS = {"根据校验结果调整当前节点的检索查询", "用户为当前节点指定补证查询"}


class OperationSuperseded(Exception):
    """The task was stopped or another worker owns its current revision."""


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def load(row: GuidedResearch) -> dict:
    state = json.loads(row.state_json)
    if not any(plan["reason"] in LEGACY_REPAIR_REASONS for plan in state["plans"]):
        return state

    # Older tasks counted local retries as plan revisions. Preserve the retry
    # events and attempts, and restore the approved query of each stable node.
    plans, versions, planned_queries = [], {0: 0}, {}
    for plan in state["plans"]:
        if plan["reason"] not in LEGACY_REPAIR_REASONS:
            for step in plan["steps"]:
                step["query"] = planned_queries.setdefault(step["step_id"], step["query"])
            plans.append({**plan, "version": len(plans) + 1})
        versions[plan["version"]] = len(plans)
    state.update(plans=plans, plan_version=len(plans))
    for step in state["steps"]:
        original = planned_queries.get(step["step_id"], step["query"])
        if step["query"] != original:
            step["retry_query"] = step["query"]
            step["query"] = original
        for attempt in step["attempts"]:
            attempt["plan_version"] = versions.get(attempt["plan_version"], attempt["plan_version"])
    for item in state["events"]:
        item["plan_version"] = versions.get(item["plan_version"], item["plan_version"])
        if item["title"] == "自动调整计划并补证":
            item["title"] = "自动调整检索查询并补证"
    return state


def save(db, task, row, state, status, *, lease=None):
    """Commit state and its visible task status with a revision guard."""
    result = db.execute(
        update(GuidedResearch)
        .where(GuidedResearch.task_id == row.task_id, GuidedResearch.revision == row.revision,
               GuidedResearch.state_json == row.state_json)
        .values(revision=row.revision + 1, state_json=json.dumps(state, ensure_ascii=False), lease_until=lease)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        return False
    task.status = status
    task.updated_at = utcnow()
    db.commit()
    return True


def documents(db, workspace: str) -> list[dict]:
    rows = db.query(Document).filter(Document.lid == workspace).order_by(Document.documentName, Document.id).all()
    return [
        {"id": doc.uid, "title": doc.documentName, "knowledge_id": doc.knowledgeID,
         "row_id": doc.id, "version": document_version(doc.documentPath)}
        for doc in rows
    ]


def document_version(path: str) -> list[int] | None:
    try:
        resolved = path if os.path.exists(path) else os.getenv("AcadeAgent_DIR", ".") + path
        stat = os.stat(resolved)
        return [stat.st_size, stat.st_mtime_ns]
    except OSError:
        return None


def sources_available(db, workspace: str, state: dict) -> bool:
    if not state["documents"]:
        return True
    rows = db.query(Document).filter(
        Document.lid == workspace, Document.id.in_([doc["row_id"] for doc in state["documents"]]),
    ).all()
    by_id = {row.id: row for row in rows}
    for doc in state["documents"]:
        row = by_id.get(doc["row_id"])
        if not row or (doc["id"], doc["knowledge_id"]) != (row.uid, row.knowledgeID):
            return False
        if "version" in doc and doc["version"] != document_version(row.documentPath):
            return False
    return True


def initial_state(source: str, selected: list[dict]) -> dict:
    state = {
        "source": source, "documents": selected, "phase": "plan", "plan_version": 0, "next_step": 1,
        "steps": [], "events": [], "plans": [], "review_step_id": None, "operations": 0,
    }
    event(state, "任务已创建", "正在生成待审阅计划")
    return state


def same_questions(steps: list[dict], questions: list[Question]) -> bool:
    return [(step["title"], step["query"], step.get("criteria", []), step.get("search_scope", "auto")) for step in steps] == [
        (question.title.strip(), question.query.strip(), question.criteria, question.search_scope) for question in questions
    ]


def record_plan_change(state: dict, reason: str):
    save_plan(state, reason)
    event(state, "计划已更新", reason)


def replace_future(state: dict, questions: list[Question], reason: str, *, objective_changed: bool = False):
    completed = [step for step in state["steps"] if step.get("reviewed")]
    pending = [step for step in state["steps"] if not step.get("reviewed")]
    if state["plans"] and same_questions(pending, questions):
        if not objective_changed:
            return False
        record_plan_change(state, reason)
        return True
    state["steps"] = completed
    for question in questions:
        state["steps"].append(new_step(f"s{state['next_step']}", question))
        state["next_step"] += 1
    record_plan_change(state, reason)
    return True


def finish_status(state: dict) -> str:
    if state["steps"] and all(step["quality"] == "VERIFIED" for step in state["steps"]):
        return "SUCCESS"
    if any(step["findings"] or step.get("papers") for step in state["steps"]):
        return "PARTIAL"
    if not state["steps"] or any(step["status"] == "FAILED" for step in state["steps"]):
        return "FAILED"
    return "NO_RESULTS"


def accept_node(state: dict, step: dict, *, automatic: bool = False):
    step["reviewed"] = True
    if automatic:
        step["review_mode"] = "automatic"
    if (step.get("issue") or {}).get("status") == "OPEN":
        step["issue"]["status"] = "ACCEPTED_GAP"
    title = "审阅超时，按原计划继续" if automatic else "用户审阅节点"
    if state["source"] == "discovery":
        detail = "保留本轮检索结果和覆盖范围"
    elif automatic or step["quality"] != "VERIFIED":
        detail = "保留已核验结果和未解决缺口"
    else:
        detail = "确认当前节点的核验结果"
    event(state, title, detail, step["step_id"])


def next_status(state: dict) -> str:
    state["review_step_id"] = None
    if any(not step.get("reviewed") for step in state["steps"]):
        return "QUEUED"
    if wants_structured_report(state) and survey_findings(state):
        state["phase"] = "synthesis"
        event(state, "研究发现已整理", "接下来撰写主报告")
        return "QUEUED"
    return finish_status(state)


def rewind(state: dict, step_id: str, questions: list[Question]) -> bool:
    for index, step in enumerate(state["steps"]):
        if step["step_id"] == step_id and step["attempts"]:
            break
    else:
        return False
    previous_steps = state["steps"][index:]
    content_changed = not same_questions(previous_steps, questions)
    state.setdefault("archived_runs", []).append({
        "plan_version": state["plan_version"], "from_step": index + 1, "steps": previous_steps,
        "difficulty": state.get("difficulty", "standard"), "rewound_at": utcnow().isoformat(),
    })
    state["steps"] = state["steps"][:index]
    for position, question in enumerate(questions):
        if content_changed:
            new_id = f"s{state['next_step']}"
            state["next_step"] += 1
        else:
            new_id = previous_steps[position]["step_id"]
        state["steps"].append(new_step(new_id, question))
    state["operations"] = 0
    state["active_seconds"] = 0
    state["phase"] = "research"
    state.pop("survey_synthesis", None)
    state["saved_report_superseded"] = True
    if content_changed:
        save_plan(state, f"用户从第 {index + 1} 步重新规划")
    event(state, "用户回退并修改计划" if content_changed else "用户回退并按原计划重做", step["title"], step_id)
    return True


def report_artifacts(state: dict, task_id: str, *, include_report: bool = True) -> list[dict]:
    artifacts = [report(state) if include_report else None]
    if len(state["documents"]) > 1:
        rows = [
            {"研究问题": step["title"], "核验结论": finding["text"],
             "原文出处": "；".join(f"{ref['title']} · 第 {ref['page']} 页" for ref in finding["references"])}
            for step in state["steps"] for finding in step["findings"]
            if finding.get("kind") == "cross_paper_comparison"
        ]
        if rows:
            artifacts.append({
                "type": "comparison_table", "title": "跨论文证据对照",
                "columns": ["研究问题", "核验结论", "原文出处"], "rows": rows,
            })
    for step in state["steps"]:
        if step.get("papers"):
            kind = "source_list" if any(item.get("source_type") == "web" for item in step["papers"]) else "paper_list"
            artifacts.append({"type": kind, "title": step["title"], "papers": step["papers"]})
    return [
        {"artifact_id": f"{task_id}-guided-{index}", "type": item["type"], "title": item["title"], "data": item}
        for index, item in enumerate(artifacts, start=1)
        if item is not None
    ]


def public_step(step: dict) -> dict:
    return {**step, "findings": [
            {**finding, "references": [
                {key: value for key, value in reference.items() if key != "text"}
                for reference in finding["references"]
            ]}
            for finding in step["findings"]
        ]}


def task_detail(state: dict, task_id: str, revision: int, status: str, *, has_saved_report: bool = False) -> dict:
    public_steps = [public_step(step) for step in state["steps"]]
    terminal = status in {"SUCCESS", "PARTIAL", "FAILED", "CANCELLED"}
    return {
        "guided": True,
        "revision": revision,
        "source": state["source"],
        "web_search_configured": WebSearchSkill.configured() if state["source"] == "discovery" else None,
        "documents": [{key: doc[key] for key in ("id", "title", "knowledge_id")} for doc in state["documents"]],
        "plan": {"steps": [plan_node(step) for step in public_steps]}
        if public_steps else None,
        "plan_version": state["plan_version"],
        "plan_history": state["plans"],
        "review_step_id": state["review_step_id"],
        "archived_runs": [{**run, "steps": [public_step(step) for step in run["steps"]]}
                          for run in state.get("archived_runs", [])],
        "assessment": state.get("assessment"),
        "objective": state.get("objective"),
        "preference": state.get("preference"),
        "difficulty": state.get("difficulty", "standard"),
        "review_policy": state.get("review_policy", "all"),
        "active_seconds": state.get("active_seconds", 0),
        "budgets": {key: {
            "first_output_seconds": budget.first_output_seconds, "idle_seconds": budget.idle_seconds,
            "automatic_repairs": budget.automatic_repairs, "effort": budget.effort,
        } for key, budget in RESEARCH_BUDGETS.items()},
        "steps": public_steps,
        "events": state["events"],
        "artifacts": report_artifacts(state, task_id, include_report=terminal and not has_saved_report)
        if terminal or wants_structured_report(state) else [],
    }


class GuidedResearchWorker:
    def __init__(self, db_factory, orchestrator):
        self.db_factory = db_factory
        self.operations = GuidedOperations(orchestrator)
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, name="guided-research", daemon=True)
        self.review_thread = threading.Thread(target=self.watch_reviews, name="guided-review-timeout", daemon=True)

    def watch_reviews(self):
        while not self.stop.wait(1):
            try:
                if self.expire_reviews():
                    self.wake.set()
            except Exception:
                logger.exception("Could not process expired research reviews")

    def expire_reviews(self) -> bool:
        cutoff = utcnow() - timedelta(seconds=NODE_REVIEW_SECONDS)
        with self.db_factory() as db:
            expired = db.execute(
                select(ResearchTask.id).join(GuidedResearch, GuidedResearch.task_id == ResearchTask.task_id)
                .where(ResearchTask.status == "AWAITING_INPUT", ResearchTask.updated_at <= cutoff)
            ).scalars().all()
        changed = False
        for task_id in expired:
            with self.db_factory() as db:
                task = db.get(ResearchTask, task_id)
                if not task or task.status != "AWAITING_INPUT" or task.updated_at > cutoff:
                    continue
                row = db.get(GuidedResearch, task.task_id)
                state = load(row)
                step = next((item for item in state["steps"] if item["step_id"] == state["review_step_id"]), None)
                if not step:
                    continue
                if sources_available(db, task.lid, state):
                    accept_node(state, step, automatic=True)
                    status = next_status(state)
                else:
                    event(state, "论文范围已变化", "自动继续已停止")
                    status = "FAILED"
                changed = save(db, task, row, state, status) or changed
        return changed

    def run(self):
        while not self.stop.is_set():
            try:
                if self.tick():
                    continue
            except Exception:
                logger.exception("Guided research worker failed to process a task")
            self.wake.wait(2)
            self.wake.clear()

    def tick(self) -> bool:
        with self.db_factory() as db:
            candidate = db.execute(
                select(ResearchTask, GuidedResearch)
                .join(GuidedResearch, GuidedResearch.task_id == ResearchTask.task_id)
                .where(or_(
                    ResearchTask.status == "QUEUED",
                    and_(ResearchTask.status == "RUNNING", GuidedResearch.lease_until <= utcnow()),
                ))
                .order_by(ResearchTask.updated_at, ResearchTask.task_id)
                .limit(1)
            ).first()
            if candidate is None:
                return False
            task, row = candidate
            state = load(row)
            task_pk, task_id, goal, workspace = task.id, task.task_id, task.goal, task.lid
            state.setdefault("goal", goal)
            revision = row.revision + 1
            writing_survey = state["phase"] == "synthesis"
            if not writing_survey and state["operations"] >= MAX_OPERATIONS:
                event(state, "任务已达到执行次数上限", "已保存当前结果，可查看研究轨迹")
                save(db, task, row, state, finish_status(state) if state["steps"] else "FAILED")
                return True
            state["operations"] += 1
            if task.status == "RUNNING":
                event(state, "从检查点恢复", "继续执行尚未完成的操作")
            step = next((item for item in state["steps"] if not item.get("reviewed")), None)
            if state["phase"] == "plan":
                event(state, "评估难度并生成研究计划")
            elif writing_survey:
                event(state, "综合撰写研究报告", "使用已经保存的研究发现")
            elif step:
                step["status"] = "RUNNING"
                event(state, "执行研究节点", execution_query(step), step["step_id"])
            if not save(db, task, row, state, "RUNNING", lease=utcnow() + timedelta(minutes=10)):
                return True

        def progress(title, detail):
            event(state, title, detail, step["step_id"] if step else None)
            with self.db_factory() as db:
                result = db.execute(
                    update(GuidedResearch)
                    .where(GuidedResearch.task_id == task_id, GuidedResearch.revision == revision)
                    .values(state_json=json.dumps(state, ensure_ascii=False), lease_until=utcnow() + timedelta(minutes=10))
                )
                if result.rowcount != 1:
                    raise OperationSuperseded
                db.get(ResearchTask, task_pk).updated_at = utcnow()
                db.commit()

        started_at = monotonic()
        research_operation = state["phase"] in {"research", "synthesis"}
        try:
            with self.db_factory() as db:
                available = sources_available(db, workspace, state)
            if not available:
                event(state, "论文范围已变化", "部分论文已移除或无权访问，请重新创建任务")
                status = "FAILED"
            elif state["phase"] == "plan":
                outline = self.operations.outline(goal, state, progress)
                state["assessment"] = {"difficulty": outline.difficulty, "reason": outline.reason}
                state["difficulty"] = outline.difficulty
                state["objective"] = outline.objective.strip() or goal
                event(state, "难度预评估已完成", outline.reason)
                replace_future(state, outline.questions, "根据研究目标和难度生成初始计划")
                state["phase"] = "research"
                status = "AWAITING_APPROVAL"
            elif writing_survey:
                state["survey_synthesis"] = self.operations.synthesize_survey(state, progress)
                event(state, "已交付文献综述" if wants_survey(state) else "已交付研究报告")
                status = finish_status(state)
            elif step:
                result = self.operations.run_step(goal, state, step, self.db_factory, workspace, progress)
                result["duration_seconds"] = round(monotonic() - started_at, 2)
                status = self.record_result(state, step, result)
            else:
                status = finish_status(state)
        except OperationSuperseded:
            return True
        except (TimeoutError, APITimeoutError, ResearchStreamInterrupted) as exc:
            detail = str(exc) if isinstance(exc, (ResearchStreamTimeout, ResearchStreamInterrupted)) else "当前操作停止响应"
            state["operations"] -= 1
            if step and state["phase"] == "research":
                step["status"] = "PENDING"
            event(state, "输出中断，等待继续", f"{detail}。已保存研究进度。", step["step_id"] if step else None)
            status = "WAITING_RETRY"
        except Exception as exc:
            logger.exception("Guided research operation failed for %s", task_id)
            if writing_survey:
                event(state, "已交付阶段性结果", "综合撰写未完成，已整理本轮发现，可直接阅读和导出")
                status = finish_status(state)
            elif step and state["phase"] == "research":
                discovery = state["source"] == "discovery"
                reason = "检索或整理未能完成，请调整查询或重试。" if discovery else "检索或校验未能完成，请调整查询或重试。"
                if isinstance(exc, ResearchResponseError):
                    reason = "模型重试后仍未返回有效的结构化结果。已保留此前核验通过的结论。"
                status = self.record_result(state, step, {
                    "findings": step["findings"], "complete": False, "execution_failed": True,
                    "reason": reason,
                    "duration_seconds": round(monotonic() - started_at, 2),
                })
            else:
                state["assessment"] = {"difficulty": None, "reason": "未取得模型评估，以下是可编辑的备用草案。"}
                state["difficulty"] = "standard"
                state["objective"] = goal
                replace_future(state, [Question(title=goal[:240], query=goal[:300])], "规划请求未完成，等待用户调整")
                state["phase"] = "research"
                status = "AWAITING_APPROVAL"
        if research_operation:
            state["active_seconds"] = round(state.get("active_seconds", 0) + monotonic() - started_at, 2)

        with self.db_factory() as db:
            task = db.get(ResearchTask, task_pk)
            row = db.get(GuidedResearch, task_id)
            if task and row and row.revision == revision:
                if not sources_available(db, workspace, state):
                    event(state, "论文范围已变化", "已停止提交本次操作结果")
                    save(db, task, row, load(row) | {"events": state["events"]}, "FAILED")
                else:
                    save(db, task, row, state, status)
        return True

    @staticmethod
    def record_result(state: dict, step: dict, result: dict) -> str:
        step["findings"] = result["findings"]
        step["reason"] = result["reason"]
        if "missing_criteria" in result:
            step["missing_criteria"] = result["missing_criteria"]
        elif not step["findings"] and not result["complete"]:
            step["missing_criteria"] = step.get("criteria", [])
        if result.get("papers"):
            step["papers"] = result["papers"]
        step["attempts"].append({
            "query": execution_query(step), "plan_version": state["plan_version"], "reason": result["reason"],
            "retrieved": result.get("retrieved", 0), "rejected": result.get("rejected", 0),
            "duration_seconds": result.get("duration_seconds"),
            "findings": [{
                "text": finding["text"],
                "references": [
                    {key: reference[key] for key in ("document_id", "knowledge_id", "title", "page", "quote", "url")
                     if key in reference}
                    for reference in finding["references"]
                ],
            } for finding in step["findings"]],
        })
        step["status"] = "FAILED" if result.get("execution_failed") else "SUCCESS"
        step["quality"] = "VERIFIED" if result["complete"] else "NEED_MORE_EVIDENCE"
        if result["complete"]:
            if step.get("issue"):
                step["issue"].update(status="RESOLVED", resolution=result["reason"])
        else:
            issue_type = "SEARCH_GAP" if state["source"] == "discovery" else "EVIDENCE_GAP"
            step["issue"] = {
                "id": f"{step['step_id']}-evidence", "status": "OPEN",
                "type": "OPERATION_FAILED" if result.get("execution_failed") else issue_type,
                "detail": result["reason"], "repair_query": result.get("repair_query", ""),
            }
        discovery = state["source"] == "discovery"
        if result.get("execution_failed"):
            title = "节点执行异常"
        elif discovery:
            title = "节点检索完成" if result["complete"] else "已记录检索缺口"
        else:
            title = "节点核验通过" if result["complete"] else "已记录证据缺口"
        event(state, title, result["reason"], step["step_id"])
        repair = result.get("repair_query", "").strip() or step["title"]
        targeted_search = discovery and wants_structured_report(state) and result.get("missing_criteria") and result.get("repair_query", "").strip()
        searched = {normalized(attempt["query"]) for attempt in step["attempts"]}
        switching_to_index = state.get("difficulty") == "quick" and len(state["documents"]) == 1 and len(step["attempts"]) == 1
        if (
            (not result["complete"] or targeted_search) and not result.get("execution_failed")
            and step.get("automatic_repairs", 0) < RESEARCH_BUDGETS[state.get("difficulty", "standard")].automatic_repairs
            and len(step["attempts"]) < MAX_ATTEMPTS and (switching_to_index or normalized(repair) not in searched)
        ):
            step["automatic_repairs"] = step.get("automatic_repairs", 0) + 1
            step["retry_query"] = repair
            step["status"] = "PENDING"
            title = "自动调整关键词继续检索" if discovery else "切换到索引补证" if switching_to_index else "自动调整检索查询并补证"
            event(state, title, repair, step["step_id"])
            return "QUEUED"
        if (
            state.get("review_policy") == "checkpoints" and result["complete"]
            and any(item is not step and not item.get("reviewed") for item in state["steps"])
        ):
            step.update(reviewed=True, review_mode="checkpoint_skipped")
            event(state, "按已批准的审批策略继续", "节点已完成，直接执行下一步", step["step_id"])
            return next_status(state)
        state["review_step_id"] = step["step_id"]
        event(state, "等待人工审阅", step["title"], step["step_id"])
        return "AWAITING_INPUT"
