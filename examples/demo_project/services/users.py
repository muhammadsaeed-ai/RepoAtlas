"""User lookup example."""

from . import billing


def find_user(user_id: str) -> dict[str, str]:
    billing.record_lookup(user_id)
    return {"id": user_id, "name": "Demo User"}
