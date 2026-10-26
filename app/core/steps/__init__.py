"""Обработчики состояний диалога: по модулю на состояние, реестр STEPS."""

from app.core.states import State
from app.core.steps import (
    budget,
    choose_type,
    clarify,
    contact,
    deadline,
    describe,
    done,
    materials,
    review,
)
from app.core.steps.common import Step

STEPS: dict[State, Step] = {
    State.DESCRIBE: Step(describe.prompt, describe.handle),
    State.CHOOSE_TYPE: Step(choose_type.prompt, choose_type.handle),
    State.CLARIFY: Step(clarify.prompt, clarify.handle),
    State.DEADLINE: Step(deadline.prompt, deadline.handle),
    State.BUDGET: Step(budget.prompt, budget.handle),
    State.MATERIALS: Step(materials.prompt, materials.handle),
    State.CONTACT_NAME: Step(contact.name_prompt, contact.name_handle),
    State.CONTACT_METHOD: Step(contact.method_prompt, contact.method_handle),
    State.CONTACT_EMAIL: Step(contact.email_prompt, contact.email_handle),
    State.REVIEW: Step(review.review_prompt, review.review_handle),
    State.REVISING: Step(review.revising_prompt, review.revising_handle),
    State.DONE: Step(done.prompt, done.handle),
}
