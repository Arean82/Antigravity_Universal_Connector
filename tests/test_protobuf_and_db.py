import unittest
import base64
from src.core.protobuf_codec import (
    encode_varint,
    read_varint,
    create_oauth_info,
    create_unified_state_entry,
    decode_unified_state_entry,
    remove_unified_topic_entry,
    find_field,
)
from src.core.vscdb_importer import find_active_db_path, extract_oauth_state_from_db


class TestProtobufAndDB(unittest.TestCase):
    def test_varint_codec(self):
        val = 150
        encoded = encode_varint(val)
        decoded, offset = read_varint(encoded)
        self.assertEqual(val, decoded)
        self.assertEqual(len(encoded), offset)

    def test_oauth_info_creation_and_fields(self):
        access_token = "ya29.test_access_token"
        refresh_token = "1//test_refresh_token"
        expiry = 1700000000

        blob = create_oauth_info(
            access_token=access_token,
            refresh_token=refresh_token,
            expiry=expiry,
            is_gcp_tos=False,
            email="test@gmail.com"
        )
        # Check Field 1 is access_token
        f1 = find_field(blob, 1)
        self.assertEqual(f1.decode("utf-8"), access_token)

        # Check Field 3 is refresh_token
        f3 = find_field(blob, 3)
        self.assertEqual(f3.decode("utf-8"), refresh_token)

    def test_unified_state_entry_roundtrip(self):
        sentinel = "oauthTokenInfoSentinelKey"
        payload = b"binary_test_payload_12345"

        encoded_b64 = create_unified_state_entry(sentinel, payload)
        decoded_sentinel, decoded_payload = decode_unified_state_entry(encoded_b64)

        self.assertEqual(sentinel, decoded_sentinel)
        self.assertEqual(payload, decoded_payload)

    def test_detect_local_antigravity_db(self):
        db_path = find_active_db_path()
        if db_path and db_path.exists():
            state = extract_oauth_state_from_db(db_path)
            self.assertIn("refresh_token", state)
            self.assertTrue(state["refresh_token"].startswith("1//"))
            print(f"\n[Verified] Found live Antigravity refresh_token starting with: {state['refresh_token'][:10]}...")


if __name__ == "__main__":
    unittest.main()
