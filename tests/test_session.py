"""Tests for dac.core.session."""
import os
import tempfile
import unittest

os.environ["DAC_HOME"] = tempfile.mkdtemp(prefix="dac-test-session-")

from dac.core.session import Session, list_sessions, SYSTEM_PROMPT  # noqa: E402


class SessionTest(unittest.TestCase):
    def test_add_and_persist_messages(self):
        s = Session(session_id="test-sess")
        s.add_user("hello")
        s.add_assistant("hi there")
        s2 = Session(session_id="test-sess")
        self.assertEqual(s2.messages, [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ])

    def test_get_full_messages_includes_system(self):
        s = Session(session_id="test-full")
        s.add_user("u1")
        msgs = s.get_full_messages()
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[0]["content"], SYSTEM_PROMPT)
        self.assertEqual(msgs[-1], {"role": "user", "content": "u1"})

    def test_history_capped_at_50(self):
        s = Session(session_id="test-cap")
        for i in range(60):
            s.add_user(f"msg-{i}")
        msgs = s.get_full_messages()
        body = [m for m in msgs if m["role"] == "user"]
        self.assertEqual(len(body), 50)
        self.assertEqual(body[0]["content"], "msg-10")

    def test_clear(self):
        s = Session(session_id="test-clear")
        s.add_user("x")
        s.clear()
        self.assertEqual(s.messages, [])

    def test_list_sessions(self):
        Session(session_id="sess-aaa").add_user("x")
        names = [s["id"] for s in list_sessions()]
        self.assertIn("sess-aaa", names)

    def test_status(self):
        s = Session(session_id="test-status")
        s.add_user("x")
        st = s.status()
        self.assertEqual(st["session_id"], "test-status")
        self.assertEqual(st["turns"], 1)


if __name__ == "__main__":
    unittest.main()
