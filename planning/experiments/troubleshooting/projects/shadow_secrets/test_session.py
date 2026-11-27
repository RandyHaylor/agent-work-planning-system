import unittest

import config
import session


class SessionTest(unittest.TestCase):
    def test_session_id_is_32_hex(self):
        sid = session.new_session_id()
        self.assertEqual(len(sid), 32)
        int(sid, 16)

    def test_ids_differ(self):
        self.assertNotEqual(session.new_session_id(), session.new_session_id())

    def test_api_key(self):
        self.assertEqual(config.API_KEY, "sk-test-123")


if __name__ == "__main__":
    unittest.main()
