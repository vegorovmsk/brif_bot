"""Сценарные тесты: полные диалоги через ConversationEngine на реальной SQLite (ТЗ, 14.1)."""

from datetime import timedelta

from sqlalchemy import func, select

from app.core.replies import TextReply, Toast
from app.storage.tables import AuditLogRow, BriefRow, ContactRow, SessionRow, UserRow
from tests.conftest import (
    DESCRIPTION,
    Chat,
    World,
    complete_brief,
    make_user,
    pass_to_contact_method,
)


async def count(world: World, table: type) -> int:
    async with world.factory() as db:
        return await db.scalar(select(func.count()).select_from(table)) or 0


# --- Полный проход ---


async def test_fr2_full_path_telegram_contact(world: World) -> None:
    chat = Chat(world.make_engine(), make_user())
    await complete_brief(chat)

    assert "Спасибо" in chat.said()
    assert chat.bot_messages <= 15  # AC этапа 1
    assert world.outbox.brief_ids == ["B-261026-001"]
    info = await world.make_engine()._ctx.briefs.get_finalize_info("B-261026-001")
    assert info is not None
    assert info.contact.name == "Иван"
    assert info.contact.username == "ivan_petrov"
    assert info.brief.deadline == "2–4 недели"
    assert info.brief.budget == "10–30 тыс. ₽"
    assert info.brief.materials == ["ТЗ или описание"]
    assert info.brief.generated_by == "template"
    assert DESCRIPTION in info.brief.summary


async def test_fr27_phone_path_accepts_only_own_contact(world: World) -> None:
    chat = Chat(world.make_engine(), make_user())
    await pass_to_contact_method(chat)
    await chat.press("Оставить телефон")
    assert any(isinstance(r, TextReply) and r.request_contact for r in chat.last)

    await chat.contact("+7 999 111-22-33", own=False)
    assert "свой номер" in chat.said()
    await chat.text("89991112233")
    assert "свой номер" in chat.said()
    await chat.contact("12345", own=True)
    assert "не получилось распознать" in chat.said().lower()

    await chat.contact("79991112233", own=True)
    assert "Проверьте" in chat.said()
    await chat.press("Всё верно")
    info = await world.make_engine()._ctx.briefs.get_finalize_info("B-261026-001")
    assert info is not None and info.contact.phone == "+79991112233"
    assert info.contact.preferred_method == "phone"


async def test_email_path_validates_format(world: World) -> None:
    chat = Chat(world.make_engine(), make_user(username=None))
    await pass_to_contact_method(chat)
    assert all("Telegram (@" not in b.label for b in chat.buttons())  # нет username
    await chat.press("Оставить email")
    await chat.text("не-почта")
    assert "email" in chat.said()
    await chat.text("Ivan@Example.com")
    await chat.press("Всё верно")
    info = await world.make_engine()._ctx.briefs.get_finalize_info("B-261026-001")
    assert info is not None and info.contact.email == "Ivan@example.com"


# --- Согласие ---


async def test_fr3_declined_consent_saves_nothing(world: World) -> None:
    chat = Chat(world.make_engine(), make_user())
    await chat.cmd("start")
    await chat.press("Не согласен")
    assert "@vegorovmsk" in chat.said()
    assert await count(world, UserRow) == 0
    assert await count(world, SessionRow) == 0
    assert await count(world, AuditLogRow) == 1  # только хеш, без ПДн


async def test_consent_is_not_asked_twice(world: World) -> None:
    chat = Chat(world.make_engine(), make_user())
    await complete_brief(chat)
    await chat.cmd("start")
    assert "Опишите задачу" in chat.said()


async def test_consent_asked_again_when_version_changes(world: World) -> None:
    chat = Chat(world.make_engine(), make_user())
    await chat.cmd("start")
    await chat.press("Согласен")
    await chat.cmd("cancel")
    await chat.press("Да")
    new_chat = Chat(world.make_engine(consent_version="v2"), make_user())
    await new_chat.cmd("start")
    assert "сохраняю ваши ответы" in new_chat.said()


# --- Кнопки и шаги ---


async def test_fr5_stale_button_does_not_change_state(world: World) -> None:
    chat = Chat(world.make_engine(), make_user())
    await chat.cmd("start")
    await chat.press("Согласен")
    await chat.text(DESCRIPTION)
    old_choice = [b for b in chat.buttons() if "ИИ" in b.label][0].payload
    await chat.payload(old_choice)
    assert "Вопрос 1 из 4" in chat.said()

    await chat.payload(old_choice)  # двойное нажатие
    assert [r for r in chat.last if isinstance(r, Toast)][0].text == "Этот шаг уже пройден"
    async with world.factory() as db:
        row = await db.scalar(select(SessionRow))
        assert row is not None and row.state == "clarify" and row.step_seq == 3


