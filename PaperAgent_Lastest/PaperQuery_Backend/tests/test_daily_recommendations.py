import tempfile
import unittest
from datetime import date, datetime
from unittest.mock import patch, Mock
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from core.backend.db.models import Document, Knowledge, ResearchTask
from core.backend.router import router_dashboard

from core.backend.services import daily_recommendations as service
from core.backend.services.research_interests import local_interests


class DailyRecommendationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict('os.environ', {'DAILY_RECOMMENDATION_CACHE_DIR': self.tmp.name})
        self.env.start()
        self.stamp = datetime(2026, 10, 9, 10, tzinfo=service.SHANGHAI)
        self.clock = patch.object(service, 'local_now', return_value=self.stamp)
        self.clock.start()
        self.feed = patch.object(service, 'search_arxiv_feed', return_value=[])
        self.feed.start()
        self.evidence = {'papers': [{'name': 'private.pdf', 'tags': '时间序列预测', 'abstract': 'confidential-sentinel'}],
                         'research_goals': ['多变量时间序列预测'], 'libraries': [], 'recent_questions': []}
        self.paper = {'id': 'new', 'title': 'Time series forecasting with adaptive models', 'summary': 'time series forecasting',
                      'authors': ['Example'], 'published': '2026-10-09', 'url': 'https://arxiv.org/abs/new',
                      'pdf_url': 'https://arxiv.org/pdf/new', 'provider': 'arXiv', 'venue': 'arXiv 预印本', 'importable': True}

    def tearDown(self):
        self.clock.stop()
        self.feed.stop()
        self.env.stop()
        self.tmp.cleanup()

    def test_local_profile_and_outbound_keywords_only(self):
        profile = local_interests(self.evidence)
        self.assertEqual(profile['topics'][0]['query'], 'time series forecasting')
        response = Mock(content=b'<feed xmlns="http://www.w3.org/2005/Atom"/>')
        with patch.object(service.requests, 'get', return_value=response) as request:
            service.search_arxiv(profile['topics'], self.stamp.date())
        args = str(request.call_args)
        self.assertNotIn('private.pdf', args)
        self.assertNotIn('confidential-sentinel', args)
        self.assertNotIn('多变量时间序列预测', args)
        self.assertIn('submittedDate', args)

    def test_cache_date_account_isolation_and_old_future_duplicates(self):
        old = {**self.paper, 'id': 'old', 'title': 'Old time series forecasting', 'published': '2025-10-01'}
        future = {**self.paper, 'id': 'future', 'title': 'Future time series forecasting', 'published': '2026-10-10'}
        with patch.object(service, 'search_arxiv', return_value=[self.paper, self.paper, old, future]) as search:
            first = service.build_daily_recommendations('alice', self.evidence)
            self.assertEqual(len(first['items']), 1)
            self.assertTrue(first['items'][0]['is_today'])
            self.assertTrue(service.build_daily_recommendations('alice', self.evidence)['cached'])
            self.assertEqual(search.call_count, 1)
            service.build_daily_recommendations('bob', self.evidence)
            self.assertEqual(search.call_count, 2)
            with patch.object(service, 'local_now', return_value=datetime(2026, 10, 10, tzinfo=service.SHANGHAI)):
                service.build_daily_recommendations('alice', self.evidence)
            self.assertEqual(search.call_count, 3)

    def test_empty_history_and_sources_unavailable_not_fabricated(self):
        with patch.object(service, 'search_arxiv') as search:
            empty = service.build_daily_recommendations('empty', {})
            self.assertEqual(empty['status'], 'no_interests')
            search.assert_not_called()
        with patch.object(service, 'search_arxiv', side_effect=RuntimeError('offline')), patch.object(service, 'search_openalex', side_effect=RuntimeError('offline')):
            result = service.build_daily_recommendations('offline', self.evidence)
            self.assertEqual(result['items'], [])
            self.assertEqual(result['status'], 'unavailable')

    def test_fallback_known_titles_and_stale_label(self):
        with patch.object(service, 'search_arxiv', return_value=[]), patch.object(service, 'search_openalex', return_value=[self.paper]):
            result = service.build_daily_recommendations('alice', self.evidence)
            self.assertEqual(len(result['items']), 1)
            self.assertIn('OpenAlex', result['warning'])
        with patch.object(service, 'local_now', return_value=datetime(2026, 10, 10, tzinfo=service.SHANGHAI)), patch.object(service, 'search_arxiv', side_effect=RuntimeError('offline')), patch.object(service, 'search_openalex', side_effect=RuntimeError('offline')):
            stale = service.build_daily_recommendations('alice', self.evidence)
            self.assertEqual(stale['status'], 'stale')
            self.assertEqual(stale['date'], '2026-10-09')
        self.assertEqual(service.select_papers([self.paper], local_interests(self.evidence)['topics'], date(2026, 10, 9), [self.paper['title'] + '.pdf']), [])


