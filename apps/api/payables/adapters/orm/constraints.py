from django.db import IntegrityError, models
from django.db.models import Q


def money_constraints(table: str, *amount_columns: str) -> list[models.CheckConstraint]:
    currency = models.CheckConstraint(
        condition=Q(currency__regex=r"^[A-Z]{3}$"), name=f"{table}_currency_iso"
    )
    amounts = [
        models.CheckConstraint(
            condition=Q(**{f"{column}__gte": 0}),
            name=f"{table}_{column}_not_negative",
        )
        for column in amount_columns
    ]
    return [currency, *amounts]


def violated_constraint(error: IntegrityError) -> str | None:
    diag = getattr(error.__cause__, "diag", None)
    return getattr(diag, "constraint_name", None)
