"""
Script to reconstruct multipart SMS messages in a Gammu SMSD database.
It finds rows with empty/null TextDecoded, groups by UDH and SenderNumber, concatenates Text, and updates TextDecoded.
"""
import sqlite3
from typing import List, Tuple

DB_PATH = "path/to/gammu.db"  # TODO: Set your actual DB path

def get_multipart_groups(conn) -> List[Tuple[str, str]]:
    """Find unique (UDH, SenderNumber) pairs with empty TextDecoded."""
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT UDH, SenderNumber
        FROM inbox
        WHERE (TextDecoded IS NULL OR TextDecoded = '')
          AND UDH IS NOT NULL AND UDH != ''
    """)
    return cur.fetchall()

def get_parts(conn, udh, sender) -> List[Tuple[int, str]]:
    """Get all parts for a given UDH and SenderNumber, ordered by ID."""
    cur = conn.cursor()
    cur.execute("""
        SELECT ID, Text
        FROM inbox
        WHERE UDH = ? AND SenderNumber = ?
        ORDER BY ID ASC
    """, (udh, sender))
    return cur.fetchall()

def update_textdecoded(conn, ids: List[int], full_text: str):
    """Update TextDecoded for all IDs in the multipart group."""
    cur = conn.cursor()
    cur.executemany(
        "UPDATE inbox SET TextDecoded = ? WHERE ID = ?",
        [(full_text, id_) for id_ in ids]
    )
    conn.commit()

def reconstruct_multipart_messages():
    conn = sqlite3.connect(DB_PATH)
    groups = get_multipart_groups(conn)
    for udh, sender in groups:
        parts = get_parts(conn, udh, sender)
        if len(parts) > 1:
            ids, texts = zip(*parts)
            full_text = ''.join(texts)
            update_textdecoded(conn, list(ids), full_text)
    # Delete all rows with empty or null TextDecoded
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM inbox
        WHERE TextDecoded IS NULL OR TextDecoded = ''
    """)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    reconstruct_multipart_messages()
    print("Multipart messages reconstructed and TextDecoded updated.")
