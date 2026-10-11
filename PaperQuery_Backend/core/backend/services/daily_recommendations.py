"""Daily metadata discovery: only locally extracted keywords leave the server."""
import hashlib
import json
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from email.utils import parsedate_to_datetime
from html import unescape

import requests
from .research_interests import local_interests
from .account_research_profile import computer_research_profile

SHANGHAI = timezone(timedelta(hours=8))
ATOM = {'a': 'http://www.w3.org/2005/Atom'}
_locks = {}
_guard = threading.Lock()
_feed_cache = {}
_feed_guard = threading.Lock()


def local_now():
    return datetime.now(SHANGHAI)


def search_arxiv_feed(topics, today):
    categories = set()
    for topic in topics:
        query = topic['query']
        if 'vision' in query or 'diffusion' in query or 'multimodal' in query:
            categories.update(['cs.CV', 'cs.LG'])
        elif 'language' in query or 'retrieval' in query:
            categories.update(['cs.CL', 'cs.AI'])
        else:
            categories.update(['cs.LG', 'cs.AI', 'stat.ML'])
    category = '+'.join(sorted(categories))
    with _feed_guard:
        cached = _feed_cache.get(category)
        if cached and (local_now() - cached[0]).total_seconds() < 3600:
            return cached[1]
        response = requests.get('https://rss.arxiv.org/rss/' + category,
                                headers={'User-Agent': 'PaperAgent/2.0 daily-discovery'}, timeout=(4, 12))
        response.raise_for_status()
        root = ET.fromstring(response.content)
        papers = []
        for item in root.findall('./channel/item'):
            # A replacement or cross-listing is not a newly published paper.
            if item.findtext('{http://arxiv.org/schemas/atom}announce_type') != 'new':
                continue
            link = item.findtext('link', '')
            match = re.fullmatch(r'https://arxiv\.org/abs/([\w.\-/]+)', link)
            if not match:
                continue
            try:
                announced = parsedate_to_datetime(item.findtext('pubDate', '')).astimezone(SHANGHAI).date().isoformat()
            except (ValueError, TypeError):
                continue
            description = item.findtext('description', '')
            abstract = description.split('Abstract:', 1)[-1]
            abstract = unescape(re.sub(r'<[^>]+>', '', abstract)).strip()
            papers.append({'id': match.group(1), 'title': item.findtext('title', ''), 'summary': abstract[:1800],
                           'authors': [item.findtext('{http://purl.org/dc/elements/1.1/}creator', '')],
                           'published': announced, 'url': link, 'pdf_url': link.replace('/abs/', '/pdf/'),
                           'provider': 'arXiv RSS', 'venue': 'arXiv 预印本 · 首次公告', 'importable': True})
        _feed_cache[category] = (local_now(), papers)
        return papers


def search_arxiv(topics, today):
    terms = ' OR '.join('(' + ' AND '.join(f'all:{term}' for term in t['query'].split()) + ')' for t in topics)
    since = today - timedelta(days=30)
    response = requests.get('https://export.arxiv.org/api/query', params={
        'search_query': f'({terms}) AND (cat:cs.* OR cat:stat.ML) AND submittedDate:[{since:%Y%m%d}0000 TO {today:%Y%m%d}2359]',
        'start': 0, 'max_results': 30, 'sortBy': 'submittedDate', 'sortOrder': 'descending',
    }, headers={'User-Agent': 'PaperAgent/2.0 daily-discovery'}, timeout=(4, 12))
    response.raise_for_status()
    papers = []
    for entry in ET.fromstring(response.content).findall('a:entry', ATOM):
        match = re.search(r'arxiv\.org/abs/([\w.\-/]+)$', entry.findtext('a:id', '', ATOM))
        if not match:
            continue
        identifier = match.group(1)
        papers.append({'id': identifier, 'title': ' '.join(entry.findtext('a:title', '', ATOM).split()),
                       'summary': ' '.join(entry.findtext('a:summary', '', ATOM).split())[:1800],
                       'authors': [a.findtext('a:name', '', ATOM) for a in entry.findall('a:author', ATOM)][:6],
                       'published': entry.findtext('a:published', '', ATOM),
                       'url': f'https://arxiv.org/abs/{identifier}', 'pdf_url': f'https://arxiv.org/pdf/{identifier}',
                       'provider': 'arXiv', 'venue': 'arXiv 预印本', 'importable': True})
    return papers


def search_openalex(topics, today):
    papers = []
    for topic in topics[:3]:
        params = {'search': topic['query'], 'per_page': 8,
                  'filter': f'topics.field.id:17,from_publication_date:{today - timedelta(days=30)},to_publication_date:{today}',
                  'sort': 'publication_date:desc'}
        if os.getenv('OPENALEX_API_KEY'):
            params['api_key'] = os.environ['OPENALEX_API_KEY']
        response = requests.get('https://api.openalex.org/works', params=params,
                                headers={'User-Agent': 'PaperAgent/2.0'}, timeout=(4, 10))
        response.raise_for_status()
        for work in response.json().get('results', []):
            location = work.get('best_oa_location') or work.get('primary_location') or {}
            index = work.get('abstract_inverted_index') or {}
            words = sorted((pos, word) for word, positions in index.items() for pos in positions)
            papers.append({'id': work.get('id'), 'title': work.get('display_name', ''),
                           'summary': ' '.join(word for _, word in words)[:1800],
                           'authors': [a.get('author', {}).get('display_name', '') for a in work.get('authorships', [])][:6],
                           'published': work.get('publication_date', ''),
                           'url': location.get('landing_page_url') or work.get('doi') or work.get('id') or '',
                           'pdf_url': location.get('pdf_url') or '', 'provider': 'OpenAlex',
                           'venue': (location.get('source') or {}).get('display_name') or '来源未注明', 'importable': False,
                           'fields': [t.get('field', {}).get('id', '') for t in work.get('topics', [])]})
    return papers


