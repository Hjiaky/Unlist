# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""In-process stand-ins for an IMAP and an SMTP server, so tests never touch the network.

``FakeIMAPServer`` speaks just enough IMAP4rev1 to the real ``imaplib`` client (its socket I/O
is replaced), so the tests see the exact command lines Unlist sends.
"""

import imaplib
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from unittest import mock


@dataclass
class Folder:
    uidvalidity: int
    messages: dict = field(default_factory=dict)  # uid -> raw bytes
    special_use: str = ""  # e.g. "\\All"


def _header_fields(raw, names):
    """Only the named header fields of a raw message (RFC 3501 HEADER.FIELDS), then a blank line."""
    head = re.split(rb"\r?\n\r?\n", raw, maxsplit=1)[0]
    fields, current = [], None
    for line in re.split(rb"\r?\n", head):
        if line[:1] in (b" ", b"\t") and current is not None:
            current.append(line)
            continue
        current = [line]
        fields.append(current)
    wanted = {name.lower().encode("ascii") for name in names}
    kept = [b"\r\n".join(lines) for lines in fields if lines[0].split(b":", 1)[0].strip().lower() in wanted]
    return b"".join(line + b"\r\n" for line in kept) + b"\r\n"


def _sequence(text, highest):
    """UIDs in an IMAP sequence set; ``*`` is the highest UID (so ``n:*`` with n > highest is highest)."""
    uids = set()
    for part in text.split(","):
        if ":" in part:
            low, high = (highest if value == "*" else int(value) for value in part.split(":"))
            low, high = min(low, high), max(low, high)
            uids.update(range(low, high + 1))
        else:
            uids.add(highest if part == "*" else int(part))
    return uids


class FakeIMAPServer:
    def __init__(self, folders, *, username="alex@example.org", password="app-password"):
        self.folders = folders
        self.username = username
        self.password = password
        self.commands = []  # every command line, without its tag
        self.seen = set()  # (folder, uid) that a fetch marked \Seen
        self.clients = []
        self.fail_fetch_after = None  # abort the connection after this many FETCH commands

    @contextmanager
    def installed(self):
        def factory(host="", port=993, *, ssl_context=None, timeout=None):
            return FakeIMAPClient(self, host, port, ssl_context=ssl_context, timeout=timeout)

        with mock.patch("imaplib.IMAP4_SSL", side_effect=factory) as patched:
            yield patched


class FakeIMAPClient(imaplib.IMAP4):
    def __init__(self, server, host, port, *, ssl_context=None, timeout=None):
        self.server = server
        self.ssl_context = ssl_context
        self._out = bytearray(b"* OK Fake IMAP ready\r\n")
        self._in = bytearray()
        self._selected = None
        self._fetches = 0
        server.clients.append(self)
        super().__init__(host, port, timeout)

    # imaplib's transport, replaced
    def open(self, host="", port=993, timeout=None):
        self.host, self.port = host, port

    def readline(self):
        end = self._out.find(b"\n")
        if end < 0:
            raise imaplib.IMAP4.abort("socket error: EOF")
        line = bytes(self._out[: end + 1])
        del self._out[: end + 1]
        return line

    def read(self, size):
        data = bytes(self._out[:size])
        del self._out[:size]
        return data

    def send(self, data):
        self._in += data
        while b"\r\n" in self._in:
            end = self._in.find(b"\r\n")
            line = bytes(self._in[:end]).decode("utf-8")
            del self._in[: end + 2]
            tag, _, command = line.partition(" ")
            self.server.commands.append(command)
            self._respond(tag, command)

    def shutdown(self):
        pass

    # the server side
    def _reply(self, text):
        self._out += text.encode("utf-8") if isinstance(text, str) else text

    def _respond(self, tag, command):
        verb, _, rest = command.partition(" ")
        verb = verb.upper()
        if verb == "CAPABILITY":
            self._reply(f"* CAPABILITY IMAP4rev1 SPECIAL-USE\r\n{tag} OK done\r\n")
        elif verb == "LOGIN":
            match = re.match(r'(\S+) "((?:[^"\\]|\\.)*)"$', rest)
            user, password = match[1], re.sub(r"\\(.)", r"\1", match[2])
            if (user, password) == (self.server.username, self.server.password):
                self._reply(f"{tag} OK logged in\r\n")
            else:
                self._reply(f"{tag} NO [AUTHENTICATIONFAILED] Invalid credentials (Failure)\r\n")
        elif verb == "LIST":
            lines = []
            for name, folder in self.server.folders.items():
                flags = " ".join(filter(None, ["\\HasNoChildren", folder.special_use]))
                lines.append(f'* LIST ({flags}) "/" "{name}"\r\n')
            self._reply("".join(lines) + f"{tag} OK done\r\n")
        elif verb in ("EXAMINE", "SELECT"):
            name = re.sub(r"\\(.)", r"\1", rest.strip('"'))
            folder = self.server.folders.get(name)
            if folder is None:
                self._reply(f"{tag} NO no such folder\r\n")
                return
            self._selected = name
            access = "READ-ONLY" if verb == "EXAMINE" else "READ-WRITE"
            self._reply(
                f"* {len(folder.messages)} EXISTS\r\n* OK [UIDVALIDITY {folder.uidvalidity}] ok\r\n"
                f"{tag} OK [{access}] done\r\n"
            )
        elif verb == "UID":
            self._uid(tag, rest)
        elif verb == "LOGOUT":
            self._reply(f"* BYE bye\r\n{tag} OK done\r\n")
        else:
            self._reply(f"{tag} BAD unknown command\r\n")

    def _uid(self, tag, rest):
        folder = self.server.folders[self._selected]
        ordered = sorted(folder.messages)
        highest = ordered[-1] if ordered else 0
        verb, _, args = rest.partition(" ")
        if verb.upper() == "SEARCH":
            wanted = _sequence(args.split()[1], highest)
            found = " ".join(str(uid) for uid in ordered if uid in wanted)
            self._reply(f"* SEARCH {found}\r\n{tag} OK done\r\n".replace("SEARCH \r", "SEARCH\r"))
            return
        sequence, _, items = args.partition(" ")
        self._fetches += 1
        if self.server.fail_fetch_after is not None and self._fetches > self.server.fail_fetch_after:
            self._out.clear()
            self._reply("* BYE connection lost\r\n")
            return
        wanted = _sequence(sequence, highest)
        header = re.search(r"BODY(\.PEEK)?\[HEADER\.FIELDS \(([^)]*)\)\]", items)
        full = re.search(r"BODY(\.PEEK)?\[\]", items)
        for number, uid in enumerate(ordered, start=1):
            if uid not in wanted:
                continue
            raw = folder.messages[uid]
            if header:
                section, data, peek = (
                    f"BODY[HEADER.FIELDS ({header[2]})]",
                    _header_fields(raw, header[2].split()),
                    header[1],
                )
            else:
                section, data, peek = "BODY[]", raw, full[1]
            if not peek:
                self.server.seen.add((self._selected, uid))
            self._reply(f"* {number} FETCH (UID {uid} {section} {{{len(data)}}}\r\n".encode() + data + b")\r\n")
        self._reply(f"{tag} OK done\r\n")


class FakeSMTP:
    """Stands in for ``smtplib.SMTP`` and ``smtplib.SMTP_SSL``; records what it is asked to do."""

    instances = []
    fail_login = False
    fail_send = None  # an exception instance to raise from send_message

    def __init__(self, host="", port=0, *, timeout=None, context=None, ssl=False):
        self.host, self.port, self.timeout, self.context, self.ssl = host, port, timeout, context, ssl
        self.calls = []
        self.sent = []
        FakeSMTP.instances.append(self)

    def starttls(self, context=None):
        self.calls.append("STARTTLS")
        self.starttls_context = context

    def login(self, user, password):
        import smtplib

        self.calls.append(f"LOGIN {user}")
        if FakeSMTP.fail_login:
            raise smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")
        self.password = password

    def send_message(self, message, from_addr=None, to_addrs=None):
        self.calls.append("SEND")
        if FakeSMTP.fail_send is not None:
            raise FakeSMTP.fail_send
        self.sent.append((message, from_addr, to_addrs))
        return {}

    def quit(self):
        self.calls.append("QUIT")

    def close(self):
        self.calls.append("CLOSE")

    @classmethod
    @contextmanager
    def installed(cls):
        cls.instances, cls.fail_login, cls.fail_send = [], False, None

        def ssl_factory(host="", port=0, **kwargs):
            return cls(host, port, ssl=True, **kwargs)

        def plain_factory(host="", port=0, **kwargs):
            return cls(host, port, ssl=False, **kwargs)

        with (
            mock.patch("smtplib.SMTP_SSL", side_effect=ssl_factory),
            mock.patch("smtplib.SMTP", side_effect=plain_factory),
        ):
            yield cls
