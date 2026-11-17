import json
import asyncio
from datetime import timedelta
from types import SimpleNamespace

import fitz
import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.backend.db.models import Artifact, Base, Document, GuidedResearch, ResearchTask, User
from core.backend.router.router_research import get_db, router
from core.backend.services.guided_research import GuidedResearchWorker, load, utcnow
from core.research.guided import collect_json_stream, diversify_evidence, verification_evidence
from core.research.guided import report, ResearchStreamInterrupted
from core.research.schemas import PlanStep, StepResult, TaskPlan
from core.research.verifier import Verifier
from core.skills.base import SkillResult
from core.skills.paper_reader import PaperReaderSkill
from core.skills.paper_search import PaperSearchSkill
from core.skills.web_search import WebSearchSkill


QUOTE = "Model B achieved F1 of 0.87 on the test split."


class ScriptedModel:
    def invoke(self, prompt):
        payload = json.loads(prompt.split("\n数据：", 1)[1].split("\n重新生成", 1)[0])
        if prompt.startswith("根据用户研究目标"):
            if "测试集 F1" in payload["goal"] or "准确率是多少" in payload["goal"]:
                return json.dumps({"difficulty": "quick", "reason": "只需定位一个指标",
                                   "questions": [{"title": "定位准确率", "query": "test accuracy"}]})
            return json.dumps({"difficulty": "standard", "reason": "包含三个独立问题", "questions": [
                {"title": "核验模型 B 的结果", "query": "initial"},
                {"title": "第二个问题", "query": "second"},
                {"title": "第三个问题", "query": "third"},
            ]})
        if prompt.startswith("针对当前问题"):
            if "Distractor" in prompt:
                return json.dumps({"findings": [{"text": "Fabricated", "references": [{"evidence_id": "E1", "quote": "Fake F1 of 0.99"}]}]})
            return json.dumps({"findings": [{"text": QUOTE, "references": [{"evidence_id": "E1", "quote": QUOTE}]}]})
        criteria = payload.get("criteria", [])
        return json.dumps({"supported": [0], "complete": True, "reason": "原文支持该结论",
                           "coverage": {str(index): [0] for index in range(len(criteria))}})


class Retrieval:
    async def run(self, data, context):
        assert data["document_ids"] == context["allowed_document_ids"] == ["paper-b"]
        text = "Distractor Fake F1 of 0.99" if data["query"] == "initial" else QUOTE
        return SkillResult(ok=True, output={"evidence": [
            {"document_id": "paper-b", "page_number": 1, "chunk_id": "chunk", "text": text}
        ]})


@pytest.fixture
def harness(tmp_path, monkeypatch):
    pdf = fitz.open()
    pdf.new_page().insert_text((72, 72), QUOTE)
    path = tmp_path / "paper.pdf"
    pdf.save(path)
    pdf.close()
    engine = create_engine(f"sqlite:///{tmp_path / 'guided.sqlite'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add_all([
            User(username="alice", password="unused", lid="alice"),
            User(username="bob", password="unused", lid="bob"),
            Document(uid="paper-b", knowledgeID="library", lid="alice", documentName="Paper B", documentPath=str(path)),
        ])
        db.commit()
    monkeypatch.setenv("SECRET_KEY", "test-guided-research-signing-key-only")
    monkeypatch.setenv("ALGORITHM", "HS256")
    app = FastAPI()
    app.include_router(router)
    app.research_orchestrator = SimpleNamespace(
        planner=SimpleNamespace(llm=ScriptedModel()),
        executor=SimpleNamespace(registry={"local_retrieval": Retrieval(), "paper_reader": PaperReaderSkill()}, ctx={}),
    )
    worker = GuidedResearchWorker(sessions, app.research_orchestrator)

    def database():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        def headers(name="alice"):
            token = jwt.encode({"username": name}, "test-guided-research-signing-key-only", algorithm="HS256")
            return {"Authorization": f"Bearer {token}"}

        yield client, headers, worker, sessions
    engine.dispose()


@pytest.mark.parametrize(("account", "goal", "selected", "source"), [
    ("alice", "总结技术路线", [], "discovery"),
    ("alice", "联网查找相关论文", [], "discovery"),
    ("alice", "检索相关外部文献", ["paper-b"], "library"),
    ("alice", "不要检索外部文献，只总结技术路线", [], None),
    ("alice", "解释这篇 ArXiv 论文的实验", [], "discovery"),
    ("bob", "总结技术路线", [], "discovery"),
    ("bob", "不要联网，梳理技术路线", [], None),
])
def test_choose_research_source_from_goal_and_selection(harness, account, goal, selected, source):
    client, headers, _, _ = harness
    response = client.post("/research/tasks", headers=headers(account), json={
        "goal": goal, "source": "auto", "document_ids": selected,
    })
    if source is None:
        assert response.status_code == 422
        return
    assert response.status_code == 200
    task_id = response.json()["data"]["task_id"]
    detail = client.get(f"/research/tasks/{task_id}", headers=headers(account)).json()["data"]
    assert detail["source"] == source
    assert [document["id"] for document in detail["documents"]] == (["paper-b"] if source == "library" else [])


