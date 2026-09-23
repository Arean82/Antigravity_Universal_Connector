r"""Pure Python Protobuf Varint and Length-Delimited Codec.
Direct line-by-line refactor of E:\GitHub\Antigravity-Manager\src-tauri\src\utils\protobuf.rs.
Zero third-party dependencies, zero regex.
"""

from __future__ import annotations
import base64
from typing import Optional, Tuple, List


def encode_varint(value: int) -> bytes:
    """Encode an integer as a protobuf varint."""
    buf = bytearray()
    val = value
    while val >= 0x80:
        buf.append((val & 0x7F) | 0x80)
        val >>= 7
    buf.append(val & 0x7F)
    return bytes(buf)


def read_varint(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """Read a protobuf varint from data starting at offset.
    Returns (value, new_offset).
    """
    result = 0
    shift = 0
    pos = offset
    while pos < len(data):
        byte = data[pos]
        result |= (byte & 0x7F) << shift
        pos += 1
        if (byte & 0x80) == 0:
            return result, pos
        shift += 7
    raise ValueError("Incomplete varint data")


def skip_field(data: bytes, offset: int, wire_type: int) -> int:
    """Skip a protobuf field based on wire type.
    Returns the new offset.
    """
    if wire_type == 0:  # Varint
        _, new_offset = read_varint(data, offset)
        return new_offset
    elif wire_type == 1:  # 64-bit
        return offset + 8
    elif wire_type == 2:  # Length-delimited
        length, content_offset = read_varint(data, offset)
        return content_offset + length
    elif wire_type == 5:  # 32-bit
        return offset + 4
    else:
        raise ValueError(f"Unknown wire type: {wire_type}")


def find_field(data: bytes, target_field: int) -> Optional[bytes]:
    """Find first specified Protobuf field content (wire_type == 2: Length-Delimited only).
    Port of find_field in protobuf.rs:85-109.
    """
    fields = find_all_fields(data, target_field)
    return fields[0] if fields else None


def find_all_fields(data: bytes, target_field: int) -> List[bytes]:
    """Find all occurrences of a length-delimited field in protobuf data."""
    results: List[bytes] = []
    offset = 0
    while offset < len(data):
        try:
            tag, new_offset = read_varint(data, offset)
        except ValueError:
            break
        wire_type = tag & 7
        field_num = tag >> 3

        if field_num == target_field and wire_type == 2:
            length, content_offset = read_varint(data, new_offset)
            results.append(data[content_offset:content_offset + length])

        offset = skip_field(data, new_offset, wire_type)
    return results


def find_varint_field(data: bytes, target_field: int) -> Optional[int]:
    """Find specified Protobuf varint field value (wire_type == 0).
    Port of find_varint_field in protobuf.rs:364-381.
    """
    offset = 0
    while offset < len(data):
        try:
            tag, new_offset = read_varint(data, offset)
        except ValueError:
            break
        wire_type = tag & 7
        field_num = tag >> 3

        if field_num == target_field and wire_type == 0:
            val, _ = read_varint(data, new_offset)
            return val

        offset = skip_field(data, new_offset, wire_type)
    return None


def encode_len_delim_field(field_num: int, data: bytes) -> bytes:
    """Encode length-delimited field (wire_type = 2)."""
    tag = (field_num << 3) | 2
    return encode_varint(tag) + encode_varint(len(data)) + data


def encode_string_field(field_num: int, value: str) -> bytes:
    """Encode UTF-8 string field (wire_type = 2)."""
    return encode_len_delim_field(field_num, value.encode("utf-8"))


def encode_varint_field(field_num: int, value: int) -> bytes:
    """Encode varint field (wire_type = 0)."""
    tag = (field_num << 3) | 0
    return encode_varint(tag) + encode_varint(value)


def create_oauth_info(
    access_token: str,
    refresh_token: str,
    expiry: int,
    is_gcp_tos: bool = False,
    id_token: Optional[str] = None,
    email: Optional[str] = None,
) -> bytes:
    """Create binary OAuthTokenInfo payload.
    Port of create_oauth_info in protobuf.rs:210-277.
    """
    # Auto-correct GCP flag for personal accounts
    if email:
        email_lower = email.lower()
        if (
            email_lower.endswith("@gmail.com")
            or email_lower.endswith("@outlook.com")
            or email_lower.endswith("@hotmail.com")
        ):
            is_gcp_tos = False

    parts: List[bytes] = []

    # Field 1: access_token
    parts.append(encode_string_field(1, access_token))

    # Field 2: token_type = "Bearer"
    parts.append(encode_string_field(2, "Bearer"))

    # Field 3: refresh_token
    parts.append(encode_string_field(3, refresh_token))

    # Field 4: expiry (Timestamp { int64 seconds = 1; int32 nanos = 2 })
    timestamp_msg = encode_varint((1 << 3) | 0) + encode_varint(expiry) + encode_varint((2 << 3) | 0) + encode_varint(0)
    parts.append(encode_len_delim_field(4, timestamp_msg))

    # Field 5: id_token
    if id_token:
        parts.append(encode_string_field(5, id_token))

    # Field 6: is_gcp_tos
    if is_gcp_tos:
        parts.append(encode_varint_field(6, 1))

    return b"".join(parts)


def _safe_b64decode(s: str) -> bytes:
    """Decode base64 string, adding missing padding if necessary."""
    missing_padding = len(s) % 4
    if missing_padding:
        s += '=' * (4 - missing_padding)
    return base64.b64decode(s)


def decode_unified_state_entry(outer_b64: str, target_sentinel: Optional[str] = None) -> Tuple[str, bytes]:
    """Decode unified state entry returning (sentinel_key, payload).
    Port of decode_unified_state_entry in protobuf.rs:352-361.
    """
    outer_blob = _safe_b64decode(outer_b64)

    # 1. Try topic row payload (decode_topic_row_payload in protobuf.rs:303-321)
    try:
        data_entries = find_all_fields(outer_blob, 1)
        for data_entry in data_entries:
            key_bytes = find_field(data_entry, 1)
            row_blob = find_field(data_entry, 2)
            if key_bytes and row_blob:
                sentinel_key = key_bytes.decode("utf-8")
                if target_sentinel and sentinel_key != target_sentinel:
                    continue  # Keep searching for desired sentinel key
                encoded_payload_bytes = find_field(row_blob, 1)
                if encoded_payload_bytes:
                    payload = _safe_b64decode(encoded_payload_bytes.decode("utf-8"))
                    return sentinel_key, payload
    except Exception:
        pass

    # 2. Try legacy outer field 1 format (decode_legacy_unified_state_entry in protobuf.rs:323-333)
    inner_blob = find_field(outer_blob, 1)
    if inner_blob:
        key_bytes = find_field(inner_blob, 1)
        payload = find_field(inner_blob, 2)
        if key_bytes and payload:
            sentinel_key = key_bytes.decode("utf-8")
            if target_sentinel and sentinel_key != target_sentinel:
                pass
            else:
                try:
                    if len(payload) % 4 == 0:
                        decoded = _safe_b64decode(payload.decode("utf-8"))
                        if decoded:
                            return sentinel_key, decoded
                except Exception:
                    pass
                return sentinel_key, payload

    raise ValueError("Failed to decode unified state entry")


def create_unified_state_entry(sentinel_key: str, payload: bytes) -> str:
    """Create unified state sync entry returning Base64 string.
    Port of create_unified_state_entry in protobuf.rs:335-348.
    """
    row = encode_string_field(1, base64.b64encode(payload).decode("ascii"))
    data_entry = encode_string_field(1, sentinel_key) + encode_len_delim_field(2, row)
    topic = encode_len_delim_field(1, data_entry)
    return base64.b64encode(topic).decode("ascii")


def create_unified_topic_entry(sentinel_key: str, payload: bytes) -> bytes:
    """Create unified-state Topic.data entry.
    Port of create_unified_topic_entry in protobuf.rs:398-407.
    """
    row = encode_string_field(1, base64.b64encode(payload).decode("ascii"))
    entry = encode_string_field(1, sentinel_key) + encode_len_delim_field(2, row)
    return encode_len_delim_field(1, entry)


def remove_unified_topic_entry(data: bytes, target_key: str) -> bytes:
    """Remove target sentinel entry from Topic.data blob.
    Port of remove_unified_topic_entry in protobuf.rs:410-440.
    """
    result = bytearray()
    offset = 0
    while offset < len(data):
        start_offset = offset
        try:
            tag, new_offset = read_varint(data, offset)
        except ValueError:
            break
        wire_type = tag & 7
        field_num = tag >> 3
        next_offset = skip_field(data, new_offset, wire_type)

        should_remove = False
        if field_num == 1 and wire_type == 2:
            length, content_offset = read_varint(data, new_offset)
            entry = data[content_offset:content_offset + length]
            # Check key inside entry
            entry_key_bytes = find_field(entry, 1)
            if entry_key_bytes and entry_key_bytes.decode("utf-8") == target_key:
                should_remove = True

        if not should_remove:
            result.extend(data[start_offset:next_offset])
        offset = next_offset

    return bytes(result)


def create_minimal_user_status_payload(email: str) -> bytes:
    """Port of create_minimal_user_status_payload in protobuf.rs:393-395."""
    return encode_string_field(3, email) + encode_string_field(7, email)
