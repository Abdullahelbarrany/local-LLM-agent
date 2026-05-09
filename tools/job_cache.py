"""
SQLite-backed job cache (Enhancement 3).

Cache key = SHA256(url). Entries are considered fresh for ttl_hours after fetching.
Uses aiosqlite for non-blocking I/O from async contexts.
"""

import hashlib
import os
from datetime import datetime, timedelta, timezone

import aiosqlite

_DB_PATH = os.getenv("JOB_CACHE_DB", "job_cache.db")


class JobCache:
    def __init__(self, db_path: str = _DB_PATH) -> None:
        self.db_path = db_path

    async def init_db(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    url_hash    TEXT    UNIQUE NOT NULL,
                    title       TEXT,
                    company     TEXT,
                    location    TEXT,
                    url         TEXT,
                    description TEXT,
                    source      TEXT,
                    fetched_at  TEXT    NOT NULL,
                    raw_html    TEXT,
                    query       TEXT
                )
            """)
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_query    ON jobs(query)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_fetched  ON jobs(fetched_at)"
            )
            await db.commit()

    @staticmethod
    def _url_hash(url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def get(self, url: str) -> dict | None:
        """Return the cached job dict for url, or None."""
        await self.init_db()
        h = self._url_hash(url)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM jobs WHERE url_hash = ?", (h,)
            ) as cur:
                row = await cur.fetchone()
        return dict(row) if row else None

    async def set(self, job_dict: dict) -> None:
        """Insert or update a job entry. Requires job_dict to have a 'url' key."""
        await self.init_db()
        url = job_dict.get("url", "")
        h   = self._url_hash(url)
        now = self._now_iso()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO jobs
                    (url_hash, title, company, location, url,
                     description, source, fetched_at, raw_html, query)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url_hash) DO UPDATE SET
                    title       = excluded.title,
                    company     = excluded.company,
                    location    = excluded.location,
                    description = excluded.description,
                    source      = excluded.source,
                    fetched_at  = excluded.fetched_at,
                    raw_html    = excluded.raw_html,
                    query       = excluded.query
                """,
                (
                    h,
                    job_dict.get("title", ""),
                    job_dict.get("company", ""),
                    job_dict.get("location", ""),
                    url,
                    job_dict.get("description", ""),
                    job_dict.get("source", ""),
                    now,
                    job_dict.get("raw_html", ""),
                    job_dict.get("query", ""),
                ),
            )
            await db.commit()

    async def is_fresh(self, url: str, ttl_hours: int = 24) -> bool:
        """True if the cached entry for url is younger than ttl_hours."""
        entry = await self.get(url)
        if entry is None:
            return False
        try:
            fetched = datetime.fromisoformat(entry["fetched_at"])
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) - fetched < timedelta(hours=ttl_hours)
        except Exception:
            return False

    async def get_all_for_query(
        self, query: str, max_age_hours: int = 48
    ) -> list[dict]:
        """Return all cached jobs for query that are younger than max_age_hours."""
        await self.init_db()
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        ).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM jobs
                WHERE query = ? AND fetched_at > ?
                ORDER BY fetched_at DESC
                """,
                (query, cutoff),
            ) as cur:
                rows = await cur.fetchall()
        return [dict(r) for r in rows]
