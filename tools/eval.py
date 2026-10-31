"""Eval качества analyze и synthesize на реальных заказах (ТЗ, 14.3, ADR-18).

Запуск: `uv run python tools/eval.py` — с реальной LLM по .env. ПЛАТНО: запускать только по просьбе
владельца. `--fake` прогоняет те же кейсы на FakeLLM: так проверяется сама механика eval, а
качество не оценивается. Отчёт — docs/eval/report_<дата>.md.
"""

# ruff: noqa: E402  (импорты app идут после добавления корня проекта в sys.path)
import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # запуск как скрипта: пакет app лежит в корне проекта

import yaml
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.guards import blocking, clean_draft, money_or_terms
from app.core.models import Analysis, Answer, BriefDraft, TaskType
from app.core.question_bank import QuestionBank, load_question_bank
from app.core.session import SessionData
from app.llm.brief_ai import LLMBriefAI
from app.llm.client import LLMClient, OpenAICompatibleLLM
from app.llm.costs import BudgetGuard, InMemoryCallLog, Prices
from app.llm.fake import FakeLLM, canned

CASES_PATH = ROOT / "tests" / "eval" / "cases.yaml"
REPORT_DIR = ROOT / "docs" / "eval"
MSK = timezone(timedelta(hours=3), "MSK")

MIN_TYPE_HITS = 12  # из 14 реальных кейсов (AC этапа 3)
REAL_CASES = 14
NOT_DEV_CASE = 15


class Case(BaseModel):
    """Один кейс eval-набора."""

    id: int
    title: str
    description: str
    budget: str
    deadline: str
    allowed_types: list[TaskType]
    expect_is_dev_task: bool | None = True
    answer_hint: str | None = None
    expect_flags: list[str] = Field(default_factory=list)  # для estimate, этап 5
    expect_recommendation: list[str] = Field(default_factory=list)  # для estimate, этап 5


class CaseFile(BaseModel):
    """Файл tests/eval/cases.yaml."""

    answer_hint_default: str
    cases: list[Case]


class EvalSettings(BaseSettings):
    """Только LLM-настройки из .env: BOT_TOKEN для eval не нужен."""

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    llm_provider: str = "yandex"
    llm_base_url: str = "https://llm.api.cloud.yandex.net/v1"
    llm_api_key: SecretStr | None = None
    llm_project: str | None = None
    llm_model: str | None = None
    llm_price_per_1k_input_rub: float | None = None
    llm_price_per_1k_output_rub: float | None = None
    llm_proxy: str | None = None


