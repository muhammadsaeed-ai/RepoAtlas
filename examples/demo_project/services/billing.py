"""Billing example."""

from .users import find_user


def record_lookup(user_id: str) -> None:
    _ = user_id


def invoice_for(user: dict[str, str]) -> str:
    return f"Invoice for {user['name']}"
