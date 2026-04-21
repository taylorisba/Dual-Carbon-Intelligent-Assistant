from pathlib import Path
import sys

from sqlmodel import Session

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.init_db import create_db_and_tables
from app.db.session import engine
from app.services.ingestion_service import IngestionService


if __name__ == "__main__":
    create_db_and_tables()
    sample_dir = ROOT / "data" / "sample"
    files = sorted(sample_dir.glob("*.md"))

    with Session(engine) as session:
        service = IngestionService(session)
        for file_path in files:
            result = service.ingest_file(file_path)
            print(f"{file_path.name}: {result.message}")