@dataclass
class CaseResult:
    """Итог одного кейса."""

    case: Case
    analysis: Analysis | None = None
    draft: BriefDraft | None = None
    answers: list[tuple[str, str]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    type_ok: bool = False
    money_violations: int = 0
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_rub: float = 0.0


class _AlwaysOn:
    """Переключатель LLM для eval: всегда включено."""

    async def is_enabled(self) -> bool:
        return True

    async def set_enabled(self, enabled: bool) -> None:
        return None


class _Clock:
    def now(self) -> datetime:
        return datetime.now(MSK)


def load_cases(path: Path = CASES_PATH) -> CaseFile:
    """Прочитать и проверить файл кейсов."""
    with path.open(encoding="utf-8") as file:
        return CaseFile.model_validate(yaml.safe_load(file))


def build_ai(
    settings: EvalSettings, bank: QuestionBank, *, fake: bool
) -> tuple[LLMBriefAI, InMemoryCallLog, LLMClient]:
    """BriefAI на реальном или фейковом клиенте; вызовы пишутся в память."""
    client: LLMClient
    if fake or settings.llm_provider == "fake":
        client = FakeLLM(fallback=canned)
    else:
        if settings.llm_api_key is None or not settings.llm_model:
            sys.exit("Для eval нужны LLM_API_KEY и LLM_MODEL в .env (или запустите с --fake).")
        client = OpenAICompatibleLLM(
            provider=settings.llm_provider,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value(),
            model=settings.llm_model,
            project=settings.llm_project,
            proxy=settings.llm_proxy,
        )
    prices = None
    if settings.llm_price_per_1k_input_rub is not None and (
        settings.llm_price_per_1k_output_rub is not None
    ):
        prices = Prices(settings.llm_price_per_1k_input_rub, settings.llm_price_per_1k_output_rub)
    clock = _Clock()
    calls = InMemoryCallLog()
    ai = LLMBriefAI(
        client,
        switch=_AlwaysOn(),
        budget=BudgetGuard(calls, 0, clock),  # бюджет 0 — без ограничения: eval запущен осознанно
        calls=calls,
        bank=bank,
        clock=clock,
        prices=prices,
    )
    return ai, calls, client


def _strings(draft: BriefDraft) -> list[str]:
    """Все тексты брифа, которые увидит заказчик."""
    out: list[str] = [draft.title, draft.summary, draft.business_goal]
    out += [draft.current_situation or ""]
    for items in (
        draft.functional_requirements,
        draft.scope_in,
        draft.scope_out,
        draft.integrations,
        draft.deliverables,
        draft.acceptance_criteria,
        draft.risks,
        draft.open_questions,
    ):
        out += items
    return out


async def run_case(
    ai: LLMBriefAI, calls: InMemoryCallLog, case: Case, hint_default: str
) -> CaseResult:
    """analyze -> ответы на вопросы -> synthesize и проверки критериев 14.3."""
    result = CaseResult(case)
    started = len(calls.calls)
    analysis = await ai.analyze(case.description, session_id=case.id)
    result.analysis = analysis
    if analysis is None:
        result.problems.append("analyze: LLM недоступна или ответ отклонён проверками")
    else:
        _check_analysis(result, analysis)
        if analysis.is_dev_task:
            await _synthesize(ai, result, analysis, hint_default)
    for call in calls.calls[started:]:
        result.calls += 1
        result.prompt_tokens += call.prompt_tokens
        result.completion_tokens += call.completion_tokens
        result.cost_rub += call.cost_rub
    return result


def _check_analysis(result: CaseResult, analysis: Analysis) -> None:
    case = result.case
    if case.expect_is_dev_task is not None and analysis.is_dev_task != case.expect_is_dev_task:
        result.problems.append(
            f"is_dev_task = {analysis.is_dev_task}, ожидалось {case.expect_is_dev_task}"
        )
    if case.expect_is_dev_task is False:
        result.type_ok = not analysis.is_dev_task
    else:
        result.type_ok = analysis.task_type in case.allowed_types
        if not result.type_ok:
            result.problems.append(
                f"тип {analysis.task_type.value}, допустимы: "
                + ", ".join(t.value for t in case.allowed_types)
            )
    texts = [analysis.understanding]
    for question in analysis.questions:
        texts += [question.text, *question.options]
    for text in texts:
        found = money_or_terms(text)
        if found:
            result.money_violations += len(found)
            result.problems.append(f"суммы или сроки в тексте для заказчика: {text[:80]!r}")


async def _synthesize(
    ai: LLMBriefAI, result: CaseResult, analysis: Analysis, hint_default: str
) -> None:
    case = result.case
    hint = case.answer_hint or hint_default
    data = SessionData(
        description=case.description,
        task_type=analysis.task_type,
        questions=list(analysis.questions),
        deadline=case.deadline,
        budget=case.budget,
    )
    for question in analysis.questions:
        answer = question.options[0] if question.options else hint
        data.answers[question.id] = Answer(value=answer)
        result.answers.append((question.id, answer))
    draft = await ai.synthesize(data, session_id=case.id)
    result.draft = draft
    if draft is None:
        result.problems.append("synthesize: LLM недоступна или ответ отклонён проверками")
        return
    client_texts = [case.description, case.deadline, case.budget, *(a for _, a in result.answers)]
    _, violations = clean_draft(draft, client_texts)
    bad = blocking(violations)
    if bad:
        result.money_violations += len(bad)
        result.problems.append("суммы или сроки в брифе, которых не называл заказчик")


def verdict(results: list[CaseResult]) -> list[tuple[str, bool]]:
    """Критерии приёмки этапа 3 (ТЗ, 13.4): (описание, выполнен ли)."""
    real = [r for r in results if r.case.id <= REAL_CASES]
    hits = sum(r.type_ok for r in real)
    not_dev = next((r for r in results if r.case.id == NOT_DEV_CASE), None)
    violations = sum(r.money_violations for r in results)
    return [
        (
            f"Тип верный минимум в {MIN_TYPE_HITS} из {REAL_CASES} кейсов (сейчас {hits})",
            hits >= MIN_TYPE_HITS,
        ),
        (
            "Кейс 15 распознан как не про разработку",
            bool(not_dev and not_dev.analysis and not not_dev.analysis.is_dev_task),
        ),
        (
            f"Ни в одном кейсе нет сумм и сроков разработки (нарушений: {violations})",
            violations == 0,
        ),
    ]


def render_report(
    results: list[CaseResult], *, provider: str, model: str, priced: bool, fake: bool
) -> str:
    """Отчёт Markdown: итог, таблица, подробности по кейсам."""
    now = datetime.now(MSK)
    briefs = [r for r in results if r.draft is not None]
    total_cost = sum(r.cost_rub for r in results)
    lines = [
        f"# Eval {now:%Y-%m-%d %H:%M}",
        "",
        f"Провайдер: `{provider}`, модель: `{model}`.",
        "",
        "## Итог",
        "",
    ]
    if fake:
        lines += ["> Режим `--fake`: проверена механика eval, качество модели не оценивается.", ""]
    else:
        for text, ok in verdict(results):
            lines.append(f"- {'✅' if ok else '❌'} {text}")
    if not priced:
        lines.append("- ⚠️ Цены `LLM_PRICE_PER_1K_*` не заданы: стоимость посчитана как 0 ₽.")
    elif briefs:
        lines.append(
            f"- Средняя стоимость брифа: **{total_cost / len(briefs):.2f} ₽** "
            f"(всего {total_cost:.2f} ₽ на {len(briefs)} брифов)"
        )
    lines += [
        "",
        "## Таблица",
        "",
        "| # | Кейс | Тип | Тип верный | Вызовов | Токены вх/исх | ₽ | Проблемы |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        kind = r.analysis.task_type.value if r.analysis else "—"
        lines.append(
            f"| {r.case.id} | {r.case.title} | {kind} | {'да' if r.type_ok else 'нет'} | {r.calls} "
            f"| {r.prompt_tokens}/{r.completion_tokens} | {r.cost_rub:.2f} | {len(r.problems)} |"
        )
    lines += ["", "## Подробно", ""]
    for r in results:
        lines += _case_section(r)
    return "\n".join(lines) + "\n"


def _case_section(r: CaseResult) -> list[str]:
    lines = [f"### {r.case.id}. {r.case.title}", "", f"> {r.case.description}", ""]
    if r.analysis is not None:
        lines += [
            f"- is_dev_task: `{r.analysis.is_dev_task}`, тип: `{r.analysis.task_type.value}`",
            f"- Понимание: {r.analysis.understanding}",
        ]
        for question in r.analysis.questions:
            options = f" — варианты: {' / '.join(question.options)}" if question.options else ""
            lines.append(f"- Вопрос {question.id}: {question.text}{options}")
    if r.draft is not None:
        lines += [
            f"- Бриф: **{r.draft.title}** — {r.draft.summary}",
            "  - Требования: " + "; ".join(r.draft.functional_requirements),
            "  - Открытые вопросы: " + ("; ".join(r.draft.open_questions) or "—"),
        ]
    for problem in r.problems:
        lines.append(f"- ❌ {problem}")
    lines.append("")
    return lines


async def run(*, fake: bool, cases_path: Path = CASES_PATH) -> tuple[str, bool]:
    """Прогнать все кейсы; вернуть текст отчёта и признак «критерии выполнены»."""
    settings = EvalSettings()
    bank = load_question_bank(ROOT / "config" / "question_bank.yaml")
    case_file = load_cases(cases_path)
    ai, calls, client = build_ai(settings, bank, fake=fake)
    results = [
        await run_case(ai, calls, case, case_file.answer_hint_default) for case in case_file.cases
    ]
    priced = (
        settings.llm_price_per_1k_input_rub is not None
        and settings.llm_price_per_1k_output_rub is not None
    )
    report = render_report(
        results, provider=client.provider, model=client.model, priced=priced, fake=fake
    )
    return report, all(ok for _, ok in verdict(results))


def write_report(report: str, out_dir: Path) -> Path:
    """Записать отчёт docs/eval/report_<дата>.md."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"report_{datetime.now(MSK):%Y-%m-%d}.md"
    path.write_text(report, encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eval analyze и synthesize (платно, кроме --fake)")
    parser.add_argument("--fake", action="store_true", help="FakeLLM вместо реальной модели")
    parser.add_argument("--out", type=Path, default=REPORT_DIR, help="каталог для отчёта")
    args = parser.parse_args(argv)
    report, passed = asyncio.run(run(fake=args.fake))
    print(f"Отчёт: {write_report(report, args.out)}")
    if args.fake:
        return 0
    print("Критерии приёмки выполнены" if passed else "Критерии приёмки НЕ выполнены")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
