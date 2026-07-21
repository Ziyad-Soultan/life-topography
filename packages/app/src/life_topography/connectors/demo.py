"""Deterministic synthetic MBOX for zero-risk product evaluation."""

from __future__ import annotations

import mailbox
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path

OWNER_EMAIL = "alex@home.example"

_CONTACTS = (
    ("Maya Chen", "maya@northstar.studio", "Product direction"),
    ("Jonas Reed", "jonas@northstar.studio", "Quarterly planning"),
    ("Priya Nair", "priya@fathom.works", "Invoice review"),
    ("Theo Martin", "theo@civic-lab.org", "Volunteer roster"),
    ("Lin Park", "lin@gmail.com", "Trail weekend"),
    ("Sam Rivera", "sam@proton.me", "Home server"),
)


def create_demo_mbox(path: Path) -> Path:
    """Write a repeatable fictional history that exercises the real connector."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    box = mailbox.mbox(path, create=True)
    start = datetime(2024, 1, 12, 14, 0, tzinfo=UTC)
    try:
        for index in range(30):
            name, address, subject = _CONTACTS[index % len(_CONTACTS)]
            outgoing = index % 3 == 1
            message = EmailMessage()
            if outgoing:
                message["From"] = f"Alex Morgan <{OWNER_EMAIL}>"
                message["To"] = f"{name} <{address}>"
            else:
                message["From"] = f"{name} <{address}>"
                message["To"] = f"Alex Morgan <{OWNER_EMAIL}>"
            message["Subject"] = subject if index < len(_CONTACTS) else f"Re: {subject}"
            message["Date"] = format_datetime(start + timedelta(days=index * 19))
            message["Message-ID"] = f"<demo-{index + 1:03d}@life-topography.example>"
            message.set_content(
                "Synthetic demo content. The connector intentionally discards this body."
            )
            box.add(message)
        box.flush()
    finally:
        box.close()
    return path
