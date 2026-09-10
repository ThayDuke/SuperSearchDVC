"""Small SQLite/FTS5 index store used by SuperSearch runtime data.

The store is deliberately stdlib-only so the runtime index does not depend on
the development machine or on a copied Python package tree.
"""

import hashlib
import os
import re
import sqlite3
import threading
import unicodedata
from contextlib import contextmanager


INDEX_SEMANTICS_VERSION = "2"
LOW_INFORMATION_TOKENS = {
    "a", "and", "at", "cua", "for", "of", "the", "va", "ve", "voi",
    "cac", "cho", "la", "mot", "nhieu", "nhung", "tren", "trong",
}
TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*")


def normalize_search_text(value):
    """Normalize Vietnamese text identically for index queries and snippets."""
    if not value:
        return ""
    normalized = unicodedata.normalize("NFD", str(value))
    no_marks = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return no_marks.replace("đ", "d").replace("Đ", "D").lower()


def tokenize_search_text(value):
    return TOKEN_PATTERN.findall(normalize_search_text(value))


def _quote_fts_term(term):
    return '"' + str(term).replace('"', '""') + '"'


def _build_query_plan(query):
    ordered_tokens = tokenize_search_text(query)
    unique_tokens = list(dict.fromkeys(ordered_tokens))
    informative_tokens = [
        token for token in unique_tokens
        if token not in LOW_INFORMATION_TOKENS and len(token) > 1
    ]
    if not informative_tokens:
        informative_tokens = unique_tokens[:]
    phrase = " ".join(ordered_tokens)
    phrase_expression = _quote_fts_term(phrase) if phrase else ""
    strict_expression = " AND ".join(_quote_fts_term(token) for token in unique_tokens)
    relaxed_expression = " OR ".join(_quote_fts_term(token) for token in informative_tokens)
    near_expression = ""
    if len(unique_tokens) >= 2:
        near_expression = "NEAR(" + " ".join(_quote_fts_term(token) for token in unique_tokens) + ", 8)"
    return {
        "raw_query": str(query or "").strip(),
        "normalized_query": normalize_search_text(query),
        "ordered_tokens": ordered_tokens,
        "unique_tokens": unique_tokens,
        "display_tokens": unique_tokens,
        "informative_tokens": informative_tokens,
        "phrase_expression": phrase_expression,
        "title_phrase_expression": f"title_clean : {phrase_expression}" if phrase_expression else "",
        "near_expression": near_expression,
        "strict_expression": strict_expression,
        "relaxed_expression": relaxed_expression,
    }


def _normalize_with_offsets(value):
    normalized_chars = []
    source_offsets = []
    for source_index, char in enumerate(str(value or "")):
        decomposed = unicodedata.normalize("NFD", char)
        for decomposed_char in decomposed:
            if unicodedata.category(decomposed_char) == "Mn":
                continue
            mapped = decomposed_char.replace("đ", "d").replace("Đ", "D").lower()
            for output_char in mapped:
                normalized_chars.append(output_char)
                source_offsets.append(source_index)
    return "".join(normalized_chars), source_offsets


