"""Small SQLite/FTS5 index store used by SuperSearch runtime data.

The store is deliberately stdlib-only so the runtime index does not depend on
the development machine or on a copied Python package tree.
"""

import hashlib
import os
import sqlite3
import threading


class IndexStore:
    def __init__(self, db_path):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self):
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    scan_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    title_clean TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    original_path TEXT,
                    absolute_original_path TEXT,
                    domain TEXT,
                    doc_type TEXT,
                    language TEXT,
                    year TEXT,
                    file_year INTEGER,
                    file_month INTEGER,
                    source_type TEXT,
                    ocr_quality_score REAL,
                    word_count INTEGER,
                    source_size INTEGER,
                    source_mtime_ns INTEGER,
                    source_sha256 TEXT,
                    content TEXT NOT NULL,
                    content_clean TEXT NOT NULL,
                    UNIQUE(scan_id, relative_path)
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                    title_clean,
                    content_clean,
                    content='documents',
                    content_rowid='rowid',
                    tokenize='unicode61 remove_diacritics 2'
                );
                CREATE INDEX IF NOT EXISTS idx_documents_domain ON documents(domain);
                CREATE INDEX IF NOT EXISTS idx_documents_doc_type ON documents(doc_type);
                CREATE INDEX IF NOT EXISTS idx_documents_language ON documents(language);
                CREATE INDEX IF NOT EXISTS idx_documents_year ON documents(year);
                CREATE INDEX IF NOT EXISTS idx_documents_source_path ON documents(absolute_original_path);
                """
            )
            try:
                connection.execute("ALTER TABLE documents ADD COLUMN source_sha256 TEXT")
            except sqlite3.OperationalError:
                pass

    @staticmethod
    def _document_id(entry):
        identity = f"{entry.get('scan_id', '')}\0{entry.get('path', '')}"
        return hashlib.sha256(identity.encode('utf-8', errors='ignore')).hexdigest()

    def replace_entries(self, entries):
        """Replace the complete logical index in one transaction."""
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM documents_fts")
            connection.execute("DELETE FROM documents")
            for entry in entries:
                values = (
                    self._document_id(entry), entry.get('scan_id') or 'legacy',
                    entry.get('title') or '', entry.get('title_clean') or '',
                    entry.get('path') or '', entry.get('original_path') or '',
                    entry.get('absolute_original_path') or '', entry.get('domain') or '',
                    entry.get('doc_type') or '', entry.get('language') or '',
                    str(entry.get('year') or 'N/A'), int(entry.get('file_year') or 0),
                    int(entry.get('file_month') or 0), entry.get('source_type') or '',
                    float(entry.get('ocr_quality_score') or 0), int(entry.get('wordCount') or 0),
                    entry.get('source_size'), entry.get('source_mtime_ns'),
                    entry.get('source_sha256'),
                    entry.get('content') or '', entry.get('content_clean') or '',
                )
                connection.execute(
                    """INSERT INTO documents (
                        document_id, scan_id, title, title_clean, relative_path,
                        original_path, absolute_original_path, domain, doc_type,
                        language, year, file_year, file_month, source_type,
                        ocr_quality_score, word_count, source_size, source_mtime_ns,
                        source_sha256, content, content_clean
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    values,
                )
            connection.execute("INSERT INTO documents_fts(documents_fts) VALUES ('rebuild')")

    def search_documents(self, query='', page=1, page_size=50, filters=None):
        query = (query or '').strip()
        page = max(1, int(page or 1))
        page_size = min(200, max(1, int(page_size or 50)))
        filters = filters or {}
        where = []
        params = []
        if query:
            where.append("documents_fts MATCH ?")
            params.append(query)
        for column, value in (("domain", filters.get('domain')), ("doc_type", filters.get('doc_type')), ("language", filters.get('language'))):
            if value:
                where.append(f"documents.{column} = ?")
                params.append(value)
        if filters.get('extension'):
            extension = str(filters['extension']).lower().lstrip('.')
            where.append("lower(documents.original_path) LIKE ?")
            params.append(f"%.{extension}")
        if filters.get('year'):
            where.append("documents.year = ?")
            params.append(str(filters['year']))
        predicate = f"WHERE {' AND '.join(where)}" if where else ''
        offset = (page - 1) * page_size
        from_clause = "documents JOIN documents_fts ON documents.rowid = documents_fts.rowid" if query else "documents"
        select_fields = "documents.document_id, documents.scan_id, documents.title, documents.title_clean, documents.relative_path, documents.original_path, documents.absolute_original_path, documents.domain, documents.doc_type, documents.language, documents.year, documents.file_year, documents.file_month, documents.source_type, documents.ocr_quality_score, documents.word_count, documents.source_size, documents.source_mtime_ns, documents.source_sha256"
        order_clause = "bm25(documents_fts, 5.0, 1.0), documents.title COLLATE NOCASE" if query else "documents.title COLLATE NOCASE"
        snippet_field = ", snippet(documents_fts, 1, '<mark>', '</mark>', '…', 18) AS snippet" if query else ""
        with self._lock, self._connect() as connection:
            try:
                total = connection.execute(f"SELECT COUNT(*) FROM {from_clause} {predicate}", params).fetchone()[0]
                rows = connection.execute(
                    f"SELECT {select_fields}{snippet_field} FROM {from_clause} {predicate} ORDER BY {order_clause} LIMIT ? OFFSET ?",
                    [*params, page_size, offset],
                ).fetchall()
            except sqlite3.OperationalError as exc:
                # Treat only FTS syntax errors as a literal phrase.  Do not
                # hide schema/IO failures behind a second query attempt.
                message = str(exc).lower()
                if not query or not any(token in message for token in ("fts", "match", "syntax", "parse")):
                    raise
                safe_query = f'"{query.replace(chr(34), "")}"'
                safe_params = [safe_query if value == query else value for value in params]
                total = connection.execute(f"SELECT COUNT(*) FROM {from_clause} {predicate}", safe_params).fetchone()[0]
                rows = connection.execute(
                    f"SELECT {select_fields}{snippet_field} FROM {from_clause} {predicate} ORDER BY {order_clause} LIMIT ? OFFSET ?",
                    [*safe_params, page_size, offset],
                ).fetchall()
        return {"total": total, "page": page, "page_size": page_size, "documents": [dict(row) for row in rows]}

    def get_document(self, document_id):
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT * FROM documents WHERE document_id = ?", (document_id,)).fetchone()
        return dict(row) if row else None

    def count_documents(self):
        with self._lock, self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0])

    def is_known_path(self, path):
        normalized = os.path.normcase(os.path.normpath(os.path.abspath(path)))
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM documents WHERE lower(absolute_original_path) = lower(?) OR lower(relative_path) = lower(?) LIMIT 1",
                (normalized, normalized.replace('\\', '/')),
            ).fetchone()
        return row is not None

    def vocabulary(self, limit=5000):
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT title_clean FROM documents ORDER BY rowid LIMIT ?", (int(limit),)
            ).fetchall()
        return {"titles": [row[0] for row in rows]}

    def stats(self):
        """Return lightweight counts used by the UI without loading document text."""
        with self._lock, self._connect() as connection:
            total = int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
            domains = connection.execute(
                "SELECT domain, COUNT(*) AS count FROM documents "
                "WHERE domain IS NOT NULL AND domain <> '' GROUP BY domain ORDER BY domain"
            ).fetchall()
            years = connection.execute(
                "SELECT year, COUNT(*) AS count FROM documents "
                "WHERE year IS NOT NULL AND year <> '' GROUP BY year ORDER BY year DESC"
            ).fetchall()
            paths = connection.execute(
                "SELECT original_path FROM documents WHERE original_path LIKE '%.%'"
            ).fetchall()
        extension_counts = {}
        for row in paths:
            extension = os.path.splitext(row[0] or "")[1].lstrip(".").upper()
            if extension:
                extension_counts[extension] = extension_counts.get(extension, 0) + 1
        return {
            "total": total,
            "domains": {row[0]: int(row[1]) for row in domains},
            "years": {str(row[0]): int(row[1]) for row in years},
            "extensions": extension_counts,
        }
