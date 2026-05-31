"""
SQLite-backed job cache (Enhancement 3).

Cache key = SHA256(url). Entries are considered fresh for ttl_hours after fetching.
Uses aiosqlite for non-blocking I/O from async contexts.
"""

import hashlib
import json
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
            # Schema migration: add new columns if they don't exist yet
            for col_ddl in (
                "ALTER TABLE jobs ADD COLUMN status          TEXT DEFAULT 'new'",
                "ALTER TABLE jobs ADD COLUMN fit_score       REAL",
                "ALTER TABLE jobs ADD COLUMN fit_reason      TEXT",
                "ALTER TABLE jobs ADD COLUMN notes           TEXT",
                "ALTER TABLE jobs ADD COLUMN tailored_cv     TEXT",
                "ALTER TABLE jobs ADD COLUMN matched_keywords TEXT",
                "ALTER TABLE jobs ADD COLUMN flagged_senior  INTEGER DEFAULT 0",
                "ALTER TABLE jobs ADD COLUMN remote_friendly INTEGER DEFAULT 0",
                "ALTER TABLE jobs ADD COLUMN region_open     INTEGER DEFAULT 0",
                "ALTER TABLE jobs ADD COLUMN quality_score   REAL",
                "ALTER TABLE jobs ADD COLUMN rejection_reason TEXT",
            ):
                try:
                    await db.execute(col_ddl)
                except Exception:
                    pass  # column already exists
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
                     description, source, fetched_at, raw_html, query,
                     flagged_senior, remote_friendly, region_open,
                     quality_score, rejection_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url_hash) DO UPDATE SET
                    title            = excluded.title,
                    company          = excluded.company,
                    location         = excluded.location,
                    description      = excluded.description,
                    source           = excluded.source,
                    fetched_at       = excluded.fetched_at,
                    raw_html         = excluded.raw_html,
                    query            = excluded.query,
                    flagged_senior   = excluded.flagged_senior,
                    remote_friendly  = excluded.remote_friendly,
                    region_open      = excluded.region_open,
                    quality_score    = excluded.quality_score,
                    rejection_reason = excluded.rejection_reason
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
                    int(bool(job_dict.get("flagged_senior", False))),
                    int(bool(job_dict.get("remote_friendly", False))),
                    int(bool(job_dict.get("region_open", False))),
                    job_dict.get("quality_score"),
                    job_dict.get("rejection_reason"),
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

    async def get_by_hash(self, url_hash: str) -> dict | None:
        """Return a cached job by its url_hash directly (no re-hashing)."""
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM jobs WHERE url_hash = ?", (url_hash,)
            ) as cur:
                row = await cur.fetchone()
        return dict(row) if row else None

    async def update_status(self, url: str, status: str) -> None:
        await self.init_db()
        h = self._url_hash(url)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE jobs SET status = ? WHERE url_hash = ?", (status, h)
            )
            await db.commit()

    async def update_status_by_hash(self, url_hash: str, status: str) -> None:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE jobs SET status = ? WHERE url_hash = ?", (status, url_hash)
            )
            await db.commit()

    async def update_fit(
        self,
        url: str,
        fit_score: float,
        fit_reason: str,
        matched_keywords=None,
    ) -> None:
        await self.init_db()
        h = self._url_hash(url)
        mk_json = json.dumps(matched_keywords) if matched_keywords is not None else None
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE jobs SET fit_score = ?, fit_reason = ?, matched_keywords = ? WHERE url_hash = ?",
                (fit_score, fit_reason, mk_json, h),
            )
            await db.commit()

    async def get_recent(self, limit: int = 30) -> list[dict]:
        """Return the most recently fetched remote/EMEA accepted jobs, with matched_keywords decoded."""
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT * FROM jobs
                   WHERE rejection_reason IS NULL
                     AND (remote_friendly = 1 OR region_open = 1)
                   ORDER BY fetched_at DESC LIMIT ?""",
                (limit,),
            ) as cur:
                rows = await cur.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("matched_keywords"):
                try:
                    d["matched_keywords"] = json.loads(d["matched_keywords"])
                except Exception:
                    d["matched_keywords"] = []
            result.append(d)
        return result

    async def get_by_status(self, status: str) -> list[dict]:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY fetched_at DESC",
                (status,),
            ) as cur:
                rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def update_notes(self, url: str, notes: str) -> None:
        await self.init_db()
        h = self._url_hash(url)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE jobs SET notes = ? WHERE url_hash = ?", (notes, h)
            )
            await db.commit()

    async def update_notes_by_hash(self, url_hash: str, notes: str) -> None:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE jobs SET notes = ? WHERE url_hash = ?", (notes, url_hash)
            )
            await db.commit()
