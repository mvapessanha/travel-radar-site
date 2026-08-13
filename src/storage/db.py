"""Camada de persistência (SQLite) para o histórico de preços."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "travel_radar.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS price_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    source TEXT NOT NULL,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    depart_date TEXT NOT NULL,
    return_date TEXT NOT NULL,
    nights INTEGER NOT NULL,
    price REAL NOT NULL,
    currency TEXT NOT NULL,
    airline TEXT,
    collected_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_quotes_lookup
    ON price_quotes (tenant_id, depart_date, nights);

CREATE TABLE IF NOT EXISTS alerts_sent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    depart_date TEXT NOT NULL,
    return_date TEXT NOT NULL,
    price REAL NOT NULL,
    reason TEXT NOT NULL,
    sent_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS digest_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    sent_date TEXT NOT NULL,
    sent_at TEXT NOT NULL
);
"""


@dataclass
class PriceQuote:
    tenant_id: str
    source: str
    origin: str
    destination: str
    depart_date: date
    return_date: date
    nights: int
    price: float
    currency: str
    airline: str | None
    collected_at: datetime


@contextmanager
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_quotes(quotes: list[PriceQuote]) -> None:
    if not quotes:
        return
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO price_quotes
               (tenant_id, source, origin, destination, depart_date, return_date,
                nights, price, currency, airline, collected_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    q.tenant_id, q.source, q.origin, q.destination,
                    q.depart_date.isoformat(), q.return_date.isoformat(), q.nights,
                    q.price, q.currency, q.airline, q.collected_at.isoformat(),
                )
                for q in quotes
            ],
        )


def fetch_all_quotes(tenant_id: str) -> list[dict]:
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM price_quotes WHERE tenant_id = ? ORDER BY collected_at",
            (tenant_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def min_price_ever(tenant_id: str, depart_date: str, nights: int) -> float | None:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT MIN(price) FROM price_quotes
               WHERE tenant_id = ? AND depart_date = ? AND nights = ?""",
            (tenant_id, depart_date, nights),
        ).fetchone()
        return row[0] if row and row[0] is not None else None


def record_alert(tenant_id: str, depart_date: str, return_date: str, price: float, reason: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO alerts_sent (tenant_id, depart_date, return_date, price, reason, sent_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (tenant_id, depart_date, return_date, price, reason, datetime.now().isoformat()),
        )


def digest_sent_today(tenant_id: str, today: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM digest_log WHERE tenant_id = ? AND sent_date = ? LIMIT 1",
            (tenant_id, today),
        ).fetchone()
        return row is not None


def record_digest(tenant_id: str, today: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO digest_log (tenant_id, sent_date, sent_at) VALUES (?, ?, ?)",
            (tenant_id, today, datetime.now().isoformat()),
        )