def test_guided_review_repair_and_replan(harness):
    client, headers, worker, sessions = harness
    response = client.post("/research/tasks", headers=headers(), json={
        "goal": "对比实验", "source": "library", "document_ids": ["paper-b"],
    })
    assert response.status_code == 200
    task_id = response.json()["data"]["task_id"]
    path = f"/research/tasks/{task_id}"

    def get():
        return client.get(path, headers=headers()).json()["data"]

    def review(detail, action, **values):
        return client.post(path + "/review", headers=headers(), json={
            "revision": detail["revision"], "action": action, **values,
        })

    assert worker.tick()
    first = get()
    assert first["status"] == "AWAITING_APPROVAL"
    assert not worker.tick()
    assert review(first, "continue").status_code == 200
    assert review(first, "continue").status_code == 409
    assert worker.tick()
    repairing = get()
    assert repairing["status"] == "QUEUED"
    assert repairing["plan_version"] == 1
    assert repairing["plan_history"] == first["plan_history"]
    assert repairing["steps"][0]["query"] == "initial"
    assert repairing["steps"][0]["attempts"][0]["rejected"] == 1
    assert repairing["steps"][0]["findings"] == []
    assert worker.tick()
    checked = get()
    assert checked["status"] == "AWAITING_INPUT"
    assert checked["steps"][0]["issue"]["status"] == "RESOLVED"
    assert checked["steps"][0]["findings"][0]["references"][0]["quote"] == QUOTE
    assert checked["steps"][0]["attempts"][1]["query"] != "initial"
    assert checked["steps"][0]["attempts"][1]["plan_version"] == 1
    assert not worker.tick()
    assert review(checked, "repair", query="manual evidence query").status_code == 200
    assert worker.tick()
    checked = get()
    assert checked["plan_history"] == first["plan_history"]
    assert checked["steps"][0]["attempts"][-1]["query"] == "manual evidence query"
    assert review(checked, "revise", questions=[{"title": "补查测试集", "query": "test split"}]).status_code == 200
    revised = get()
    assert revised["plan_version"] == 2
    assert revised["steps"][0] == {**checked["steps"][0], "reviewed": True}
    assert revised["steps"][1]["title"] == "补查测试集"
    assert len(revised["plan_history"][0]["steps"]) == 3
    assert worker.tick()
    final_review = get()
    assert final_review["status"] == "AWAITING_INPUT"
    assert final_review["review_deadline"]
    assert not worker.expire_reviews()
    with sessions() as db:
        db.query(ResearchTask).filter_by(task_id=task_id).one().updated_at = utcnow() - timedelta(seconds=61)
        db.commit()
    assert review(final_review, "continue").status_code == 409
    assert worker.expire_reviews()
    assert not worker.expire_reviews()
    finished = get()
    assert finished["status"] == "SUCCESS"
    assert finished["plan_version"] == 2
    assert QUOTE in finished["artifacts"][0]["data"]["markdown"]
    assert "Fabricated" not in finished["artifacts"][0]["data"]["markdown"]
    assert finished["steps"][1]["reviewed"]
    assert finished["events"][-1]["title"] == "审阅超时，按原计划继续"
    assert client.post(path + "/review", headers=headers("bob"), json={"revision": finished["revision"], "action": "cancel"}).status_code == 404
    assert review(finished, "rewind", step_id=finished["steps"][1]["step_id"],
                  questions=[{"title": "重做对比", "query": "new comparison"}]).status_code == 200
    rewound = get()
    assert rewound["status"] == "QUEUED"
    assert rewound["plan_version"] == 3
    assert rewound["steps"][0] == finished["steps"][0]
    assert rewound["steps"][1]["step_id"] != finished["steps"][1]["step_id"]
    assert rewound["archived_runs"][0]["steps"] == finished["steps"][1:]
    assert worker.tick()
    assert get()["review_step_id"] == rewound["steps"][1]["step_id"]

    with sessions() as db:
        db.query(Document).filter_by(uid="paper-b").delete()
        db.commit()
    assert get()["source_unavailable"]
    assert not get()["artifacts"]


