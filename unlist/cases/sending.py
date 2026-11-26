# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""How an approved draft leaves: sent by Unlist (live mode) or handed over to the Subject.

Live mode is a later ticket. It registers a sender here:

    from unlist.cases import sending
    sending.live_senders.append(send_with_smtp)   # draft -> bool

A sender is called only for an approved email draft whose Subject's mailbox is in live mode. It
returns True if it sent the draft, False to leave it to the next sender or to hand it over. With
no sender registered, every approved draft is handed over: the Subject sends it from their own
mail app (an ``.eml`` download or a ``mailto:`` link), uses the web form, or posts the letter,
and then marks it sent.

Nothing here runs on its own: ``services.approve`` is the only caller of ``try_live_send``, and
it calls it only after the Operator approved the draft.
"""

from collections.abc import Callable
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, make_msgid
from urllib.parse import quote

from django.utils import timezone

live_senders: list[Callable[[object], bool]] = []


class NotApproved(Exception):
    """A draft that was not approved must never leave."""


def mailbox_for(draft):
    """The Subject's mailbox the draft is sent from (by its sender address), or None."""
    return draft.case.subject.mailboxes.filter(email__iexact=draft.sender).first()


def hands_over(draft) -> bool:
    """True when the Subject sends this draft: import-only mailbox, or a web-form or letter Organization."""
    from unlist.cases.models import Draft
    from unlist.subjects.models import Mailbox

    if draft.channel != Draft.Channel.EMAIL:
        return True
    mailbox = mailbox_for(draft)
    return mailbox is None or mailbox.mode != Mailbox.Mode.LIVE


def will_send(draft) -> bool:
    """Whether approving this draft would let Unlist send it (for the approve button's label)."""
    return bool(live_senders) and not hands_over(draft)


def try_live_send(draft) -> bool:
    """Offer an approved draft to the registered live senders. True if one of them sent it."""
    from unlist.cases.models import Draft

    if draft.status != Draft.Status.APPROVED or draft.approved_at is None:
        raise NotApproved("Only an approved draft can be sent.")
    if hands_over(draft):
        return False
    return any(sender(draft) for sender in list(live_senders))


def new_message_id(sender: str) -> str:
    """A fresh Message-ID on the sender's own domain, so replies can be matched (spec section 7)."""
    domain = sender.rpartition("@")[2] or "localhost"
    return make_msgid(domain=domain)


def build_message(draft) -> EmailMessage:
    """The draft as an RFC 5322 message, From the Subject's address, To the recipient."""
    message = EmailMessage()
    message["From"] = formataddr((draft.case.subject.name, draft.sender))
    message["To"] = draft.recipient
    message["Subject"] = draft.subject_line
    message["Date"] = format_datetime(draft.approved_at or timezone.now())
    if draft.message_id:
        message["Message-ID"] = draft.message_id
    message.set_content(draft.body)
    return message


def eml_bytes(draft) -> bytes:
    return bytes(build_message(draft))


def eml_filename(draft) -> str:
    return f"{draft.case.reference}-{draft.kind}.eml"


def mailto_link(draft) -> str:
    """A ``mailto:`` link with the recipient, subject line and body filled in."""
    body = draft.body.replace("\r\n", "\n").replace("\n", "\r\n")
    return f"mailto:{quote(draft.recipient, safe='@')}?subject={quote(draft.subject_line)}&body={quote(body)}"
