"""Проверка доступности внешних сервисов с сервера (ТЗ, ADR-16, этап 2).

Запуск без uv и без секретов, достаточно системного python3:

    python3 tools/check_connectivity.py

Для HTTPS-хостов проверяется TCP-соединение и TLS-рукопожатие, для SMTP — только TCP.
Код возврата 0 — всё доступно, 1 — есть недоступные сервисы.
"""

import socket
import ssl
import sys
import time
from dataclasses import dataclass

TIMEOUT_SECONDS = 5.0

# (хост, порт, TLS, зачем нужен, подсказка при сбое)
TARGETS = [
    ("api.telegram.org", 443, True, "Telegram Bot API", "задайте TELEGRAM_PROXY в .env"),
    ("llm.api.cloud.yandex.net", 443, True, "Yandex AI Studio (LLM)", "задайте LLM_PROXY в .env"),
    ("www.googleapis.com", 443, True, "Google Диск и таблицы", "нужен прокси или отключите Google"),
    ("cloud-api.yandex.net", 443, True, "Яндекс Диск", "проверьте сеть и DNS сервера"),
    ("smtp.yandex.ru", 465, False, "SMTP Яндекса (почта)", "проверьте, не закрыт ли порт 465"),
]


@dataclass(frozen=True)
class Result:
    """Итог проверки одного сервиса."""

    host: str
    port: int
    ok: bool
    millis: int
    error: str = ""


def check(host: str, port: int, tls: bool, timeout: float = TIMEOUT_SECONDS) -> Result:
    """Открыть соединение (и TLS-рукопожатие, если tls) и замерить время."""
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            if tls:
                context = ssl.create_default_context()
                with context.wrap_socket(sock, server_hostname=host):
                    pass
    except (OSError, ssl.SSLError) as exc:
        elapsed = int((time.monotonic() - started) * 1000)
        return Result(host, port, False, elapsed, f"{type(exc).__name__}: {exc}")
    return Result(host, port, True, int((time.monotonic() - started) * 1000))


def format_result(result: Result, purpose: str, hint: str) -> str:
    """Одна строка отчёта."""
    if result.ok:
        return f"OK    {result.host}:{result.port}  {result.millis} мс  {purpose}"
    return f"FAIL  {result.host}:{result.port}  {purpose}\n      {result.error}\n      -> {hint}"


def main() -> int:
    """Проверить все сервисы и напечатать отчёт."""
    failed = 0
    for host, port, tls, purpose, hint in TARGETS:
        result = check(host, port, tls)
        print(format_result(result, purpose, hint))
        failed += not result.ok
    print()
    print("Всё доступно." if not failed else f"Недоступно сервисов: {failed}.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
