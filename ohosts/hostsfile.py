"""Reading and writing /etc/hosts without disturbing the parts you did not touch.

The file is kept as a list of lines, each one either an entry or something we leave
exactly as we found it. That is the whole trick: a hosts file usually has comments,
blank lines and a header put there by the distribution, and a tool that rewrites it
from its own idea of the contents loses all of that on the first save.
"""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field

# A hostname label: letters, digits and hyphens, not starting or ending with one.
LABEL = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$")
BLOCK_IP = "0.0.0.0"


class HostsError(ValueError):
    """Something that would make the file wrong — reported, never written."""


@dataclass
class Entry:
    ip: str
    hostnames: list[str]
    comment: str = ""              # the text after # on the same line
    enabled: bool = True           # a disabled entry stays in the file, commented out
    indent: str = ""
    raw: str | None = None         # the line exactly as it was read, until it changes

    def render(self) -> str:
        """The original line while nothing has changed; our own spelling once it has.

        Hosts files are full of deliberate alignment — two tabs here, one there — and
        rewriting every line on every save turns a one-line edit into a diff of the
        whole file.
        """
        if self.raw is not None:
            return self.raw
        line = f"{self.indent}{self.ip}\t{' '.join(self.hostnames)}"
        if self.comment:
            line += f"\t# {self.comment}"
        return line if self.enabled else f"# {line.lstrip()}"

    def set_enabled(self, value: bool) -> bool:
        if self.enabled == value:
            return False
        self.enabled = value
        self.raw = None
        return True

    def matches(self, needle: str) -> bool:
        needle = needle.strip().lower()
        return needle == self.ip or needle in [h.lower() for h in self.hostnames]


@dataclass
class Other:
    """A comment, a blank line, or anything we did not recognise. Kept verbatim."""
    text: str

    def render(self) -> str:
        return self.text


@dataclass
class HostsFile:
    lines: list = field(default_factory=list)

    # ------------------------------------------------------------------ reading
    @classmethod
    def parse(cls, text: str) -> "HostsFile":
        lines: list = []
        for raw in text.splitlines():
            entry = _parse_entry(raw)
            lines.append(entry if entry else Other(raw))
        return cls(lines)

    @property
    def entries(self) -> list[Entry]:
        return [line for line in self.lines if isinstance(line, Entry)]

    def find(self, needle: str) -> list[Entry]:
        return [e for e in self.entries if e.matches(needle)]

    def render(self) -> str:
        return "\n".join(line.render() for line in self.lines) + "\n"

    # ------------------------------------------------------------------ editing
    def add(self, ip: str, hostnames: list[str], comment: str = "",
            enabled: bool = True) -> Entry:
        validate_ip(ip)
        names = [validate_hostname(h) for h in hostnames]
        if not names:
            raise HostsError("an entry needs at least one hostname")
        for name in names:
            for existing in self.entries:
                if existing.enabled and enabled and name.lower() in \
                        [h.lower() for h in existing.hostnames] and existing.ip != ip:
                    raise HostsError(
                        f"{name} already points at {existing.ip}; remove or disable "
                        f"that entry first")
        entry = Entry(ip=ip, hostnames=names, comment=comment, enabled=enabled)
        # Append after the last entry rather than at the very end, so a trailing
        # comment block in the file stays at the bottom where its author put it.
        last = max((i for i, line in enumerate(self.lines) if isinstance(line, Entry)),
                   default=len(self.lines) - 1)
        self.lines.insert(last + 1, entry)
        return entry

    def remove(self, needle: str) -> list[Entry]:
        gone = self.find(needle)
        self.lines = [line for line in self.lines if line not in gone]
        return gone

    def set_enabled(self, needle: str, enabled: bool) -> list[Entry]:
        return [e for e in self.find(needle) if e.set_enabled(enabled)]

    def toggle(self, needle: str) -> list[Entry]:
        found = self.find(needle)
        for entry in found:
            entry.set_enabled(not entry.enabled)
        return found


def _parse_entry(raw: str) -> Entry | None:
    """An entry, live or commented out. Anything else comes back as None."""
    stripped = raw.strip()
    if not stripped:
        return None

    enabled = True
    body = raw
    if stripped.startswith("#"):
        # A commented-out entry is one we disabled; a comment that is not an entry
        # (a header, a note) falls through to None below and is kept verbatim.
        enabled = False
        body = stripped.lstrip("#").strip()
        if not body:
            return None

    indent = "" if not enabled else raw[:len(raw) - len(raw.lstrip())]
    text, _, comment = body.partition("#")
    parts = text.split()
    if len(parts) < 2:
        return None
    try:
        ipaddress.ip_address(parts[0])
    except ValueError:
        return None
    if not all(LABEL.match(label) for name in parts[1:] for label in name.split(".")):
        return None
    return Entry(ip=parts[0], hostnames=parts[1:], comment=comment.strip(),
                 enabled=enabled, indent=indent, raw=raw)


# ---------------------------------------------------------------- validation

def validate_ip(text: str) -> str:
    try:
        ipaddress.ip_address(text.strip())
    except ValueError as e:
        raise HostsError(f"{text!r} is not an IP address") from e
    return text.strip()


def mdns_shadowed(hostname: str) -> bool:
    """True for a name the hosts file will lose a fight over.

    Arch (and so Omarchy) ships nsswitch with `mdns_minimal [NOTFOUND=return]` ahead
    of `files`, so anything ending in .local is answered by mDNS and never reaches
    /etc/hosts. The entry looks right, the name does not resolve, and nothing says
    why — which is worth a warning at the moment someone types it.
    """
    return hostname.strip().rstrip(".").lower().endswith(".local")


def validate_hostname(text: str) -> str:
    name = text.strip().rstrip(".")
    if not name:
        raise HostsError("an empty hostname")
    if len(name) > 253:
        raise HostsError(f"{text!r} is too long for a hostname")
    labels = name.split(".")
    if not all(LABEL.match(label) for label in labels):
        raise HostsError(f"{text!r} is not a hostname "
                         f"(letters, digits and hyphens, separated by dots)")
    return name
