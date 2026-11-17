import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from core.agent.chatAgent import ChatAgent
from core.decision.engine import DecisionEngine, is_obvious_general_chat
from core.decision.schemas import IntentType
from core.decision.prompts import ASSISTANT_SYSTEM_PROMPT, GENERAL_CHAT_PROMPT, ANSWER_PROMPT
from langchain_core.messages import SystemMessage, HumanMessage

class AssistantPromptTests(unittest.TestCase):
    def test_real_system_and_user_messages_are_separate(self):
        stream = Mock()
        agent = ChatAgent(None, stream, None)
        agent.chat_simple('解释 Python 装饰器')
        messages = stream.stream.call_args.args[0]
        self.assertIsInstance(messages[0], SystemMessage)
        self.assertEqual(messages[0].content, ASSISTANT_SYSTEM_PROMPT)
        self.assertIsInstance(messages[1], HumanMessage)
        self.assertEqual(messages[1].content, '解释 Python 装饰器')

    def test_general_tasks_do_not_depend_on_bound_documents(self):
        llm = Mock()
        engine = DecisionEngine(llm)
        for query in ['你好', '什么是 RAG', '解释一下 Transformer', '帮我写一个 Python 排序函数',
                      '帮我写封邮件', '翻译一下 hello world', '帮我制定学习计划', 'Explain gradient descent']:
            with self.subTest(query=query):
                self.assertEqual(engine.decide_intent(query, '已选 13 篇论文').intent, IntentType.GENERAL_CHAT)
        llm.invoke.assert_not_called()

    def test_classifier_failure_does_not_force_paper_retrieval(self):
        llm = Mock()
        llm.invoke.side_effect = RuntimeError('classifier unavailable')
        engine = DecisionEngine(llm)
        self.assertEqual(engine.decide_intent('今天吃什么比较好', '已绑定论文').intent, IntentType.GENERAL_CHAT)
        self.assertEqual(engine.decide_intent('这篇论文使用了哪些数据集', '已绑定论文').intent, IntentType.PAPER_QA)
        self.assertFalse(is_obvious_general_chat('解释这篇论文的消融实验'))
        self.assertFalse(is_obvious_general_chat('翻译一下，请结合当前论文第 1 页选中的文字'))

    def test_prompts_are_format_safe_and_allow_helpful_partial_answers(self):
        general = GENERAL_CHAT_PROMPT.format(question='编程问题', selected_papers='a.pdf', conversation_context='历史')
        paper = ANSWER_PROMPT.format(question='GPU 小时是多少', selected_papers='a.pdf', evidence='[C1] 模型介绍')
        self.assertIn('不要求用户先选择论文', general)
        self.assertIn('核查方法', paper)
        self.assertNotIn('明确写"当前证据不足"', paper)

if __name__ == '__main__':
    unittest.main()
