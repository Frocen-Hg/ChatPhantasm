"""seed 专项测试：验证 seed_defaults 的建库与补强逻辑（使用临时库，不污染本地数据）

用法（仓库根目录）：
    python backend/tests/test_seed.py

退出码：0 = 全部通过；1 = 存在失败。
"""
import asyncio
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_tmp = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(Path(_tmp.name) / 'seed.db').as_posix()}"

try:
    from sqlalchemy import select  # noqa: E402

    from app.db.models import Character, ProviderConfig  # noqa: E402
    from app.db.session import SessionLocal, engine, init_db  # noqa: E402
    from app.seed import seed_defaults  # noqa: E402
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


async def run() -> None:
    await init_db()

    def _fresh() -> None:
        """seed 在独立会话提交，测试会话因 expire_on_commit=False 会缓存旧值，需强制刷新"""
        db.expire_all()

    # --- 场景 1：全新库 seed → 1 角色 + 1 provider，角色卡指向默认 provider ---
    async with SessionLocal() as db:
        await seed_defaults()
        _fresh()
        chars = (await db.execute(select(Character))).scalars().all()
        provs = (await db.execute(select(ProviderConfig))).scalars().all()
        check("全新库：seed 1 个角色 + 1 个 provider", len(chars) == 1 and len(provs) == 1, f"{len(chars)}/{len(provs)}")
        check("seed 出影子角色", len(chars) == 1 and chars[0].name == "影子", chars[0].name if chars else "-")
        check("seed 出 deepseek 默认 provider", len(provs) == 1 and provs[0].is_default and provs[0].name == "deepseek")
        check(
            "角色卡 ext.model.provider 指向默认 provider",
            len(chars) == 1 and len(provs) == 1 and chars[0].ext.get("model", {}).get("provider") == provs[0].id,
            f"ext={chars[0].ext}",
        )

        # --- 场景 2：幂等（重复 seed 不产生重复数据）---
        await seed_defaults()
        _fresh()
        chars = (await db.execute(select(Character))).scalars().all()
        provs = (await db.execute(select(ProviderConfig))).scalars().all()
        check("幂等：重复 seed 仍为 1 角色 + 1 provider", len(chars) == 1 and len(provs) == 1)

        # --- 场景 3：悬空引用修复 ---
        db.add(
            Character(
                name="坏引用",
                card_json=json.dumps({"name": "坏引用"}),
                ext_json=json.dumps({"model": {"provider": 999}}),
            )
        )
        await db.commit()
        await seed_defaults()
        _fresh()
        bad = (await db.execute(select(Character).where(Character.name == "坏引用"))).scalar_one()
        check(
            "悬空引用：provider 不存在则移除引用",
            "provider" not in bad.ext.get("model", {}),
            f"ext={bad.ext}",
        )

        # --- 场景 4：有 provider 但无默认 → 兜底设首个为默认 ---
        ds = (await db.execute(select(ProviderConfig).where(ProviderConfig.name == "deepseek"))).scalar_one()
        await db.delete(ds)
        db.add(
            ProviderConfig(
                name="ollama",
                type="ollama",
                base_url="http://localhost:11434",
                models_json="[]",
                is_default=False,
                api_key="existing-key",
            )
        )
        await db.commit()
        await seed_defaults()
        _fresh()
        provs = (await db.execute(select(ProviderConfig))).scalars().all()
        check("无默认兜底：首个 provider 设为默认", len(provs) == 1 and provs[0].is_default, f"{[(p.name, p.is_default) for p in provs]}")
        check(
            "key 不覆盖：非 openai_compat 不写 key",
            provs[0].api_key == "existing-key",
            f"api_key={provs[0].api_key}",
        )

        # --- 场景 5：openai_compat 且 key 为空 → 从 .env 补 key ---
        p = provs[0]
        p.type = "openai_compat"
        p.api_key = ""
        await db.commit()
        await seed_defaults()
        _fresh()
        p = (await db.execute(select(ProviderConfig))).scalar_one()
        check("key 空则补：openai_compat 补 .env key", bool(p.api_key), f"api_key={p.api_key!r}")

        # --- 场景 6：已有 key 不被覆盖 ---
        p.api_key = "user-set-key"
        await db.commit()
        await seed_defaults()
        _fresh()
        p = (await db.execute(select(ProviderConfig))).scalar_one()
        check("key 不覆盖：已有 key 保持不变", p.api_key == "user-set-key", f"api_key={p.api_key}")

    await engine.dispose()
    try:
        _tmp.cleanup()
    except Exception:
        pass
    print(f"\n结果：{PASSED} 通过 / {FAILED} 失败")
    sys.exit(1 if FAILED else 0)


def main() -> None:
    try:
        asyncio.run(run())
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()