class RecommendationScopeTests(unittest.TestCase):
    def test_route_uses_only_authenticated_workspace_and_bounds_questions(self):
        engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        for model in (Document, Knowledge, ResearchTask):
            model.__table__.create(engine)
        sessions = sessionmaker(bind=engine)
        with sessions() as db:
            for lid in ['mine', 'other']:
                db.add(Document(uid=lid, knowledgeID=lid, lid=lid, documentName=lid + '.pdf', documentPath=lid, tags='时间序列预测'))
                db.add(Knowledge(knowledgeID=lid, lid=lid, knowledgeName=lid))
                db.add(ResearchTask(task_id=lid, lid=lid, goal=lid, status='SUCCESS'))
            db.commit()
        def test_db():
            with sessions() as db:
                yield db
        app = FastAPI()
        app.include_router(router_dashboard.router)
        app.dependency_overrides[router_dashboard.get_db] = test_db
        app.dependency_overrides[router_dashboard.get_current_user] = lambda: SimpleNamespace(workspace_lid='mine', username='alice')
        try:
            with TestClient(app) as client, patch.object(service, 'build_daily_recommendations', return_value={'fingerprint': 'internal', 'status': 'no_interests'}) as build:
                response = client.post('/dashboard/recommendations', json={'chat_queries': ['  own question  ']})
                self.assertEqual(response.status_code, 200)
                self.assertNotIn('fingerprint', response.json()['data'])
                account, evidence, _ = build.call_args.args
                self.assertEqual(account, 'mine:alice')
                self.assertEqual(evidence['research_goals'], ['mine'])
                self.assertEqual([p['name'] for p in evidence['papers']], ['mine.pdf'])
                self.assertEqual(evidence['recent_questions'], ['own question'])
                self.assertEqual(client.post('/dashboard/recommendations', json={'chat_queries': ['x'] * 31}).status_code, 422)
        finally:
            engine.dispose()


class FeedTests(unittest.TestCase):
    def test_feed_ignores_replacement_and_marks_first_announcement_date(self):
        xml = b'''<rss xmlns:arxiv="http://arxiv.org/schemas/atom" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>
        <item><title>Time series forecasting</title><link>https://arxiv.org/abs/2610.10001</link><description>Abstract: time series forecasting</description><pubDate>Fri, 09 Oct 2026 00:00:00 -0400</pubDate><arxiv:announce_type>new</arxiv:announce_type><dc:creator>Test Author</dc:creator></item>
        <item><title>Updated time series forecasting</title><link>https://arxiv.org/abs/2501.10001</link><pubDate>Fri, 09 Oct 2026 00:00:00 -0400</pubDate><arxiv:announce_type>replace</arxiv:announce_type></item>
        </channel></rss>'''
        with patch.dict(service._feed_cache, {}, clear=True), patch.object(service.requests, 'get', return_value=Mock(content=xml)):
            items = service.search_arxiv_feed([{'query': 'time series forecasting'}], date(2026, 10, 9))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['published'], '2026-10-09')
        self.assertEqual(items[0]['provider'], 'arXiv RSS')


if __name__ == '__main__':
    unittest.main()
