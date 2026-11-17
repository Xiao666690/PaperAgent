import unittest
from types import SimpleNamespace
from core.backend.router.router_qa import _stream_model_text

class StreamingCompletionTests(unittest.TestCase):
    def test_length_finish_resumes_without_dropping_tail(self):
        class Agent:
            def __init__(self): self.prompts = []
            def chat_simple(self, prompt):
                self.prompts.append(prompt)
                if len(self.prompts) == 1:
                    yield SimpleNamespace(content="12. Paper title", response_metadata={})
                    yield SimpleNamespace(content="", response_metadata={"finish_reason": "length"})
                else:
                    yield SimpleNamespace(content=" — complete summary.\n13. Last paper.", response_metadata={"finish_reason": "stop"})
        agent = Agent()
        result = "".join(_stream_model_text(agent, "Summarize", continue_on_length=True))
        self.assertIn("complete summary", result)
        self.assertIn("13. Last paper", result)
        self.assertEqual(len(agent.prompts), 2)
        self.assertIn("12. Paper title", agent.prompts[1])

    def test_normal_stop_does_not_issue_extra_request(self):
        class Agent:
            def __init__(self): self.calls = 0
            def chat_simple(self, prompt):
                self.calls += 1
                yield SimpleNamespace(content="Complete", response_metadata={"finish_reason": "stop"})
        agent = Agent()
        self.assertEqual("".join(_stream_model_text(agent, "Question", continue_on_length=True)), "Complete")
        self.assertEqual(agent.calls, 1)

    def test_persistent_length_is_bounded_and_visible(self):
        class Agent:
            def __init__(self): self.calls = 0
            def chat_simple(self, prompt):
                self.calls += 1
                yield SimpleNamespace(content="More", response_metadata={"finish_reason": "length"})
        agent = Agent()
        result = "".join(_stream_model_text(agent, "Question", continue_on_length=True))
        self.assertEqual(agent.calls, 3)
        self.assertIn("尚未完整", result)