def test_old_retry_versions_keep_query_history_without_counting_as_plan_edits():
    original = {"step_id": "s1", "title": "Research", "query": "approved"}
    changed = {**original, "query": "retry"}
    replacement = {"step_id": "s2", "title": "Next", "query": "new"}
    row = SimpleNamespace(state_json=json.dumps({
        "plan_version": 3,
        "plans": [
            {"version": 1, "reason": "初始计划", "steps": [original]},
            {"version": 2, "reason": "根据校验结果调整当前节点的检索查询", "steps": [changed]},
            {"version": 3, "reason": "用户修改节点", "steps": [changed, replacement]},
        ],
        "steps": [{**changed, "attempts": [{"query": "retry", "plan_version": 2}]}],
        "events": [{"plan_version": 2, "title": "自动调整计划并补证", "detail": "retry"}],
    }))
    state = load(row)
    assert state["plan_version"] == 2
    assert state["plans"][1]["steps"] == [original, replacement]
    assert state["steps"][0]["query"] == "approved"
    assert state["steps"][0]["retry_query"] == "retry"
    assert state["steps"][0]["attempts"] == [{"query": "retry", "plan_version": 1}]
    assert state["events"] == [{"plan_version": 1, "title": "自动调整检索查询并补证", "detail": "retry"}]


def test_difficulty_approval_and_checkpoint_policy(harness):
    client, headers, worker, _ = harness
    task = client.post("/research/tasks", headers=headers(), json={
        "goal": "准确率是多少", "source": "library",
    }).json()["data"]
    path = f"/research/tasks/{task['task_id']}"

    def get():
        return client.get(path, headers=headers()).json()["data"]

    assert worker.tick()
    initial = get()
    assert initial["status"] == "AWAITING_APPROVAL"
    assert initial["assessment"]["difficulty"] == "quick"
    assert initial["budgets"]["quick"]["automatic_repairs"] == 1
    assert len(initial["steps"]) == 1
    approval = client.post(path + "/review", headers=headers(), json={
        "revision": initial["revision"], "action": "revise", "difficulty": "deep",
        "review_policy": "checkpoints", "questions": [
            {"title": "核对指标", "query": "test metric"},
            {"title": "复核测试集", "query": "test split"},
        ],
    })
    assert approval.status_code == 200
    assert worker.tick()
    interim = get()
    assert interim["status"] == "QUEUED"
    assert interim["plan_version"] == 2
    assert interim["difficulty"] == "deep"
    assert interim["steps"][0]["review_mode"] == "checkpoint_skipped"
    assert worker.tick()
    assert get()["status"] == "AWAITING_INPUT"


def test_quick_research_reads_pdf_and_retries_invalid_verifier_indices(harness):
    client, headers, worker, _ = harness

    class RecoveringModel(ScriptedModel):
        verdicts = 0

        def invoke(self, prompt):
            if prompt.startswith("独立验收"):
                self.verdicts += 1
                if self.verdicts == 1:
                    return json.dumps({"supported": [9], "complete": True, "reason": "无效编号"})
            return super().invoke(prompt)

    model = RecoveringModel()
    worker.operations.llm = model
    task = client.post("/research/tasks", headers=headers(), json={
        "goal": "测试集 F1 是多少", "source": "library",
    }).json()["data"]
    path = f"/research/tasks/{task['task_id']}"
    assert worker.tick()
    initial = client.get(path, headers=headers()).json()["data"]
    for questions in [[], None]:
        response = client.post(path + "/review", headers=headers(), json={
            "revision": initial["revision"], "action": "revise" if questions is not None else "continue",
            "questions": questions,
        })
        assert response.status_code == (422 if questions is not None else 200)
    assert worker.tick()
    reviewed = client.get(path, headers=headers()).json()["data"]
    assert reviewed["status"] == "AWAITING_INPUT"
    assert model.verdicts == 2
    assert reviewed["steps"][0]["quality"] == "VERIFIED"
    reference = reviewed["steps"][0]["findings"][0]["references"][0]
    assert reference["chunk_id"].startswith("pdf:")
    assert reference["quote"] == QUOTE
    response = client.post(path + "/review", headers=headers(), json={"revision": reviewed["revision"], "action": "continue"})
    assert response.status_code == 200
    feedback = {"plan_version": 1, "rating": "unsatisfied", "reason": "too_verbose",
                "note": "希望直接看数值", "preference": "concise"}
    assert client.put(path + "/feedback", headers=headers("bob"), json=feedback).status_code == 404
    assert client.put(path + "/feedback", headers=headers(), json=feedback | {"plan_version": 2}).status_code == 409
    assert client.put(path + "/feedback", headers=headers(), json=feedback).status_code == 200
    assert client.put(path + "/feedback", headers=headers(), json=feedback | {"note": "更新意见"}).status_code == 200
    saved = client.get(path, headers=headers()).json()["data"]
    assert saved["feedback"]["note"] == "更新意见"
    another = client.post("/research/tasks", headers=headers(), json={"goal": "测试集 F1 是多少", "source": "library"}).json()["data"]
    new_task = client.get(f"/research/tasks/{another['task_id']}", headers=headers()).json()["data"]
    assert new_task["preference"] == "concise"
    assert "更新意见" not in str(new_task)


