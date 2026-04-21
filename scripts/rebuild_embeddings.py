from pathlib import Path
import sys

from sqlmodel import Session

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.db.init_db import create_db_and_tables
from app.db.session import engine
from app.services.embedding_service import EmbeddingService


if __name__ == "__main__":
    create_db_and_tables()
    settings = get_settings()

    with Session(engine) as session:
        result = EmbeddingService(settings=settings).rebuild_all_embeddings(session)

    print(
        f"embedding 重建完成 | model={result.model_name} | profile={result.profile_name} | "
        f"total={result.total_chunks} | updated={result.updated_chunks} | failed={result.failed_chunks}"
    )