async def test_fr10_resume_after_restart(world: World) -> None:
    chat = Chat(world.make_engine(), make_user())
    await chat.cmd("start")
    await chat.press("Согласен")
    await chat.text(DESCRIPTION)
    await chat.press("ИИ-ассистент")
    await chat.press("Клиентам")

    restarted = Chat(world.make_engine(), make_user())  # новый движок на той же БД
    await restarted.cmd("start")
    await restarted.press("Продолжить")
    assert "Вопрос 2 из 4" in restarted.said()
    await restarted.press("Пропустить")
    assert "Вопрос 3 из 4" in restarted.said()


async def test_fr11_start_with_active_session_offers_resume_or_restart(world: World) -> None:
    chat = Chat(world.make_engine(), make_user())
    await chat.cmd("start")
    await chat.press("Согласен")
    await chat.text(DESCRIPTION)
    await chat.cmd("start")
    labels = [b.label for b in chat.buttons()]
    assert labels == ["Продолжить", "Начать заново"]
    await chat.press("Начать заново")
    assert "Опишите задачу" in chat.said()
    assert await count(world, SessionRow) == 1


async def test_fr9_free_text_answer_and_skip(world: World) -> None:
    chat = Chat(world.make_engine(), make_user())
    await chat.cmd("start")
    await chat.press("Согласен")
    await chat.text(DESCRIPTION)
    await chat.press("Парсинг")
    assert "Вопрос 1 из 4" in chat.said()
    await chat.text("Wildberries и Ozon")
    assert "Вопрос 2 из 4" in chat.said()
    await chat.press("Пропустить")
    assert "Вопрос 3 из 4" in chat.said()


async def test_materials_toggle_and_nothing_option(world: World) -> None:
    chat = Chat(world.make_engine(), make_user())
    await chat.cmd("start")
    await chat.press("Согласен")
    await chat.text(DESCRIPTION)
    await chat.press("Другое")
    for _ in range(3):
        await chat.press("Пропустить")
    await chat.press("Не срочно")
    await chat.press("Не знаю")
    await chat.press("ТЗ или описание")
    assert isinstance(chat.last[0], TextReply) and chat.last[0].edit_in_place
    await chat.press("Тексты или дизайн")
    assert sum(b.label.startswith("✅") for b in chat.buttons()) == 2
    await chat.press("Пока ничего")
    assert [b.label for b in chat.buttons() if b.label.startswith("✅")] == ["✅ Пока ничего"]
    await chat.press("ТЗ или описание")
    assert [b.label for b in chat.buttons() if b.label.startswith("✅")] == ["✅ ТЗ или описание"]


async def test_custom_deadline_text(world: World) -> None:
    chat = Chat(world.make_engine(), make_user())
    await chat.cmd("start")
    await chat.press("Согласен")
    await chat.text(DESCRIPTION)
    await chat.press("Другое")
    for _ in range(3):
        await chat.press("Пропустить")
    await chat.text("до пятницы")
    assert "Выберите" in chat.said()  # свободный текст до «Своя дата» не принимается
    await chat.press("Своя дата")
    await chat.text("К 15 ноября")
    assert "бюджет" in chat.said().lower()


# --- Ввод ---


async def test_describe_length_and_unsupported_input(world: World) -> None:
    chat = Chat(world.make_engine(), make_user())
    await chat.cmd("start")
    await chat.press("Согласен")
    await chat.text("бот")
    assert "подробнее" in chat.said()
    await chat.text("я" * 4001)
    assert "4000" in chat.said()
    await chat.unsupported("voice")
    assert "только текст" in chat.said()
    await chat.text(DESCRIPTION)
    assert "К чему ближе" in chat.said()
    await chat.text("просто текст")
    assert "кнопкой" in chat.said()


async def test_text_without_session_hints_start(world: World) -> None:
    chat = Chat(world.make_engine(), make_user())
    await chat.text("привет")
    assert "/start" in chat.said()


# --- Команды ---