@pytest.mark.parametrize("action", ["continue", "revise"])
def test_execution_settings_leave_plan_version_unchanged(harness, action):
    client, headers, worker, _ = harness
    task = client.post("/research/tasks", headers=headers(), json={
        "goal": "测试集 F1 是多少", "source": "library",
    }).json()["data"]
    path = f"/research/tasks/{task['task_id']}"

    def read():
        return client.get(path, headers=headers()).json()["data"]

    def review(detail, action, **values):
        response = client.post(path + "/review", headers=headers(), json={
            "revision": detail["revision"], "action": action, **values,
        })
        assert response.status_code == 200

    assert worker.tick()
    initial = read()
    questions = initial["plan"]["steps"]
    review(initial, action, difficulty="deep", review_policy="checkpoints",
           **({"questions": questions} if action == "revise" else {}))
    approved = read()
    assert approved["difficulty"] == "deep"
    assert approved["review_policy"] == "checkpoints"
    assert approved["plan_version"] == 1
    assert approved["plan_history"] == initial["plan_history"]
    assert approved["plan"] == initial["plan"]
    assert [item["title"] for item in approved["events"][-2:]] == ["用户调整执行难度", "用户调整审批方式"]

    assert worker.tick()
    checked = read()
    review(checked, "rewind", step_id=questions[0]["step_id"], questions=questions, difficulty="quick")
    rerun = read()
    assert rerun["status"] == "QUEUED"
    assert rerun["difficulty"] == "quick"
    assert rerun["plan_history"] == initial["plan_history"]
    assert rerun["plan_version"] == 1
    assert rerun["plan"] == initial["plan"]
    assert rerun["steps"][0]["attempts"] == []
    assert rerun["archived_runs"][0]["difficulty"] == "deep"
    assert rerun["archived_runs"][0]["steps"] == checked["steps"]


def test_quick_setting_keeps_all_planned_nodes(harness):
    client, headers, worker, _ = harness
    task = client.post("/research/tasks", headers=headers(), json={
        "goal": "梳理代表性技术路线", "source": "library",
    }).json()["data"]
    path = f"/research/tasks/{task['task_id']}"
    assert worker.tick()
    initial = client.get(path, headers=headers()).json()["data"]
    assert len(initial["steps"]) == 3
    approval = client.post(path + "/review", headers=headers(), json={
        "revision": initial["revision"], "action": "continue", "difficulty": "quick",
    })
    assert approval.status_code == 200
    approved = client.get(path, headers=headers()).json()["data"]
    assert approved["difficulty"] == "quick"
    assert approved["plan_version"] == 1
    assert approved["plan"] == initial["plan"]
    assert worker.tick()
    step_review = client.get(path, headers=headers()).json()["data"]
    assert step_review["status"] == "AWAITING_INPUT"
    assert client.post(path + "/review", headers=headers(), json={
        "revision": step_review["revision"], "action": "continue", "difficulty": "deep",
    }).status_code == 200
    continued = client.get(path, headers=headers()).json()["data"]
    assert continued["difficulty"] == "deep"
    assert continued["plan_version"] == 1
    assert continued["plan"] == initial["plan"]


def test_required_answer_items_and_citations_survive_a_partial_result(harness):
    client, headers, worker, sessions = harness

    class CoverageModel(ScriptedModel):
        def invoke(self, prompt):
            if prompt.startswith("根据用户研究目标"):
                return json.dumps({"difficulty": "quick", "reason": "同一实验", "objective": "核对测试指标",
                                   "questions": [{"title": "报告指标", "query": "test split F1", "criteria": ["给出 F1", "给出 Accuracy"]}]})
            if prompt.startswith("独立验收"):
                return json.dumps({"supported": [0], "complete": True, "reason": "原文支持 F1",
                                   "coverage": {"0": [0]}, "repair_query": "accuracy"})
            return super().invoke(prompt)

    worker.operations.llm = CoverageModel()
    task = client.post("/research/tasks", headers=headers(), json={"goal": "给出 F1 和 Accuracy", "source": "library"}).json()["data"]
    path = f"/research/tasks/{task['task_id']}"
    assert worker.tick()
    read = lambda: client.get(path, headers=headers()).json()["data"]
    initial = read()
    assert initial["objective"] == "核对测试指标"
    assert initial["plan"]["steps"][0]["criteria"] == ["给出 F1", "给出 Accuracy"]
    assert client.post(path + "/review", headers=headers(), json={
        "revision": initial["revision"], "action": "continue", "objective": "核对测试集的两个指标",
    }).status_code == 200
    with sessions() as db:
        row = db.get(GuidedResearch, task["task_id"])
        state = json.loads(row.state_json)
        state["active_seconds"] = 310
        row.state_json = json.dumps(state)
        db.commit()
    assert worker.tick()
    assert worker.tick()
    review = read()
    assert review["status"] == "AWAITING_INPUT"
    assert review["steps"][0]["missing_criteria"] == ["给出 Accuracy"]
    assert review["plan_version"] == 2
    assert client.post(path + "/review", headers=headers(), json={"revision": review["revision"], "action": "continue"}).status_code == 200
    final = read()
    assert final["status"] == "PARTIAL"
    markdown = final["artifacts"][0]["data"]["markdown"]
    assert "核对测试集的两个指标" in markdown
    assert "尚未回答：给出 Accuracy" in markdown
    assert "/home/pdfInfo/library/paper-b?page=1" in markdown


