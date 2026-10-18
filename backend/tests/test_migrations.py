"""迁移一致性测试：`alembic upgrade head` 后的 schema 必须与 ORM 模型一致（防漂移）。

用法（仓库根目录）：
    python backend/tests/test_migrations.py

退出码：0 = 全部通过；1 = 存在失败。
使用独立临时 SQLite，不触碰本地 data.db。
"""
import os
import sys
import tempfile
import traceback
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

_tmp = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(Path(_tmp.name) / 'mig.db').as_posix()}"

try:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect, text

    from app.config import settings  # noqa: E402
    from app.db.base import Base  # noqa: E402
    from app.db import models  # noqa: E402,F401
except Exception:
    traceback.print_exc()
    sys.exit(1)

PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"[PASS] {name}")
    else:
        FAILED += 1
        print(f"[FAIL] {name}  {detail}")


def main() -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")

    sync_url = settings.database_url.replace("+aiosqlite", "").replace("+asyncpg", "")
    engine = create_engine(sync_url)
    inspector = inspect(engine)

    with engine.connect() as conn:
        version = conn.execute(text("select version_num from alembic_version")).scalar_one()
    check("迁移停留在 head", version == "0004", f"version={version}")

    existing = {t for t in inspector.get_table_names() if t != "alembic_version"}
    expected = set(Base.metadata.tables.keys())
    check(
        "迁移后表集合与模型一致",
        existing == expected,
        f"missing={expected - existing} extra={existing - expected}",
    )

    for table in sorted(expected & existing):
        model_cols = {c.name for c in Base.metadata.tables[table].columns}
        db_cols = {c["name"] for c in inspector.get_columns(table)}
        check(
            f"表 {table} 列集合一致",
            model_cols == db_cols,
            f"missing={model_cols - db_cols} extra={db_cols - model_cols}",
        )

    engine.dispose()
    try:
        _tmp.cleanup()
    except Exception:
        pass
    print(f"\n结果：{PASSED} 通过 / {FAILED} 失败")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
