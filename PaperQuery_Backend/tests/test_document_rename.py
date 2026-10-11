import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.backend.db.models import Document
from core.backend.router import router_document as module


class DocumentRenameTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Document.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        with self.Session() as db:
            db.add_all([
                Document(uid='same-pdf', knowledgeID='own', lid='mine', documentName='old.pdf', documentPath='/original.pdf', documentStatus=2, documentVector=28),
                Document(uid='same-pdf', knowledgeID='other-library', lid='mine', documentName='other.pdf', documentPath='/original.pdf', documentStatus=2),
                Document(uid='foreign', knowledgeID='foreign-library', lid='theirs', documentName='private.pdf', documentPath='/private.pdf'),
            ])
            db.commit()

        def test_db():
            with self.Session() as db:
                yield db

        app = FastAPI()
        app.include_router(module.router)
        app.dependency_overrides[module.get_db] = test_db
        self.auth = patch.object(module, 'get_current_user', AsyncMock(return_value=SimpleNamespace(workspace_lid='mine')))
        self.auth.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.auth.stop()
        self.engine.dispose()

    def rename(self, name, document='same-pdf', knowledge='own', headers=None):
        return self.client.post('/document/rename', json={'documentID': document, 'knowledgeID': knowledge, 'documentName': name}, headers=headers if headers is not None else {'Authorization': 'Bearer test'})

    def test_persistent_name_and_unchanged_file_index_and_other_library(self):
        response = self.rename('  时间序列预测 · 多变量建模  ')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['documentName'], '时间序列预测 · 多变量建模')
        with self.Session() as db:
            own = db.query(Document).filter_by(knowledgeID='own').one()
            self.assertEqual((own.documentName, own.documentPath, own.documentStatus, own.documentVector), ('时间序列预测 · 多变量建模', '/original.pdf', 2, 28))
            self.assertEqual(db.query(Document).filter_by(knowledgeID='other-library').one().documentName, 'other.pdf')

    def test_auth_scope_missing_and_invalid_names(self):
        self.assertEqual(self.rename('name', headers={}).status_code, 401)
        self.assertEqual(self.rename('name', 'foreign', 'foreign-library').status_code, 404)
        self.assertEqual(self.rename('name', knowledge='wrong').status_code, 404)
        for name in [' ', 'x' * 256, 'hello\nworld']:
            self.assertEqual(self.rename(name).status_code, 422)
        with self.Session() as db:
            self.assertEqual(db.query(Document).filter_by(knowledgeID='own').one().documentName, 'old.pdf')


if __name__ == '__main__':
    unittest.main()