@pytest.mark.parametrize("missing", [[], [0]])
def test_open_research_summarizes_search_with_public_links(harness, missing):
    client, headers, worker, _ = harness

    class DiscoveryModel(ScriptedModel):
        summary_calls = 0

        def invoke(self, prompt):
            if prompt.startswith("根据用户研究目标"):
                return json.dumps({"difficulty": "quick", "reason": "检索论文",
                                   "questions": [{"title": "梳理方法", "query": "time series forecasting",
                                                  "criteria": ["梳理预测方法及测试结果"]}]})
            assert prompt.startswith("根据公开学术搜索结果")
            self.summary_calls += 1
            return json.dumps({"findings": [{"text": "该方法用于时间序列预测",
                                             "sources": [9 if self.summary_calls == 1 else 1]}],
                               "missing_criteria": missing, "reason": "整理公开摘要"})

    class Search:
        async def run(self, data, context):
            assert context["allowed_document_ids"] == []
            return SkillResult(ok=True, output={"papers": [
                {"title": "Forecasting paper", "doi": "https://doi.org/10.1234/synthetic",
                 "summary": "We present a method for time series forecasting."}
            ]})

    model = DiscoveryModel()
    worker.operations.llm = model
    worker.operations.executor.registry = {"paper_search": Search()}
    task = client.post("/research/tasks", headers=headers(), json={
        "goal": "梳理时间序列预测并总结研究结果", "source": "auto",
    }).json()["data"]
    path = f"/research/tasks/{task['task_id']}"

    def approve(expected):
        detail = client.get(path, headers=headers()).json()["data"]
        assert detail["status"] == expected
        assert detail["source"] == "discovery"
        assert detail["documents"] == []
        assert client.post(path + "/review", headers=headers(), json={"revision": detail["revision"], "action": "continue"}).status_code == 200

    assert worker.tick()
    approve("AWAITING_APPROVAL")
    assert worker.tick()
    approve("AWAITING_INPUT")
    final = client.get(path, headers=headers()).json()["data"]
    assert final["status"] == "SUCCESS"
    assert model.summary_calls == 2
    assert final["artifacts"][0]["type"] == "research_report"
    markdown = final["artifacts"][0]["data"]["markdown"]
    assert "[Forecasting paper](https://doi.org/10.1234/synthetic)" in markdown
    assert ("本轮未覆盖" in markdown) == bool(missing)
    assert final["steps"][0]["attempts"][0]["findings"][0]["references"][0]["url"] == "https://doi.org/10.1234/synthetic"


@pytest.mark.parametrize("search_failed", [False, True])
def test_empty_search_is_distinct_from_an_execution_failure(harness, search_failed):
    client, headers, worker, _ = harness

    class Search:
        async def run(self, data, context):
            return SkillResult(ok=not search_failed, output={"papers": []})

    worker.operations.executor.registry = {"paper_search": Search()}
    task = client.post("/research/tasks", headers=headers(), json={
        "goal": "测试集 F1 是多少", "source": "auto",
    }).json()["data"]
    path = f"/research/tasks/{task['task_id']}"

    def approve(status):
        detail = client.get(path, headers=headers()).json()["data"]
        assert detail["status"] == status
        assert client.post(path + "/review", headers=headers(), json={
            "revision": detail["revision"], "action": "continue",
        }).status_code == 200
        return detail

    assert worker.tick()
    approve("AWAITING_APPROVAL")
    assert worker.tick()
    if not search_failed:
        assert worker.tick()
    step = approve("AWAITING_INPUT")["steps"][0]
    assert step["status"] == ("FAILED" if search_failed else "SUCCESS")
    assert step["issue"]["type"] == ("OPERATION_FAILED" if search_failed else "SEARCH_GAP")
    final = client.get(path, headers=headers()).json()["data"]
    assert final["status"] == ("FAILED" if search_failed else "NO_RESULTS")


@pytest.mark.parametrize("arxiv_failed,openalex_failed", [(False, False), (False, True), (True, False), (True, True)])
def test_paper_search_distinguishes_provider_errors_from_no_matches(monkeypatch, arxiv_failed, openalex_failed):
    from arxiv_client import ArxivClient

    def arxiv_results(*args):
        if arxiv_failed:
            raise RuntimeError("arXiv unavailable")
        return []

    def openalex_get(*args, **kwargs):
        if openalex_failed:
            raise RuntimeError("OpenAlex unavailable")
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"results": []})

    monkeypatch.setattr(ArxivClient, "fetch_results", arxiv_results)
    monkeypatch.setattr("requests.get", openalex_get)
    result = asyncio.run(PaperSearchSkill().run({"keywords": ["forecasting"]}, {}))
    assert result.ok is not (arxiv_failed and openalex_failed)
    if result.ok:
        assert result.output["papers"] == []