def build_plain_snippet(content, query_tokens, width=180):
    """Return an accent-preserving, non-HTML snippet around query tokens."""
    original = str(content or "")
    if not original:
        return ""
    normalized, offsets = _normalize_with_offsets(original)
    if not normalized or not offsets:
        return original[:width] + ("…" if len(original) > width else "")
    phrase = " ".join(query_tokens or [])
    match_start = normalized.find(phrase) if phrase else -1
    if match_start < 0:
        positions = [normalized.find(token) for token in (query_tokens or [])]
        positions = [position for position in positions if position >= 0]
        match_start = min(positions) if positions else 0
    context_before = max(20, width // 3)
    normalized_start = max(0, match_start - context_before)
    normalized_end = min(len(normalized), normalized_start + width)
    source_start = offsets[normalized_start]
    source_end = offsets[normalized_end - 1] + 1
    snippet = original[source_start:source_end].strip()
    if source_start > 0:
        snippet = "…" + snippet
    if source_end < len(original):
        snippet += "…"
    return snippet


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

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self):
        with self._lock, self._connection() as connection:
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
                CREATE TABLE IF NOT EXISTS index_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
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

                CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                  INSERT INTO documents_fts(rowid, title_clean, content_clean) VALUES (new.rowid, new.title_clean, new.content_clean);
                END;
                CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                  INSERT INTO documents_fts(documents_fts, rowid, title_clean, content_clean) VALUES('delete', old.rowid, old.title_clean, old.content_clean);
                END;
                CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
                  INSERT INTO documents_fts(documents_fts, rowid, title_clean, content_clean) VALUES('delete', old.rowid, old.title_clean, old.content_clean);
                  INSERT INTO documents_fts(rowid, title_clean, content_clean) VALUES (new.rowid, new.title_clean, new.content_clean);
                END;
                """
            )
            try:
                connection.execute("ALTER TABLE documents ADD COLUMN source_sha256 TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                doc_count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
                if doc_count > 0:
                    fts_count = connection.execute("SELECT COUNT(*) FROM documents_fts").fetchone()[0]
                    if fts_count == 0:
                        connection.execute("INSERT INTO documents_fts(documents_fts) VALUES ('rebuild')")
            except Exception:
                pass

    @staticmethod
    def _document_id(entry):
        identity = f"{entry.get('scan_id', '')}\0{entry.get('path', '')}"
        return hashlib.sha256(identity.encode('utf-8', errors='ignore')).hexdigest()

    def sync_entries(self, entries, scan_id=None):
        """Incrementally synchronize documents without wiping the whole database."""
        with self._lock, self._connection() as connection:
            target_scan_ids = set()
            if scan_id:
                target_scan_ids.add(scan_id)
            for entry in entries:
                sid = entry.get('scan_id') or 'legacy'
                target_scan_ids.add(sid)

            existing = {}
            for sid in target_scan_ids:
                rows = connection.execute(
                    "SELECT document_id, source_size, source_mtime_ns, source_sha256 FROM documents WHERE scan_id = ?",
                    (sid,)
                ).fetchall()
                for r in rows:
                    existing[r["document_id"]] = {
                        "source_size": r["source_size"],
                        "source_mtime_ns": r["source_mtime_ns"],
                        "source_sha256": r["source_sha256"],
                    }

            new_ids = set()
            for entry in entries:
                doc_id = self._document_id(entry)
                new_ids.add(doc_id)
                old_meta = existing.get(doc_id)

                is_new = old_meta is None
                is_changed = False
                if not is_new:
                    if (
                        old_meta.get("source_mtime_ns") != entry.get("source_mtime_ns")
                        or old_meta.get("source_size") != entry.get("source_size")
                        or (entry.get("source_sha256") and old_meta.get("source_sha256") != entry.get("source_sha256"))
                    ):
                        is_changed = True

                if is_new or is_changed:
                    values = (
                        doc_id, entry.get('scan_id') or 'legacy',
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
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(document_id) DO UPDATE SET
                            title = excluded.title,
                            title_clean = excluded.title_clean,
                            relative_path = excluded.relative_path,
                            original_path = excluded.original_path,
                            absolute_original_path = excluded.absolute_original_path,
                            domain = excluded.domain,
                            doc_type = excluded.doc_type,
                            language = excluded.language,
                            year = excluded.year,
                            file_year = excluded.file_year,
                            file_month = excluded.file_month,
                            source_type = excluded.source_type,
                            ocr_quality_score = excluded.ocr_quality_score,
                            word_count = excluded.word_count,
                            source_size = excluded.source_size,
                            source_mtime_ns = excluded.source_mtime_ns,
                            source_sha256 = excluded.source_sha256,
                            content = excluded.content,
                            content_clean = excluded.content_clean
                        """,
                        values,
                    )

            deleted_ids = [doc_id for doc_id in existing if doc_id not in new_ids]
            if deleted_ids:
                for chunk_start in range(0, len(deleted_ids), 500):
                    chunk = deleted_ids[chunk_start:chunk_start + 500]
                    placeholders = ",".join("?" for _ in chunk)
                    connection.execute(f"DELETE FROM documents WHERE document_id IN ({placeholders})", chunk)

            connection.execute(
                "INSERT INTO index_metadata(key, value) VALUES('semantics_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (INDEX_SEMANTICS_VERSION,),
            )

    def replace_entries(self, entries):
        """Replace the complete logical index in one transaction."""
        with self._lock, self._connection() as connection:
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
            connection.execute(
                "INSERT INTO index_metadata(key, value) VALUES('semantics_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (INDEX_SEMANTICS_VERSION,),
            )

    def search_documents(self, query='', page=1, page_size=50, filters=None):
        query = (query or '').strip()
        page = max(1, int(page or 1))
        page_size = min(200, max(1, int(page_size or 50)))
        filters = filters or {}
        plan = _build_query_plan(query)
        query_tokens = plan["display_tokens"]
        cap = 2000
        with self._lock, self._connection() as connection:
            semantics_row = connection.execute(
                "SELECT value FROM index_metadata WHERE key = 'semantics_version'"
            ).fetchone()
            total_documents = int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
            requires_reindex = bool(total_documents and (not semantics_row or semantics_row[0] != INDEX_SEMANTICS_VERSION))
            sql_filters, filter_params = self._build_sql_filters(filters)
            within_query = _build_query_plan(filters.get("within_query", ""))
            within_expression = within_query["strict_expression"] if within_query["unique_tokens"] else ""
            display_query_tokens = list(dict.fromkeys(query_tokens + within_query["display_tokens"]))
            if not query_tokens:
                rows = connection.execute(
                    "SELECT " + self._select_fields() + " FROM documents "
                    + ("WHERE " + " AND ".join(sql_filters) if sql_filters else "")
                    + " ORDER BY documents.title COLLATE NOCASE, documents.document_id LIMIT ? OFFSET ?",
                    [*filter_params, page_size, (page - 1) * page_size],
                ).fetchall()
                total_sql = "SELECT COUNT(*) FROM documents" + (
                    " WHERE " + " AND ".join(sql_filters) if sql_filters else ""
                )
                total = int(connection.execute(total_sql, filter_params).fetchone()[0])
                return {
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "query_tokens": display_query_tokens,
                    "truncated": False,
                    "requires_reindex": requires_reindex,
                    "documents": [dict(row) for row in rows],
                }

            ranking_specs = []
            if len(query_tokens) == 1:
                ranking_specs.append(("single", 1.0, plan["strict_expression"]))
            else:
                ranking_specs.extend([
                    ("title_phrase", 4.0, plan["title_phrase_expression"]),
                    ("phrase", 3.0, plan["phrase_expression"]),
                    ("near", 2.0, plan["near_expression"]),
                    ("strict", 1.5, plan["strict_expression"]),
                ])
            ranking_lists = []
            strict_rows = []
            truncated = False
            for name, weight, expression in ranking_specs:
                if not expression:
                    continue
                combined_expression = expression
                if within_expression:
                    combined_expression = f"({combined_expression}) AND ({within_expression})"
                rows = self._fetch_ranked_rows(
                    connection, combined_expression, sql_filters, filter_params, cap
                )
                if name == "strict" or name == "single":
                    strict_rows = rows
                ranking_lists.append((name, weight, rows))
                truncated = truncated or len(rows) >= cap

            if not strict_rows and len(query_tokens) > 1:
                relaxed_expression = plan["relaxed_expression"]
                if relaxed_expression:
                    if within_expression:
                        relaxed_expression = f"({relaxed_expression}) AND ({within_expression})"
                    rows = self._fetch_ranked_rows(
                        connection, relaxed_expression, sql_filters, filter_params, cap
                    )
                    ranking_lists.append(("relaxed", 1.0, rows))
                    truncated = truncated or len(rows) >= cap

            merged = {}
            for name, weight, rows in ranking_lists:
                for rank, row in enumerate(rows, 1):
                    document_id = row["document_id"]
                    item = merged.setdefault(document_id, {
                        "row": dict(row),
                        "rrf_score": 0.0,
                        "best_bm25": float(row["_bm25"]),
                        "tier": 0,
                    })
                    item["rrf_score"] += weight / (60.0 + rank)
                    item["best_bm25"] = min(item["best_bm25"], float(row["_bm25"]))
                    item["tier"] = max(item["tier"], {
                        "title_phrase": 5, "phrase": 4, "near": 3,
                        "strict": 2, "single": 2, "relaxed": 1,
                    }.get(name, 0))
            ordered = sorted(
                merged.values(),
                key=lambda item: (
                    -item["rrf_score"], -item["tier"], item["best_bm25"],
                    str(item["row"].get("title") or "").casefold(),
                    str(item["row"].get("document_id") or ""),
                ),
            )
            total = len(ordered)
            page_items = ordered[(page - 1) * page_size: page * page_size]
            page_ids = [item["row"]["document_id"] for item in page_items]
            content_by_id = self._fetch_content_rows(connection, page_ids)
            documents = []
            for item in page_items:
                row = item["row"]
                content = content_by_id.get(row["document_id"], {})
                row.pop("_bm25", None)
                row["snippet"] = build_plain_snippet(content.get("content", ""), display_query_tokens)
                documents.append(row)
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "query_tokens": display_query_tokens,
                "truncated": truncated,
                "requires_reindex": requires_reindex,
                "documents": documents,
            }

    @staticmethod
    def _select_fields():
        return ("documents.document_id, documents.scan_id, documents.title, documents.title_clean, "
                "documents.relative_path, documents.original_path, documents.absolute_original_path, "
                "documents.domain, documents.doc_type, documents.language, documents.year, "
                "documents.file_year, documents.file_month, documents.source_type, "
                "documents.ocr_quality_score, documents.word_count, documents.source_size, "
                "documents.source_mtime_ns, documents.source_sha256")

    @staticmethod
    def _build_sql_filters(filters):
        where = []
        params = []
        for column, value in (("domain", filters.get("domain")), ("doc_type", filters.get("doc_type")), ("language", filters.get("language"))):
            if value:
                where.append(f"documents.{column} = ?")
                params.append(value)
        if filters.get("extension"):
            extension = str(filters["extension"]).lower().lstrip(".")
            where.append("lower(documents.original_path) LIKE ?")
            params.append(f"%.{extension}")
        if filters.get("year"):
            where.append("documents.year = ?")
            params.append(str(filters["year"]))
        return where, params

    def _fetch_ranked_rows(self, connection, expression, sql_filters, filter_params, cap):
        predicates = ["documents_fts MATCH ?", *sql_filters]
        sql = (
            "SELECT " + self._select_fields() + ", bm25(documents_fts, 5.0, 1.0) AS _bm25 "
            "FROM documents JOIN documents_fts ON documents.rowid = documents_fts.rowid "
            "WHERE " + " AND ".join(predicates) +
            " ORDER BY _bm25, documents.title COLLATE NOCASE, documents.document_id LIMIT ?"
        )
        return connection.execute(sql, [expression, *filter_params, cap]).fetchall()

    @staticmethod
    def _fetch_content_rows(connection, document_ids):
        if not document_ids:
            return {}
        placeholders = ",".join("?" for _ in document_ids)
        rows = connection.execute(
            f"SELECT document_id, content FROM documents WHERE document_id IN ({placeholders})",
            document_ids,
        ).fetchall()
        return {row["document_id"]: dict(row) for row in rows}

    def get_document(self, document_id):
        with self._lock, self._connection() as connection:
            row = connection.execute("SELECT * FROM documents WHERE document_id = ?", (document_id,)).fetchone()
        return dict(row) if row else None

    def count_documents(self):
        with self._lock, self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0])

    def resolve_file_path(self, path):
        """Given a path, resolve to an existing absolute file on disk matching document records."""
        if not path:
            return None
        norm = os.path.normpath(str(path).strip())
        if os.path.exists(norm):
            return norm

        clean_name = os.path.basename(norm)
        norm_fwd = norm.replace(chr(92), '/')
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT absolute_original_path FROM documents WHERE "
                "absolute_original_path = ? OR original_path = ? OR relative_path = ? "
                "OR original_path = ? OR relative_path = ? LIMIT 1",
                (norm, norm, norm, norm_fwd, norm_fwd),
            ).fetchone()
            if row and row[0] and os.path.exists(row[0]):
                return row[0]
            rows = connection.execute(
                "SELECT absolute_original_path FROM documents WHERE title = ? OR original_path LIKE ? LIMIT 10",
                (clean_name, f"%{clean_name}"),
            ).fetchall()
            for r in rows:
                if r[0] and os.path.exists(r[0]):
                    return r[0]
        return norm if os.path.exists(norm) else None

    def is_known_path(self, path):
        resolved = self.resolve_file_path(path)
        return resolved is not None
    def vocabulary(self, limit=5000):
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT title_clean FROM documents ORDER BY rowid LIMIT ?", (int(limit),)
            ).fetchall()
        return {"titles": [row[0] for row in rows]}

    def stats(self):
        """Return lightweight counts used by the UI without loading document text."""
        with self._lock, self._connection() as connection:
            total = int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
            domains = connection.execute(
                "SELECT domain, COUNT(*) AS count FROM documents "
                "WHERE domain IS NOT NULL AND domain <> '' GROUP BY domain ORDER BY domain"
            ).fetchall()
            years = connection.execute(
                "SELECT year, COUNT(*) AS count FROM documents "
                "WHERE year IS NOT NULL AND year <> '' GROUP BY year ORDER BY year DESC"
            ).fetchall()
            semantics_row = connection.execute(
                "SELECT value FROM index_metadata WHERE key = 'semantics_version'"
            ).fetchone()
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
            "requires_reindex": bool(total and (not semantics_row or semantics_row[0] != INDEX_SEMANTICS_VERSION)),
        }
