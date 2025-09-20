"""
Utilities to assemble Gammu SMSD multipart messages and hide empty rows.

Gammu stores each SMS part as a row in `inbox`. Many parts can have empty
`TextDecoded` when messages are concatenated via UDH. We detect UDH
concatenation, group parts, and produce a single combined message, filtering
out the intermediate empty rows.

This is done purely in application logic; no DB schema changes are required.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class ConcatKey:
    sender: str
    ref: str  # textual reference key extracted from UDH (8/16-bit safe)


def _bytes_to_hex(data: bytes) -> str:
    return data.hex()


def _parse_udh_concat(udh: bytes | str | None) -> Optional[Tuple[int, int, int]]:
    """
    Parse UDH for concatenation headers.

    Returns (ref, total_parts, sequence) if this looks like a concatenated UDH.
    Supports 8-bit (05 00 03 ref total seq) and 16-bit (06 08 04 ref_hi ref_lo total seq).
    """
    if not udh:
        return None
    try:
        if isinstance(udh, str):
            # Could be hex string like "050003A40201" or text; try to normalize
            s = udh.strip().lower().replace(" ", "")
            # Ensure even length
            if len(s) % 2 == 1:
                return None
            b = bytes.fromhex(s)
        else:
            b = bytes(udh)
    except Exception:
        return None

    if len(b) < 5:
        return None

    # 8-bit ref: IEI=0x00, IEDL=0x03, pattern: 05 00 03 ref total seq
    # length can vary because UDH can contain multiple IEs; minimal check
    # Some gateways omit the leading overall-length byte. Handle both.
    def match_8bit(buf: bytes) -> Optional[Tuple[int, int, int]]:
        for i in range(0, len(buf) - 4):
            if buf[i] == 0x00 and i + 3 < len(buf) and buf[i + 1] == 0x03:
                ref = buf[i + 2]
                total = buf[i + 3]
                seq = buf[i + 4] if i + 4 < len(buf) else None
                if seq is not None and total and 1 <= seq <= total:
                    return (ref, total, seq)
        return None

    # 16-bit ref: IEI=0x08, IEDL=0x04 -> ref_hi ref_lo total seq
    def match_16bit(buf: bytes) -> Optional[Tuple[int, int, int]]:
        for i in range(0, len(buf) - 5):
            if buf[i] == 0x08 and i + 4 < len(buf) and buf[i + 1] == 0x04:
                ref = (buf[i + 2] << 8) | buf[i + 3]
                total = buf[i + 4]
                seq = buf[i + 5] if i + 5 < len(buf) else None
                if seq is not None and total and 1 <= seq <= total:
                    return (ref, total, seq)
        return None

    # Some implementations prefix with overall UDH length at byte 0.
    # Try with and without that first byte.
    for candidate in (b, b[1:] if len(b) > 1 else b):
        m = match_8bit(candidate) or match_16bit(candidate)
        if m:
            return m
    return None


def _concat_key(sender: str | None, udh: bytes | str | None) -> Optional[ConcatKey]:
    parsed = _parse_udh_concat(udh)
    if parsed is None:
        return None
    ref, _total, _seq = parsed
    s = sender or ""
    return ConcatKey(s, f"{ref}")



def assemble_inbox_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Collapse multipart inbox rows into single combined logical messages.

    Strategy:
    - Detect concatenated parts via UDH; group by (SenderNumber, ref).
    - Order parts by sequence from UDH if present, else by ID.
    - Combine TextDecoded from all parts (skip None/empty during join to avoid blank spam).
    - Produce a single synthetic row based on the newest part's metadata and combined text.
    - For non-multipart or messages without UDH, include as-is.
    - If the combined text is empty after trimming, drop the message.

    Input row keys expected: ID, SenderNumber, TextDecoded, ReceivingDateTime, Processed, UDH.
    Missing keys are handled gracefully.
    """
    singles: List[Dict[str, Any]] = []
    groups: Dict[ConcatKey, List[Dict[str, Any]]] = {}

    for r in rows:
        key = _concat_key(r.get("SenderNumber"), r.get("UDH"))
        if key is None:
            singles.append(r)
        else:
            groups.setdefault(key, []).append(r)

    out: List[Dict[str, Any]] = []
    out.extend(singles)

    def sort_key(item: Dict[str, Any]) -> Tuple[int, Any]:
        # Prefer UDH sequence if present, else ID
        udh = item.get("UDH")
        parsed = _parse_udh_concat(udh)
        if parsed:
            return (0, parsed[2])  # sequence
        return (1, item.get("ID", 0))

    for parts in groups.values():
        parts_sorted = sorted(parts, key=sort_key)
        texts: List[str] = []
        for p in parts_sorted:
            t = p.get("TextDecoded")
            if isinstance(t, str) and t.strip():
                texts.append(t)
        combined = "".join(texts).strip()
        if not combined:
            # nothing meaningful, skip
            continue
        # Use the newest part for metadata (ReceivingDateTime biggest)
        newest = max(parts_sorted, key=lambda x: x.get("ReceivingDateTime") or 0)
        # clone and replace text; mark as processed if all are processed
        merged = dict(newest)
        merged["TextDecoded"] = combined
        # If any part is unread, keep unread; else read
        try:
            processed_vals = {str(p.get("Processed", "")).lower() for p in parts_sorted}
            merged["Processed"] = "false" if "false" in processed_vals else "true"
        except Exception:
            pass
        # store a synthetic list of part IDs for traceability
        merged["_part_ids"] = [p.get("ID") for p in parts_sorted]
        out.append(merged)

    # Sort final list by ReceivingDateTime desc if available, else ID desc
    out.sort(key=lambda x: x.get("ReceivingDateTime") or x.get("ID", 0), reverse=True)
    return out
