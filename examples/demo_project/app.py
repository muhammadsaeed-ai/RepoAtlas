"""Tiny application used by the RepoAtlas demonstration."""

from services import billing
from services.users import find_user


def main() -> None:
    user = find_user("demo")
    print(billing.invoice_for(user))


if __name__ == "__main__":
    main()
