import re


def display_name_from_email(email: str) -> str:
    local = email.split("@", 1)[0]
    parts = [part for part in re.split(r"[._+\-]+", local) if part]
    name = " ".join(part.capitalize() for part in parts) or local
    return name[:200]