async def test_cancel_new_and_delete_my_data(world: World) -> None:
    chat = Chat(world.make_engine(), make_user())
    await chat.cmd("cancel")
    assert "нечего отменять" in chat.said().lower()

    await chat.cmd("start")
    await chat.press("Согласен")
    await chat.cmd("cancel")
    await chat.press("Нет")
    assert await count(world, SessionRow) == 1
    await chat.cmd("cancel")
    await chat.press("Да")
    assert await count(world, SessionRow) == 0

    await chat.cmd("new")
    assert "Опишите задачу" in chat.said()
    await chat.cmd("new")
    await chat.press("Да")
    assert "Опишите задачу" in chat.said() and await count(world, SessionRow) == 1

    await chat.cmd("delete_my_data")
    await chat.press("Да")
    assert "удалены" in chat.said()
    for table in (UserRow, SessionRow, ContactRow, BriefRow):
        assert await count(world, table) == 0
    assert await count(world, AuditLogRow) == 2  # consent + data_deleted, без ПДн


async def test_delete_my_data_removes_confirmed_brief(world: World) -> None:
    chat = Chat(world.make_engine(), make_user())
    await complete_brief(chat)
    assert await count(world, BriefRow) == 1 and await count(world, ContactRow) == 1
    await chat.cmd("delete_my_data")
    await chat.press("Да")
    assert await count(world, BriefRow) == 0 and await count(world, ContactRow) == 0


async def test_help_privacy_and_unknown_commands(world: World) -> None:
    chat = Chat(world.make_engine(privacy_policy_url="https://example.com/p"), make_user())
    await chat.cmd("help")
    assert "/start" in chat.said()
    await chat.cmd("privacy")
    assert "https://example.com/p" in chat.said()
    await chat.cmd("stats")  # FR-37: владельческая команда для чужого — как неизвестная
    assert "Не знаю такой команды" in chat.said()


# --- Источник, лимиты, правки ---


async def test_fr12_source_from_deep_link(world: World) -> None:
    chat = Chat(world.make_engine(), make_user())
    await chat.cmd("start", "youdo_15342164")
    await chat.press("Согласен")
    async with world.factory() as db:
        row = await db.scalar(select(SessionRow))
        assert row is not None and row.source == "youdo_15342164"

    other = Chat(world.make_engine(), make_user(2002))
    await other.cmd("start", "bad source!<>")
    await other.press("Согласен")
    async with world.factory() as db:
        sources = (await db.scalars(select(SessionRow.source).order_by(SessionRow.id))).all()
    assert list(sources) == ["youdo_15342164", None]


async def test_fr13_daily_brief_limit(world: World) -> None:
    chat = Chat(world.make_engine(), make_user())
    for _ in range(3):
        await complete_brief(chat)
    await chat.cmd("start")
    assert "лимит брифов" in chat.said()
    assert world.outbox.brief_ids == ["B-261026-001", "B-261026-002", "B-261026-003"]

    world.clock.current += timedelta(days=1)
    await chat.cmd("start")
    assert "Опишите задачу" in chat.said()


async def test_fr22_revisions_go_to_comments_and_are_limited(world: World) -> None:
    chat = Chat(world.make_engine(), make_user())
    await pass_to_contact_method(chat)
    await chat.press("Telegram (@")
    for number in range(1, 4):
        await chat.press("Исправить")
        assert "Напишите, что поправить" in chat.said()
        await chat.text(f"Поправка {number}")
        assert "Добавил вашу правку" in chat.said()
    assert all(b.label != "✏️ Исправить" for b in chat.buttons())
    assert "обсудим с Владимиром" in chat.said()
    await chat.press("Всё верно")
    info = await world.make_engine()._ctx.briefs.get_finalize_info("B-261026-001")
    assert info is not None
    assert info.brief.client_comments == ["Поправка 1", "Поправка 2", "Поправка 3"]


async def test_fr24_brief_has_no_contacts(world: World) -> None:
    chat = Chat(world.make_engine(), make_user())
    await chat.cmd("start")
    await chat.press("Согласен")
    await chat.text("Нужен бот, пишите мне на ivan@ya.ru или +7 999 123-45-67, @ivan_petrov")
    await chat.press("Другое")
    for _ in range(3):
        await chat.press("Пропустить")
    await chat.press("Не срочно")
    await chat.press("Не знаю")
    await chat.press("Готово")
    await chat.press("Иван")
    await chat.press("Telegram (@")
    await chat.press("Всё верно")
    info = await world.make_engine()._ctx.briefs.get_finalize_info("B-261026-001")
    assert info is not None
    text = info.brief.model_dump_json()
    assert "ivan@ya.ru" not in text and "123-45-67" not in text and "@ivan_petrov" not in text
    assert "ivan_petrov" not in info.brief.summary


async def test_fr13_second_brief_gets_next_number(world: World) -> None:
    first = Chat(world.make_engine(), make_user(1))
    second = Chat(world.make_engine(), make_user(2))
    await complete_brief(first)
    await complete_brief(second)
    assert world.outbox.brief_ids == ["B-261026-001", "B-261026-002"]
