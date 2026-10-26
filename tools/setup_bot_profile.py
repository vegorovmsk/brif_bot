"""Применить профиль бота (имя, описание, «О боте») из config/bot_profile.yaml (этап 2).

    uv run python tools/setup_bot_profile.py --dry-run   # только показать тексты и лимиты
    uv run python tools/setup_bot_profile.py             # применить к боту из BOT_TOKEN

Токен берётся из окружения или .env. Перед применением скрипт показывает, к какому боту
он обратится, и просит подтверждение (или флаг --yes). Токен нигде не печатается.
"""

import argparse
import asyncio
import sys
from pathlib import Path

import yaml
from aiogram import Bot

ROOT = Path(__file__).resolve().parent.parent
PROFILE_PATH = ROOT / "config" / "bot_profile.yaml"
LIMITS = {"name": 64, "short_description": 120, "description": 512}


def load_profile(path: Path = PROFILE_PATH) -> dict[str, str]:
    """Прочитать профиль и проверить лимиты Telegram; при нарушении — ValueError."""
    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)
    profile: dict[str, str] = {}
    for key, limit in LIMITS.items():
        value = str(data[key]).strip()
        if not value or len(value) > limit:
            raise ValueError(f"{key}: длина {len(value)}, допустимо 1-{limit}")
        profile[key] = value
    return profile


async def apply(profile: dict[str, str], assume_yes: bool) -> int:
    """Показать, к какому боту идём, и после подтверждения применить профиль."""
    from app.config import load_settings

    bot = Bot(token=load_settings().bot_token.get_secret_value())
    try:
        me = await bot.get_me()
        print(f"Профиль будет применён к боту @{me.username} (id {me.id}).")
        if not assume_yes:
            answer = await asyncio.to_thread(input, "Продолжить? [y/N] ")
            if answer.strip().lower() != "y":
                print("Отменено.")
                return 1
        await bot.set_my_name(profile["name"])
        await bot.set_my_description(profile["description"])
        await bot.set_my_short_description(profile["short_description"])
        print("Готово. Аватар задайте через @BotFather: /setuserpic.")
        return 0
    finally:
        await bot.session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="только показать и проверить")
    parser.add_argument("--yes", action="store_true", help="не спрашивать подтверждение")
    args = parser.parse_args()

    try:
        profile = load_profile()
    except (OSError, KeyError, ValueError, yaml.YAMLError) as exc:
        print(f"Ошибка в config/bot_profile.yaml: {exc}")
        return 2
    for key, value in profile.items():
        print(f"{key} ({len(value)}/{LIMITS[key]}):\n  {value}\n")
    if args.dry_run:
        return 0
    sys.path.insert(0, str(ROOT))
    return asyncio.run(apply(profile, args.yes))


if __name__ == "__main__":
    sys.exit(main())
