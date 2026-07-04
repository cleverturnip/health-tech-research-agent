"""Generate the value for the `HTRA_PASSWORD_HASH` secret.

Run:  python -m health_tech_research_agent.webapp.hash_password
It prompts for the app password twice (no echo) and prints the encoded PBKDF2 hash to paste into the Render
secret. The plaintext is never stored or transmitted.
"""

from __future__ import annotations

import getpass

from .security import hash_password


def main() -> None:
    pw = getpass.getpass("App password: ")
    if not pw:
        raise SystemExit("Empty password — aborted.")
    if pw != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords do not match — aborted.")
    print(hash_password(pw))


if __name__ == "__main__":
    main()
