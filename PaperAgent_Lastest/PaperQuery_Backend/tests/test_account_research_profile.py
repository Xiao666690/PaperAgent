import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from core.backend.db.database import Base
from core.backend.db.models import Document
from core.backend.services.account_research_profile import account_evidence, computer_research_profile
from core.decision.external_search import is_broad_paper_recommendation, make_search_keywords, filter_computer_papers, wants_recent_papers
from core.skills.paper_search import PaperSearchSkill

class ResearchProfileTests(unittest.TestCase):
    def test_generic_question_uses_history_instead_of_literal_sentence(self):
        profile = computer_research_profile({'papers': [{'name': 'P09.pdf', 'tags': '时间序列预测', 'abstract': 'time series forecasting'}], 'research_goals': [], 'libraries': [], 'recent_questions': []})
        for question in ['今日没有推荐论文码', '今天没有推荐论文吗', '现在有推荐的论文吗']:
            self.assertTrue(is_broad_paper_recommendation(question))
            self.assertEqual(make_search_keywords(None, question, '', profile=profile), ['time series forecasting'])
        self.assertTrue(wants_recent_papers('今日没有推荐论文码'))
        self.assertEqual(make_search_keywords(None, '推荐联邦学习论文', '', profile=profile), ['federated learning'])

    def test_wrong_field_and_wrong_topic_are_removed(self):
        papers = [{'title': '试论小学语文作文教学中学生想象能力的培养'},
                  {'title': '日本网络文学的概念辨析及创作特征'},
                  {'title': '论东汉宦官在教育科学文化领域的贡献'},
                  {'title': 'Machine learning for time series forecasting'},
                  {'title': 'Computer vision image classification with neural networks'}]
        self.assertEqual(filter_computer_papers(papers, ['time series forecasting']), [papers[3]])
        self.assertEqual(filter_computer_papers(papers[:3], ['machine learning']), [])

    def test_account_history_isolation_and_restart_persistence(self):
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'RESEARCH_PROFILE_DIR': folder}), Session(engine) as db:
            db.add_all([Document(uid='a', lid='alice', knowledgeID='a', documentName='P09.pdf', documentPath='a', tags='时间序列预测'),
                        Document(uid='b', lid='bob', knowledgeID='b', documentName='private.pdf', documentPath='b', tags='计算机视觉')])
            db.commit()
            alice = SimpleNamespace(workspace_lid='alice', username='alice')
            bob = SimpleNamespace(workspace_lid='bob', username='bob')
            account_evidence(db, alice, remember='图神经网络')
            later = account_evidence(db, alice)
            other = account_evidence(db, bob)
            self.assertEqual(later['recent_questions'], ['图神经网络'])
            self.assertEqual(other['recent_questions'], [])
            self.assertEqual([p['name'] for p in later['papers']], ['P09.pdf'])
            self.assertEqual([p['name'] for p in other['papers']], ['private.pdf'])
        engine.dispose()

    def test_openalex_field_filter_survives_recent_filter(self):
        response = Mock()
        response.json.return_value = {'results': [{'display_name': 'Time series forecasting with neural networks', 'topics': [{'field': {'id': 'https://openalex.org/fields/17'}}]}]}
        with patch('requests.get', return_value=response) as get:
            result = PaperSearchSkill._search_openalex(['time series forecasting'], 8, recent=True, computer_science=True)
        params = get.call_args.kwargs['params']
        self.assertIn('topics.field.id:17', params['filter'])
        self.assertIn('from_publication_date:', params['filter'])
        self.assertEqual(result[0]['fields'], ['https://openalex.org/fields/17'])

if __name__ == '__main__':
    unittest.main()
