import os
import unittest
import tempfile
from unittest.mock import patch
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.backend.db.database import Base
from core.backend.db.models import Document, TMPDocument, User
from core.backend.router.dependencies import get_db
from main import app
from core.skills.base import SkillResult
from core.common.types import EvidenceChunk
from core.decision.schemas import GroundingDecision


class AskAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.profile_directory = tempfile.TemporaryDirectory()
        self.profile_environment = patch.dict(os.environ, {'RESEARCH_PROFILE_DIR': self.profile_directory.name})
        self.profile_environment.start()
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        with self.Session() as db:
            db.add_all([
                User(username="alice", password="unused", lid="alice-lid"),
                User(username="bob", password="unused", lid="bob-lid"),
                Document(uid="alice-paper", knowledgeID="a", lid="alice-lid", documentName="a.pdf", documentPath="a.pdf"),
                Document(uid="bob-paper", knowledgeID="b", lid="bob-lid", documentName="b.pdf", documentPath="b.pdf"),
                TMPDocument(uid="alice-temp", knowledgeID="tmp", lid="alice-lid", documentName="tmp.pdf", documentPath="tmp.pdf"),
            ])
            db.commit()

        def test_db():
            with self.Session() as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        self.client = TestClient(app)

    def tearDown(self):
        self.profile_environment.stop()
        self.profile_directory.cleanup()
        app.dependency_overrides.clear()
        self.client.close()
        self.engine.dispose()

    def token(self, username, expired=False):
        when = datetime.now(timezone.utc) + timedelta(minutes=-1 if expired else 10)
        return jwt.encode(
            {"username": username, "exp": when},
            os.environ["SECRET_KEY"], algorithm=os.environ["ALGORITHM"],
        )

    def ask(self, token=None, documents=None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.client.post(
            "/qa/stream", headers=headers,
            json={"question": "Summarize the selected paper", "document_ids": documents or []},
        )

    def test_missing_invalid_and_expired_jwt_are_rejected(self):
        self.assertEqual(self.ask().status_code, 401)
        self.assertEqual(self.ask("invalid.jwt.token").status_code, 401)
        self.assertEqual(self.ask(self.token("alice", expired=True)).status_code, 401)

    def test_other_accounts_document_is_rejected(self):
        response = self.ask(self.token("alice"), ["bob-paper"])
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("bob.pdf", response.text)

    def test_mixed_ownership_is_rejected(self):
        self.assertEqual(self.ask(self.token("alice"), ["alice-paper", "bob-paper"]).status_code, 403)

    def test_owned_library_and_temporary_documents_are_allowed(self):
        self.assertEqual(self.ask(self.token("alice"), ["alice-paper"]).status_code, 200)
        self.assertEqual(self.ask(self.token("alice"), ["alice-temp"]).status_code, 200)

    def test_broad_recent_paper_request_has_useful_fallback_when_sources_fail(self):
        class UnavailableSearch:
            async def run(self, _args):
                return SkillResult(ok=False, error_code="SEARCH_ERROR", error_message="source unavailable")

        with patch.object(app, "chat_agents", {}, create=True), \
             patch.object(app, "decision_engine", None, create=True), \
             patch("core.backend.router.router_qa.PaperSearchSkill", UnavailableSearch):
            response = self.client.post(
                "/qa/stream",
                headers={"Authorization": f"Bearer {self.token('alice')}"},
                json={"question": "最近最新的论文有没有推荐的", "document_ids": []},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("machine learning", response.text)
        self.assertIn("你想关注哪个方向", response.text)
        self.assertNotIn("请调整研究领域或关键词后重试", response.text)

    def test_generic_recommendation_uses_account_profile_and_excludes_irrelevant_papers(self):
        import tempfile
        captured = []
        class Search:
            async def run(self, args):
                captured.append(args)
                return SkillResult(ok=True, output={'provider': 'openalex', 'papers': [
                    {'title': '试论小学语文作文教学中学生想象能力的培养'},
                    {'title': '日本网络文学的概念辨析及创作特征'},
                    {'title': 'Machine learning for time series forecasting', 'summary': 'Neural time series forecasting models'},
                ]})
        with self.Session() as db:
            db.query(Document).filter(Document.uid == 'alice-paper').first().tags = '时间序列预测'
            db.commit()
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(os.environ, {'RESEARCH_PROFILE_DIR': directory}), \
             patch.object(app, 'chat_agents', {}, create=True), \
             patch.object(app, 'decision_engine', None, create=True), \
             patch('core.backend.router.router_qa.PaperSearchSkill', Search):
            response = self.client.post('/qa/stream', headers={'Authorization': f'Bearer {self.token("alice")}'},
                                        json={'question': '今日没有推荐论文码', 'document_ids': []})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured[0]['keywords'], ['time series forecasting'])
        self.assertTrue(captured[0]['computer_science'])
        self.assertTrue(captured[0]['recent'])
        self.assertIn('Machine learning for time series forecasting', response.text)
        self.assertNotIn('日本网络文学', response.text)
        self.assertNotIn('小学语文', response.text)

    def test_bound_paper_does_not_hijack_general_tasks(self):
        captured = []
        class Agent:
            def get_llm(self):
                return object()
            def chat_simple(self, prompt):
                captured.append(prompt)
                yield SimpleNamespace(content='直接完成用户的任务。')
        class Chroma:
            def search_evidence(self, *args, **kwargs):
                raise AssertionError('通用问题不应调用论文检索')
        with patch.object(app, 'chat_agents', {'deepseek': Agent()}, create=True), \
             patch.object(app, 'chroma_db', Chroma(), create=True):
            for question in ['帮我写一个 Python 排序函数', '什么是 RAG', '帮我写封邮件', 'Explain gradient descent']:
                response = self.client.post('/qa/stream', headers={'Authorization': f'Bearer {self.token("alice")}'},
                                            json={'question': question, 'document_ids': ['alice-paper']})
                self.assertIn('"route": "GENERAL_CHAT"', response.text)
                self.assertIn('直接完成用户的任务', response.text)
        self.assertTrue(all('不能强行转向计算机论文' in prompt for prompt in captured))

    def test_general_question_without_papers_gets_normal_answer(self):
        class FakeAgent:
            def get_llm(self):
                return object()

            def chat_simple(self, _prompt):
                yield SimpleNamespace(content="RAG 把检索到的资料用于生成回答。")

        with patch.object(app, "chat_agents", {"deepseek": FakeAgent()}, create=True):
            response = self.client.post(
                "/qa/stream",
                headers={"Authorization": f"Bearer {self.token('alice')}"},
                json={"question": "什么是 RAG？", "document_ids": []},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn('"route": "GENERAL_CHAT"', response.text)
        self.assertIn("RAG 把检索到的资料用于生成回答", response.text)

    def test_bound_paper_overview_uses_pdf_evidence_even_if_intent_would_be_general(self):
        prompts = []

        class FakeAgent:
            def get_llm(self):
                return object()

            def chat_simple(self, prompt):
                prompts.append(prompt)
                yield SimpleNamespace(content="这篇论文讨论联邦学习。[C1]")

        class FakeDecisionEngine:
            def __init__(self, _llm):
                pass

            def decide_intent(self, *_args):
                raise AssertionError("明确指向已选论文时不应进入普通聊天分类")

            def decide_evidence(self, *_args):
                raise AssertionError("概述应直接使用论文开头的证据")

            def verify_grounding(self, *_args):
                return GroundingDecision(passed=True, confidence=1.0)

        class FakeChroma:
            def get_opening_evidence(self, document_ids):
                self.document_ids = document_ids
                return [EvidenceChunk(
                    chunk_id="alice-paper:p1", document_id="alice-paper", knowledge_id="THIS_IS_A_TMP_KID",
                    source="a.pdf", page_number=1,
                    text="This paper proposes a federated learning method.",
                )]

            def search_evidence(self, *_args, **_kwargs):
                return []

        chroma = FakeChroma()
        with patch.object(app, "chat_agents", {"deepseek": FakeAgent()}, create=True), \
             patch.object(app, "chroma_db", chroma, create=True), \
             patch("core.backend.router.router_qa.DecisionEngine", FakeDecisionEngine):
            response = self.client.post(
                "/qa/stream",
                headers={"Authorization": f"Bearer {self.token('alice')}"},
                json={"question": "讲一下这篇论文", "document_ids": ["alice-paper"]},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(chroma.document_ids, ["alice-paper"])
        self.assertIn('"route": "LOCAL_RAG"', response.text)
        self.assertIn("这篇论文讨论联邦学习", response.text)
        self.assertIn('"id": "C1"', response.text)
        self.assertIn('"knowledgeID": "a"', response.text)
        self.assertNotIn("THIS_IS_A_TMP_KID", response.text)
        self.assertIn("a.pdf", prompts[0])
        self.assertIn("This paper proposes a federated learning method.", prompts[0])

    def test_multi_paper_overview_preserves_evidence_for_all_thirteen_papers(self):
        ids = [f"overview-{i}" for i in range(13)]
        with self.Session() as db:
            db.add_all([Document(uid=uid, knowledgeID="a", lid="alice-lid",
                documentName=f"P{i + 1:02}.pdf", documentPath=f"{uid}.pdf")
                for i, uid in enumerate(ids)])
            db.commit()
        prompts = []

        class FakeAgent:
            def get_llm(self):
                return object()

            def chat_simple(self, prompt):
                prompts.append(prompt)
                yield SimpleNamespace(content="论文概述。[C1]")

        class FakeDecisionEngine:
            def __init__(self, _llm):
                pass

            def decide_intent(self, *_args):
                raise AssertionError("已选论文介绍必须读取正文")

            def verify_grounding(self, *_args):
                return GroundingDecision(passed=True, confidence=1.0)

        class FakeChroma:
            def get_opening_evidence(self, document_ids):
                return [EvidenceChunk(chunk_id=f"{uid}:{i}", document_id=uid,
                    source=f"{uid}.pdf", page_number=1,
                    text=f"Unique abstract for {uid}, section {i}.")
                    for uid in document_ids for i in range(2)]

            def search_evidence(self, *_args, **_kwargs):
                return []

        with patch.object(app, "chat_agents", {"deepseek": FakeAgent()}, create=True), \
             patch.object(app, "chroma_db", FakeChroma(), create=True), \
             patch("core.backend.router.router_qa.DecisionEngine", FakeDecisionEngine):
            response = self.client.post("/qa/stream",
                headers={"Authorization": f"Bearer {self.token('alice')}"},
                json={"question": "分别介绍这些论文", "document_ids": ids})
        self.assertEqual(response.status_code, 200)
        for i, uid in enumerate(ids):
            self.assertIn(f"Unique abstract for {uid}, section 1.", prompts[0])
            self.assertIn(f"论文库文件名=P{i + 1:02}.pdf", prompts[0])
        self.assertIn('"id": "C26"', response.text)

    def test_pdf_old_citation_scope_resolves_only_owned_document(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            Path(directory, "a.pdf").write_bytes(b"%PDF-1.4\nfixture")
            with patch.dict(os.environ, {"AcadeAgent_DIR": directory + "/"}):
                headers = {"Authorization": f"Bearer {self.token('alice')}"}
                response = self.client.get("/document/getFile",
                    params={"documentID": "alice-paper", "knowledgeID": "THIS_IS_A_TMP_KID"}, headers=headers)
                self.assertEqual(response.status_code, 200)
                self.assertIn("application/pdf", response.headers["content-type"])
                denied = self.client.get("/document/getFile",
                    params={"documentID": "bob-paper", "knowledgeID": "THIS_IS_A_TMP_KID"}, headers=headers)
                self.assertEqual(denied.status_code, 404)

    def test_bound_paper_without_index_reports_processing_instead_of_losing_binding(self):
        class FakeChroma:
            def get_opening_evidence(self, _document_ids):
                return []

            def search_evidence(self, *_args, **_kwargs):
                return []

        with patch.object(app, "chat_agents", {}, create=True), \
             patch.object(app, "decision_engine", None, create=True), \
             patch.object(app, "chroma_db", FakeChroma(), create=True):
            response = self.client.post(
                "/qa/stream",
                headers={"Authorization": f"Bearer {self.token('alice')}"},
                json={"question": "讲一下这篇论文", "document_ids": ["alice-paper"]},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("已选定 a.pdf", response.text)
        self.assertIn("选中相关段落继续提问", response.text)
        self.assertIn('PARTIAL_GUIDANCE', response.text)
        self.assertNotIn('无法回答', response.text)


if __name__ == "__main__":
    unittest.main()
