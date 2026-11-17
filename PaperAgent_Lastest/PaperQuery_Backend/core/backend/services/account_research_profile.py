"""Account-scoped interests derived locally without model calls."""
import hashlib
import json
import os
import threading
from pathlib import Path
from core.backend.db.models import Document, Knowledge, ResearchTask
from .research_interests import local_interests

_lock = threading.Lock()

def account_evidence(db, user, questions=(), remember=None):
    key = hashlib.sha256(f'{user.workspace_lid}:{user.username}'.encode()).hexdigest()
    directory = Path(os.getenv('RESEARCH_PROFILE_DIR', './res/research_profiles'))
    with _lock:
        path = directory / f'{key}.json'
        try:
            recent = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(recent, list):
                recent = []
        except (OSError, ValueError):
            recent = []
        recent = [str(q).strip()[:500] for q in recent + list(questions) if str(q).strip()]
        if remember:
            recent.append(remember.strip()[:500])
        recent = list(dict.fromkeys(reversed(recent)))[:30][::-1]
        if questions or remember:
            directory.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(recent, ensure_ascii=False), encoding='utf-8')
            temporary.replace(path)
    documents = db.query(Document).filter(Document.lid == user.workspace_lid).order_by(Document.createTime.desc()).limit(60).all()
    tasks = db.query(ResearchTask).filter(ResearchTask.lid == user.workspace_lid).order_by(ResearchTask.created_at.desc()).limit(20).all()
    libraries = db.query(Knowledge).filter(Knowledge.lid == user.workspace_lid).limit(12).all()
    return {
        'papers': [{'name': d.documentName, 'tags': d.tags or '', 'abstract': (d.documentDescription or '')[:1000]} for d in documents],
        'research_goals': [t.goal[:500] for t in tasks],
        'libraries': [{'name': k.knowledgeName, 'description': (k.knowledgeDescription or '')[:250]} for k in libraries],
        'recent_questions': recent,
    }

def computer_research_profile(evidence):
    profile = local_interests(evidence)
    profile['topics'] = [t for t in profile['topics'] if t['query'] != 'biomedical research']
    profile['domain'] = 'computer science'
    profile['summary'] = '计算机领域；' + ('近期关注：' + '、'.join(t['label'] for t in profile['topics']) if profile['topics'] else '暂未归纳出细分兴趣')
    return profile