@pytest.mark.parametrize("synthesis_fails", [False, True])
def test_survey_writes_from_saved_findings_even_when_one_step_is_empty(harness, synthesis_fails):
    client, headers, worker, sessions = harness

    class SurveyModel(ScriptedModel):
        writing_calls = 0

        def invoke(self, prompt):
            if prompt.startswith("根据用户研究目标"):
                return json.dumps({"difficulty": "standard", "reason": "主题归纳", "questions": [
                    {"title": "梳理方法", "query": "forecasting"},
                    {"title": "比较指标", "query": "metrics"},
                ]})
            if prompt.startswith("根据公开学术搜索结果"):
                return json.dumps({"findings": [
                    {"text": "论文描述预测方法。", "sources": [1]},
                    {"text": "论文采用时间窗口。", "sources": [1]},
                ], "missing_criteria": [], "reason": "已整理"})
            assert prompt.startswith("根据已有研究发现")
            self.writing_calls += 1
            payload = json.loads(prompt.split("\n数据：", 1)[1].split("\n重新生成", 1)[0])
            assert len(payload["findings"]) == 2
            assert "summary" not in payload["findings"][0]
            if synthesis_fails:
                raise ValueError("invalid synthesis")
            return json.dumps({
                "summary": {"text": "现有文献讨论基于时间窗口的预测。", "sources": [1, 2]},
                "scope": "本文讨论基于时间窗口的预测方法。",
                "sections": [{"title": "预测方法", "paragraphs": [{"text": "预测中使用了时间窗口。", "sources": [2]}]}],
                "conclusion": {"text": "本轮结论适用于所列公开文献。", "sources": [1]},
            })

    class Search:
        calls = []

        async def run(self, data, context):
            query = data["keywords"][0]
            self.calls.append(query)
            papers = [{"title": "Public paper", "doi": "https://doi.org/10.1234/synthetic", "summary": "A public abstract."}] if query == "forecasting" else []
            return SkillResult(ok=True, output={"papers": papers})

    model, search = SurveyModel(), Search()
    worker.operations.llm = model
    worker.operations.executor.registry = {"paper_search": search}
    task = client.post("/research/tasks", headers=headers(), json={
        "goal": "生成预测方法文献综述", "source": "auto",
    }).json()["data"]
    path = f"/research/tasks/{task['task_id']}"

    def read():
        return client.get(path, headers=headers()).json()["data"]

    def approve():
        assert client.post(path + "/review", headers=headers(), json={
            "revision": read()["revision"], "action": "continue",
        }).status_code == 200

    assert worker.tick()
    approve()
    assert worker.tick()
    assert [item["type"] for item in read()["artifacts"]] == ["paper_list"]
    approve()
    assert worker.tick()
    assert worker.tick()
    approve()
    assert read()["status"] == "QUEUED"
    assert [item["type"] for item in read()["artifacts"]] == ["paper_list"]
    search_calls = search.calls.copy()
    assert worker.tick()
    assert search.calls == search_calls
    assert model.writing_calls == (2 if synthesis_fails else 1)
    final = read()
    assert final["status"] == "PARTIAL"
    artifact = final["artifacts"][0]
    assert artifact["title"] == "文献综述报告"
    assert [item["type"] for item in final["artifacts"]] == ["research_report", "paper_list"]
    assert "https://doi.org/10.1234/synthetic" in artifact["data"]["markdown"]
    assert "覆盖范围与局限" in artifact["data"]["markdown"]
    assert "比较指标" in artifact["data"]["markdown"]
    if synthesis_fails:
        assert "综合撰写尚未完成" in artifact["data"]["markdown"]
    else:
        markdown = artifact["data"]["markdown"]
        assert markdown.index("## 摘要") < markdown.index("## 研究范围") < markdown.index("## 预测方法")
        assert "本文讨论基于时间窗口的预测方法。" in markdown

    with sessions() as db:
        for identifier, title, content in (
            ("older", "旧版综述报告", {"markdown": "旧版内容"}),
            ("reviewed", "答辩综述", {"origin": "reviewed_defense_version", "markdown": "复核后的正文"}),
        ):
            db.add(Artifact(task_id=task["task_id"], artifact_id=identifier, title=title,
                            type="research_report", data_json=json.dumps(content)))
        db.commit()
    updated = read()["artifacts"]
    assert [item["artifact_id"] for item in updated] == ["reviewed", final["artifacts"][1]["artifact_id"]]
    assert updated[0]["data"]["markdown"] == "复核后的正文"

    detail = read()
    assert client.post(path + "/review", headers=headers(), json={
        "revision": detail["revision"], "action": "rewind",
        "step_id": detail["steps"][1]["step_id"], "questions": [{"title": "比较指标", "query": "metrics"}],
    }).status_code == 200
    assert [item["type"] for item in read()["artifacts"]] == ["paper_list"]


