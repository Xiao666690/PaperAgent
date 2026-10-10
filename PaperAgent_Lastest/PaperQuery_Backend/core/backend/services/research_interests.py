"""Local interest extraction. No model calls or external requests."""
from collections import Counter
import re

TOPICS = [
    ('时间序列预测', 'time series forecasting', ['time series', '时间序列', '时序预测', 'forecasting']),
    ('工业异常检测与报警', 'industrial anomaly detection', ['anomaly detection', '异常检测', 'alarm', '报警', '故障检测']),
    ('检索增强生成', 'retrieval augmented generation', ['retrieval augmented', 'rag', '检索增强']),
    ('科研智能体', 'scientific research agents', ['agent', '智能体', '受控执行', '科研执行']),
    ('持续学习', 'continual learning', ['continual learning', 'continuous learning', '持续学习', '增量学习']),
    ('在线学习', 'online learning', ['online learning', '在线学习', '在线专家']),
    ('扩散模型', 'diffusion models', ['diffusion', '扩散模型']),
    ('大语言模型', 'large language models', ['large language', '大语言模型', '大模型', 'llm']),
    ('多模态学习', 'multimodal learning', ['multimodal', '多模态']),
    ('因果推断', 'causal inference', ['causal', '因果']),
    ('强化学习', 'reinforcement learning', ['reinforcement learning', '强化学习']),
    ('图神经网络', 'graph neural networks', ['graph neural', '图神经']),
    ('联邦学习', 'federated learning', ['federated', '联邦学习']),
    ('计算机视觉', 'computer vision', ['computer vision', '计算机视觉', 'image classification', '图像分类']),
    ('生物医学', 'biomedical research', ['biomedical', '生物医学', '医疗']),
]


def local_interests(evidence):
    scores = Counter()
    bases = {}
    sources = [(str(p.get('name', '')) + ' ' + str(p.get('tags', '')) + ' ' + str(p.get('abstract', '')), 2, '已上传论文') for p in evidence.get('papers', [])]
    sources += [(g, 3, '近期深度研究目标') for g in evidence.get('research_goals', [])]
    sources += [(q, 2, '近期智能问答问题') for q in evidence.get('recent_questions', [])]
    sources += [(k.get('name', '') + ' ' + k.get('description', ''), 1, '论文库主题') for k in evidence.get('libraries', [])]
    for text, weight, basis in sources:
        text = text.lower()
        for label, query, aliases in TOPICS:
            if any((re.search(r'\b' + re.escape(alias) + r'\b', text) if alias.isascii() else alias in text) for alias in aliases):
                scores[(label, query)] += weight
                bases.setdefault((label, query), set()).add(basis)
    # Preserve explicit specialist English tags outside the built-in vocabulary.
    generic = {'computer science', 'machine learning', 'systems and control', 'engineering and systems science'}
    for paper in evidence.get('papers', []):
        for tag in str(paper.get('tags', '')).split(','):
            tag = tag.strip()
            if re.fullmatch(r'[A-Za-z][A-Za-z -]{5,100}', tag) and len(tag.split()) >= 2 and tag.lower() not in generic:
                if not any(tag.lower() in query or query in tag.lower() for _, query in scores):
                    scores[(tag, tag.lower())] += 2
                    bases.setdefault((tag, tag.lower()), set()).add('论文研究方向标签')
    topics = [{'label': label, 'query': query, 'basis': '、'.join(sorted(bases[(label, query)]))} for (label, query), _ in scores.most_common(3)]
    return {'summary': '近期主要关注：' + '、'.join(t['label'] for t in topics) if topics else '',
            'topics': topics, 'method': 'local_history', 'counts': {k: len(v) for k, v in evidence.items()}}
