import unittest
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.keyring_service import KeyringService
from src.core.process_supervisor import ProcessSupervisor
from src.core.device_service import DeviceService
from src.proxy.token_manager import TokenManager, RateLimitReason
from src.proxy.thinking_store import ThinkingStore

class TestHybridSubsystems(unittest.TestCase):

    def test_keyring_advapi32_roundtrip(self):
        if sys.platform != "win32":
            self.skipTest("Windows-only Advapi32 test")
        # Write test credential
        now = 1774345200
        ok = KeyringService.write_credential("test_access_token", "1//test_refresh_token", now)
        self.assertTrue(ok)

        # Read back
        cred = KeyringService.read_credential()
        self.assertIsNotNone(cred)
        self.assertEqual(cred["token"]["refresh_token"], "1//test_refresh_token")

        # Cleanup
        KeyringService.delete_credential()

    def test_device_profile_generation(self):
        prof = DeviceService.generate_device_profile()
        self.assertIn("machine_id", prof)
        self.assertIn("dev_device_id", prof)
        self.assertEqual(len(prof["machine_id"]), 64)

    def test_thinking_store_packing(self):
        store = ThinkingStore("test_thinking.db")
        large_thought = "Thinking reasoning block step 1... " * 50
        packed = store.pack_thought(large_thought)
        # Verify gzip compression prefix
        self.assertTrue(packed.startswith(b"AGZ1"))
        unpacked = store.unpack_thought(packed)
        self.assertEqual(unpacked, large_thought)

        if os.path.exists("test_thinking.db"):
            os.remove("test_thinking.db")

    def test_token_manager_429_classification(self):
        reason1 = TokenManager.classify_rate_limit("Resource has been exhausted (quota_exhausted)")
        self.assertEqual(reason1, RateLimitReason.QUOTA_EXHAUSTED)

        reason2 = TokenManager.classify_rate_limit("Model_capacity reached")
        self.assertEqual(reason2, RateLimitReason.MODEL_CAPACITY_EXHAUSTED)

        reason3 = TokenManager.classify_rate_limit("Too many requests per minute")
        self.assertEqual(reason3, RateLimitReason.RATE_LIMIT_EXCEEDED)

    def test_process_supervisor_arg_sanitizer(self):
        dirty_args = ["--standalone", "--override_ide_name=foo", "e:/workspace", "--language_server=abc"]
        clean = ProcessSupervisor.sanitize_restart_args(dirty_args)
        self.assertEqual(clean, ["e:/workspace"])

if __name__ == "__main__":
    unittest.main()
