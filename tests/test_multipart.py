from datetime import datetime, timedelta
import os
from importlib.machinery import SourceFileLoader

# Load module directly from file because the package name contains a hyphen
ROOT = os.path.dirname(os.path.dirname(__file__))
MODULE_PATH = os.path.join(ROOT, "src", "sms-dashboard", "multipart.py")
multipart = SourceFileLoader("multipart", MODULE_PATH).load_module()
assemble_inbox_rows = multipart.assemble_inbox_rows


def test_single_non_multipart_passes_through():
    rows = [
        {
            "ID": 1,
            "SenderNumber": "+123",
            "TextDecoded": "Hello",
            "ReceivingDateTime": datetime.now(),
            "Processed": "false",
        }
    ]
    out = assemble_inbox_rows(rows)
    assert len(out) == 1
    assert out[0]["TextDecoded"] == "Hello"


def test_multipart_8bit_udh_combines_parts_ordered():
    base = datetime.now()
    # Example 8-bit UDH: 00 03 ref total seq -> we wrap with a typical 05 length prefix as seen in some tools
    # We'll omit prefix and provide IE directly: 00 03 A4 02 01 (seq 1), 00 03 A4 02 02 (seq 2)
    part1 = {
        "ID": 10,
        "SenderNumber": "+111",
        "TextDecoded": "Part1-",
        "ReceivingDateTime": base,
        "Processed": "false",
        "UDH": "0003A40201",
        "SequencePosition": 1,
    }
    part2 = {
        "ID": 11,
        "SenderNumber": "+111",
        "TextDecoded": "Part2",
        "ReceivingDateTime": base + timedelta(seconds=2),
        "Processed": "false",
        "UDH": "0003A40202",
        "SequencePosition": 2,
    }
    out = assemble_inbox_rows([part2, part1])
    assert len(out) == 1
    m = out[0]
    assert m["TextDecoded"] == "Part1-Part2"
    # Keeps unread if any part unread
    assert str(m.get("Processed")).lower() == "false"
    assert set(m.get("_part_ids", [])) == {10, 11}


def test_empty_parts_are_filtered_out():
    base = datetime.now()
    part1 = {"ID": 20, "SenderNumber": "+222", "TextDecoded": "", "ReceivingDateTime": base, "Processed": "false", "UDH": "0003A40101"}
    part2 = {"ID": 21, "SenderNumber": "+222", "TextDecoded": "Hello", "ReceivingDateTime": base + timedelta(seconds=1), "Processed": "false", "UDH": "0003A40102"}
    out = assemble_inbox_rows([part1, part2])
    assert len(out) == 1
    assert out[0]["TextDecoded"] == "Hello"


def test_discard_when_combined_is_empty():
    base = datetime.now()
    part1 = {"ID": 30, "SenderNumber": "+333", "TextDecoded": " ", "ReceivingDateTime": base, "Processed": "true", "UDH": "0003A40101"}
    part2 = {"ID": 31, "SenderNumber": "+333", "TextDecoded": "\t", "ReceivingDateTime": base, "Processed": "true", "UDH": "0003A40102"}
    out = assemble_inbox_rows([part1, part2])
    assert out == []