def select_papers(papers, topics, today, known_titles):
    from core.decision.external_search import filter_computer_papers
    papers = filter_computer_papers(papers, [t['query'] for t in topics])
    normalize = lambda title: re.sub(r'\W+', '', title.lower().removesuffix('.pdf'))
    seen = set()
    known = {normalize(title) for title in known_titles}
    chosen = []
    for paper in papers:
        key = normalize(str(paper.get('title') or ''))
        if not key or key in seen or key in known:
            continue
        try:
            published = datetime.fromisoformat(paper['published'].replace('Z', '+00:00')).date()
        except (ValueError, TypeError, KeyError):
            continue
        if not today - timedelta(days=30) <= published <= today:
            continue
        if not str(paper.get('url', '')).startswith(('https://', 'http://')):
            continue
        text = re.sub(r'[-–—]+', ' ', (paper['title'] + ' ' + str(paper.get('summary') or '')).lower())
        scores = [sum(bool(re.search(r'\b' + re.escape(term) + r'\b', text)) for term in t['query'].lower().split()) / len(t['query'].split()) for t in topics]
        if not scores or max(scores) < .5:
            continue
        topic = topics[scores.index(max(scores))]
        matched_topics = [t['label'] for t, score in zip(topics, scores) if score >= .5]
        seen.add(key)
        chosen.append({**paper, 'published': published.isoformat(), 'topic': topic['label'], 'topics': matched_topics, 'is_today': published == today,
                       'reason': f'关键词与「{topic["label"]}」匹配；依据：{topic["basis"]}', '_score': max(scores)})
    chosen.sort(key=lambda p: (p['published'], p['_score']), reverse=True)
    # Reserve a result for every matched direction before filling remaining slots.
    selected = []
    for topic in topics:
        if any(topic['label'] in p['topics'] for p in selected):
            continue
        candidate = next((p for p in chosen if topic['label'] in p['topics']), None)
        if candidate:
            selected.append(candidate)
    selected += [p for p in chosen if p not in selected][:6-len(selected)]
    selected.sort(key=lambda p: (p['published'], p['_score']), reverse=True)
    return [{k: v for k, v in p.items() if k != '_score'} for p in selected]


def build_daily_recommendations(account, evidence, force=False):
    stamp = local_now()
    today = stamp.date()
    profile = computer_research_profile(evidence)
    # Cache holds the local interest profile and public metadata, never raw activity text.
    fingerprint = hashlib.sha256(('v3-cs:' + json.dumps(profile, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()
    key = hashlib.sha256(account.encode()).hexdigest()
    directory = Path(os.getenv('DAILY_RECOMMENDATION_CACHE_DIR', './res/daily_recommendations'))
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{key}.json'
    with _guard:
        lock = _locks.setdefault(key, threading.Lock())
    with lock:
        cached = None
        try:
            cached = json.loads(path.read_text(encoding='utf-8'))
            age = (stamp - datetime.fromisoformat(cached['generated_at'])).total_seconds()
            ttl = 60 if force or cached.get('status') == 'unavailable' else 4 * 3600
            if not force and cached['date'] == today.isoformat() and cached.get('fingerprint') == fingerprint and age < ttl:
                return {**cached, 'cached': True}
        except (OSError, ValueError, KeyError):
            cached = None
        result = {'date': today.isoformat(), 'generated_at': stamp.isoformat(), 'profile': profile,
                  'items': [], 'warning': '', 'status': 'no_interests', 'cached': False,
                  'fingerprint': fingerprint, 'window_days': 30}
        if profile['topics']:
            unavailable = False
            topics = profile['topics']
            known_titles = [p['name'] for p in evidence.get('papers', [])]
            def missing_topics(items):
                covered = {label for p in items for label in p.get('topics', [p['topic']])}
                return [t for t in topics if t['label'] not in covered]
            try:
                papers = select_papers(search_arxiv_feed(topics, today), topics, today, known_titles)
            except Exception:
                papers = []
                unavailable = True
            missing = missing_topics(papers)
            if missing:
                try:
                    papers = select_papers(papers + search_arxiv(missing, today), topics, today, known_titles)
                    unavailable = False
                except Exception:
                    unavailable = True
            missing = missing_topics(papers)
            if missing:
                try:
                    papers = select_papers(papers + search_openalex(missing, today), topics, today, known_titles)
                    result['warning'] = '部分方向已补充检索 OpenAlex；来源可能存在收录延迟'
                    unavailable = False
                except Exception:
                    unavailable = True
            result['items'] = papers
            result['status'] = 'ready' if result['items'] else ('unavailable' if unavailable else 'no_results')
            if unavailable:
                if papers:
                    result['warning'] = '部分方向的补充检索暂不可用，已保留可用推荐；可点击更新推荐重试'
                if cached and cached.get('fingerprint') == fingerprint and cached.get('items'):
                    if not papers:
                        return {**cached, 'cached': True, 'status': 'stale', 'warning': '最新检索暂不可用，以下保留上次推荐，请留意论文日期与更新时间'}
                if not papers:
                    result['warning'] = '论文来源暂不可用，请稍后刷新'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        temporary.replace(path)
        return result
