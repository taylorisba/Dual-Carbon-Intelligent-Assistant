from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.init_db import create_db_and_tables


if __name__ == "__main__":
    create_db_and_tables()
    print("数据库与 FTS5 索引初始化完成。")
