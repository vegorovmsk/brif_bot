"""Уведомления владельцу: текст по ТЗ 10.8 и InlineFinalizer — простая замена outbox (этап 1)."""

import html
from typing import Protocol

import structlog

from app.core.ports import BriefRepository, FinalizeInfo

log = structlog.get_logger()

_PLATFORM_TITLES = {"telegram": "Telegram", "vk": "VK", "max": "MAX"}
_METHOD_TITLES = {"telegram": "Telegram", "phone": "телефон", "email": "email"}
_SUMMARY_PREVIEW = 300


class OwnerNotifier(Protocol):
    """Канал уведомлений владельцу (в Telegram — адаптер с OWNER_CHAT_ID)."""

    async def send_html(self, text: str) -> None: ...


def _e(value: str | None) -> str:
    return html.escape(value or "—", quote=False)


def format_new_brief(info: FinalizeInfo) -> str:
    """HTML-уведомление о подтверждённом брифе. Оценка появится на этапе 5."""
    brief, contact = info.brief, info.contact
    platform = _PLATFORM_TITLES.get(info.platform, info.platform)
    method = _METHOD_TITLES.get(contact.preferred_method, contact.preferred_method)
    contacts = [f"@{contact.username}" if contact.username else None, contact.phone, contact.email]
    contact_line = ", ".join(_e(item) for item in contacts if item) or "—"
    summary = brief.summary[:_SUMMARY_PREVIEW]
    return (
        f"🆕 Бриф {_e(brief.brief_id)} · {platform} · источник: {_e(info.source)}\n"
        f"👤 {_e(contact.name)} ({contact_line}) · связь: {method}\n"
        f"📌 {_e(brief.title)}\n"
        f"Тип: {brief.task_type.value} · Срок: {_e(brief.deadline)} · Бюджет: {_e(brief.budget)}\n"
        f"Материалы: {_e(', '.join(brief.materials) or None)}\n\n"
        f"{_e(summary)}\n\n"
        f"Оценка: появится на этапе 5"
    )


class InlineFinalizer:
    """Порт Outbox без очереди: сразу шлёт уведомление; сбой не ломает сценарий заказчика."""

    def __init__(self, briefs: BriefRepository, notifier: OwnerNotifier) -> None:
        self._briefs = briefs
        self._notifier = notifier

    async def enqueue_finalize(self, brief_id: str) -> None:
        try:
            info = await self._briefs.get_finalize_info(brief_id)
            if info is None:
                log.error("finalize_info_missing", brief_id=brief_id)
                return
            await self._notifier.send_html(format_new_brief(info))
        except Exception:
            log.exception("owner_notification_failed", brief_id=brief_id)
