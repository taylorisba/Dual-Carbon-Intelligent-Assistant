from sqlalchemy import text
from sqlmodel import SQLModel

from app.db.session import engine


FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    content,
    keywords,
    section_path,
    tokenize = 'unicode61'
);
"""

INSERT_TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(chunk_id, content, keywords, section_path)
    VALUES (new.id, new.content, COALESCE(new.keywords, ''), COALESCE(new.section_path, ''));
END;
"""

UPDATE_TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    DELETE FROM chunks_fts WHERE chunk_id = old.id;
    INSERT INTO chunks_fts(chunk_id, content, keywords, section_path)
    VALUES (new.id, new.content, COALESCE(new.keywords, ''), COALESCE(new.section_path, ''));
END;
"""

DELETE_TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    DELETE FROM chunks_fts WHERE chunk_id = old.id;
END;
"""

INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_documents_source_url ON documents(source_url);",
    "CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash);",
    "CREATE INDEX IF NOT EXISTS idx_chunks_document_chunk_idx ON chunks(document_id, chunk_index);",
]



def create_db_and_tables() -> None:
    from app.models.db_models import Chunk, Document, KnowledgeSource, QALog, SyncJob  # noqa: F401

    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text(FTS_SQL))
        conn.execute(text(INSERT_TRIGGER_SQL))
        conn.execute(text(UPDATE_TRIGGER_SQL))
        conn.execute(text(DELETE_TRIGGER_SQL))
        for statement in INDEX_SQL:
            conn.execute(text(statement))