def test_web_search_node_uses_public_web_and_preserves_its_citation(harness):
    client, headers, worker, _ = harness

    class WebModel(ScriptedModel):
        def invoke(self, prompt):
            if prompt.startswith("根据用户研究目标"):
                return json.dumps({"difficulty": "quick", "reason": "查官方文档", "questions": [
                    {"title": "核对 Python 官方文档", "query": "Python pathlib resolve", "search_scope": "web"},
                ]})
            payload = json.loads(prompt.split("\n数据：", 1)[1])
            assert payload["search_results"][0]["source_type"] == "网页"
            return json.dumps({"findings": [{"text": "resolve 返回绝对路径。", "sources": [1]}], "reason": "官方文档有说明"})

    class WebTool:
        async def run(self, data, context):
            assert data["query"] == "Python pathlib resolve"
            assert context["allowed_document_ids"] == []
            return SkillResult(ok=True, output={"sources": [
                {"title": "Python pathlib documentation", "url": "https://docs.python.org/3/library/pathlib.html",
                 "source_type": "web", "summary": "Make the path absolute and resolve symlinks."},
            ]})

    worker.operations.llm = WebModel()
    worker.operations.executor.registry = {"web_search": WebTool()}
    task = client.post("/research/tasks", headers=headers(), json={
        "goal": "查官方文档说明 Path.resolve", "source": "auto",
    }).json()["data"]
    path = f"/research/tasks/{task['task_id']}"

    def read():
        return client.get(path, headers=headers()).json()["data"]

    def approve():
        assert client.post(path + "/review", headers=headers(), json={
            "revision": read()["revision"], "action": "continue",
        }).status_code == 200

    assert worker.tick()
    assert read()["plan"]["steps"][0]["search_scope"] == "web"
    approve()
    assert worker.tick()
    approve()
    result = read()
    assert result["status"] == "SUCCESS"
    assert "https://docs.python.org/3/library/pathlib.html" in result["artifacts"][0]["data"]["markdown"]
    assert result["artifacts"][1]["type"] == "source_list"


@pytest.mark.parametrize("web_available", [True, False])
def test_public_search_combines_channels_and_keeps_papers_when_web_is_unavailable(harness, web_available):
    _, _, worker, _ = harness

    class Tool:
        def __init__(self, result):
            self.result = result

        async def run(self, data, context):
            return self.result

    worker.operations.executor.registry = {
        "paper_search": Tool(SkillResult(ok=True, output={"papers": [{"title": "Paper A"}, {"title": "Paper B"}]})),
        "web_search": Tool(SkillResult(ok=web_available, output={"sources": [{"title": "Official docs"}]},
                                      error_code=None if web_available else "WEB_SEARCH_UNCONFIGURED")),
    }
    sources, warning, available = asyncio.run(worker.operations.search_public(
        "公开综述", {"goal": "公开综述"}, {"title": "检索", "query": "test", "search_scope": "both"}, {}, 8,
    ))
    assert available
    assert [item["title"] for item in sources] == (["Paper A", "Official docs", "Paper B"] if web_available else ["Paper A", "Paper B"])
    assert warning == ("" if web_available else "网页搜索尚未配置")


def test_web_search_reports_missing_configuration_and_normalizes_searx_results(monkeypatch):
    import httpx

    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    skill = WebSearchSkill()
    assert asyncio.run(skill.run({"query": "official documentation"})).error_code == "WEB_SEARCH_UNCONFIGURED"
    monkeypatch.setenv("SEARXNG_URL", "https://search.example")

    def search(request):
        assert request.url.path == "/search"
        assert request.url.params["format"] == "json"
        assert request.url.params["q"] == "official documentation"
        return httpx.Response(200, json={"results": [
            {"title": "Documentation", "url": "https://docs.example/guide", "content": "<b>Official</b> &amp; current"},
            {"title": "Unsafe URL", "url": "javascript:alert(1)"},
        ]})

    client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client(transport=httpx.MockTransport(search), **kwargs))
    output = asyncio.run(skill.run({"query": "official documentation"})).output
    assert len(output["sources"]) == 1
    assert output["sources"][0]["summary"] == "Official & current"
    assert output["sources"][0]["venue"] == "docs.example"


def test_empty_survey_offers_outline_after_searching():
    state = {"goal": "生成综述", "source": "discovery", "steps": [
        {"title": "梳理方法", "findings": [], "attempts": [{}], "status": "SUCCESS"},
    ]}
    artifact = report(state)
    assert artifact["title"] == "文献综述提纲"
    assert "暂无可归纳的文献内容" in artifact["markdown"]
    assert "梳理方法" in artifact["markdown"]


