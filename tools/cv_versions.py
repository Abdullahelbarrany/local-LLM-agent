"""
CV version tracker (Enhancement 5).

Stores tailored CV versions as .tex files under cv_versions/ with a SQLite index.
Status lifecycle: draft → submitted → interviewing → rejected / offer
"""

import os
import re
from datetime import date

import aiosqlite

_DB_PATH      = os.getenv("CV_TRACKER_DB",   "cv_tracker.db")
_VERSIONS_DIR = os.getenv("CV_VERSIONS_DIR", "cv_versions")

VALID_STATUSES = {"draft", "submitted", "interviewing", "rejected", "offer"}


class CVVersionTracker:
    def __init__(
        self,
        db_path: str      = _DB_PATH,
        versions_dir: str = _VERSIONS_DIR,
    ) -> None:
        self.db_path      = db_path
        self.versions_dir = versions_dir

    async def init_db(self) -> None:
        os.makedirs(self.versions_dir, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS versions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    company     TEXT    NOT NULL,
                    role        TEXT    NOT NULL,
                    date        TEXT    NOT NULL,
                    file_path   TEXT    NOT NULL,
                    match_score REAL    NOT NULL DEFAULT 0.0,
                    status      TEXT    NOT NULL DEFAULT 'draft'
                )
            """)
            await db.commit()

    @staticmethod
    def _safe_slug(text: str) -> str:
        """Convert text to a safe, compact filename fragment (max 30 chars)."""
        return re.sub(r"[^\w]", "_", text.lower().strip())[:30].strip("_")

    async def save_version(
        self,
        company: str,
        role: str,
        tex_content: str,
        match_score: float = 0.0,
    ) -> int:
        """Write tex_content to disk and record it in the index. Returns new ID."""
        await self.init_db()
        today     = date.today().strftime("%Y-%m-%d")
        filename  = f"cv_{self._safe_slug(company)}_{self._safe_slug(role)}_{today}.tex"
        file_path = os.path.join(self.versions_dir, filename)
        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write(tex_content)
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """
                INSERT INTO versions (company, role, date, file_path, match_score, status)
                VALUES (?, ?, ?, ?, ?, 'draft')
                """,
                (company, role, today, file_path, float(match_score)),
            )
            await db.commit()
            return cur.lastrowid  # type: ignore[return-value]

    async def list_versions(self) -> list[dict]:
        """Return all versions ordered by date descending."""
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM versions ORDER BY date DESC, id DESC"
            ) as cur:
                rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def update_status(self, version_id: int, status: str) -> None:
        """Update the application status for a CV version."""
        if status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status {status!r}. Choose from: {sorted(VALID_STATUSES)}"
            )
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE versions SET status = ? WHERE id = ?",
                (status, version_id),
            )
            await db.commit()

    async def get_version(self, version_id: int) -> dict | None:
        """Return a single version by ID, or None if not found."""
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM versions WHERE id = ?", (version_id,)
            ) as cur:
                row = await cur.fetchone()
        return dict(row) if row else None