@pytest.mark.parametrize("interruption", [TimeoutError, ResearchStreamInterrupted])
def test_stalled_model_can_resume_the_same_node_without_a_failed_attempt(harness, monkeypatch, interruption):
    client, headers, worker, _ = harness
    task = client.post("/research/tasks", headers=headers(), json={
        "goal": "测试集 F1 是多少", "source": "library",
    }).json()["data"]
    path = f"/research/tasks/{task['task_id']}"

    def read():
        return client.get(path, headers=headers()).json()["data"]

    def review(action):
        response = client.post(path + "/review", headers=headers(), json={
            "revision": read()["revision"], "action": action,
        })
        assert response.status_code == 200

    assert worker.tick()
    review("continue")

    def stall(*args):
        raise interruption("output interrupted")

    with monkeypatch.context() as patch:
        patch.setattr(worker.operations, "run_step", stall)
        assert worker.tick()
    paused = read()
    assert paused["status"] == "WAITING_RETRY"
    assert paused["steps"][0]["attempts"] == []
    assert not worker.tick()

    review("resume")
    assert worker.tick()
    checked = read()
    assert checked["status"] == "AWAITING_INPUT"
    assert checked["plan_version"] == paused["plan_version"]
    assert checked["steps"][0]["step_id"] == paused["steps"][0]["step_id"]
    assert checked["steps"][0]["findings"]


def test_verifier_deduplicates_excerpts_without_losing_reference_bindings():
    reference = {"document_id": "p", "page": 3, "chunk_id": "c", "text": "First fact. Second fact.",
                 "title": "Paper", "quote": "First fact."}
    findings = [{"text": "First", "references": [reference]},
                {"text": "Second", "references": [reference | {"quote": "Second fact."}]}]
    entries, evidence = verification_evidence(findings)
    assert len(evidence) == 1
    assert [entry["references"][0] for entry in entries] == [
        {"evidence_id": "E1", "quote": "First fact."},
        {"evidence_id": "E1", "quote": "Second fact."},
    ]


def test_model_output_renews_wait_window_without_adding_reasoning_to_answer():
    async def replay():
        for content, reasoning, finish in [("", "thinking", None), ('{"found":', "", None),
                                           ("true}", "", "stop")]:
            await asyncio.sleep(0.08)
            yield SimpleNamespace(choices=[SimpleNamespace(
                delta=SimpleNamespace(content=content, reasoning_content=reasoning), finish_reason=finish,
            )])

    async def run():
        async with asyncio.timeout(0.18) as deadline:
            return await collect_json_stream(replay(), deadline, 0.20, None)

    assert asyncio.run(run()) == '{"found":true}'


def test_empty_stream_events_do_not_renew_wait_window():
    async def replay():
        while True:
            await asyncio.sleep(0.02)
            yield SimpleNamespace(choices=[SimpleNamespace(
                delta=SimpleNamespace(content=" ", reasoning_content=None), finish_reason=None,
            )])

    async def run():
        async with asyncio.timeout(0.15) as deadline:
            await collect_json_stream(replay(), deadline, 0.20, None)

    with pytest.raises(TimeoutError):
        asyncio.run(run())


def test_many_paper_research_does_not_fill_context_with_one_paper():
    hits = [{"document_id": paper, "page_number": i} for i, paper in enumerate(["a", "a", "a", "b", "c"])]
    assert [item["document_id"] for item in diversify_evidence(hits, 4)] == ["a", "b", "c", "a"]


def test_expired_worker_lease_resumes_planning(harness):
    client, headers, worker, sessions = harness
    response = client.post("/research/tasks", headers=headers(), json={"goal": "复核实验", "source": "library"})
    task_id = response.json()["data"]["task_id"]
    with sessions() as db:
        db.query(ResearchTask).filter_by(task_id=task_id).one().status = "RUNNING"
        db.get(GuidedResearch, task_id).lease_until = utcnow() - timedelta(seconds=1)
        db.commit()
    assert worker.tick()
    detail = client.get(f"/research/tasks/{task_id}", headers=headers()).json()["data"]
    assert detail["status"] == "AWAITING_APPROVAL"
    assert any(item["title"] == "从检查点恢复" for item in detail["events"])


def test_verifier_requires_plan_coverage_and_expected_artifact():
    plan = TaskPlan(task_id="task", goal="verify", steps=[
        PlanStep(step_id="a", title="a", skill="skill"),
        PlanStep(step_id="b", title="b", skill="skill"),
    ], expected_artifacts=["research_report"])
    first, second = [StepResult(step_id=key, status="SUCCESS") for key in ["a", "b"]]
    verifier = Verifier()
    artifact = {"type": "research_report"}
    assert not verifier.verify(plan, [first], [artifact])[0]
    assert not verifier.verify(plan, [first, first], [artifact])[0]
    assert not verifier.verify(plan, [first, second], [])[0]
    assert verifier.verify(plan, [first, second], [artifact])[0]
