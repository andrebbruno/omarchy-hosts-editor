"""omarchy-hosts — edit /etc/hosts without opening a root editor.

    omarchy-hosts                          the menu
    omarchy-hosts add 127.0.0.1 dev.local
    omarchy-hosts block ads.example.com
    omarchy-hosts toggle dev.local
"""
from __future__ import annotations

import argparse
import datetime
import os
import shutil
import subprocess
import sys

from . import __version__, menu, privileged
from .hostsfile import (BLOCK_IP, Entry, HostsError, HostsFile, mdns_shadowed,
                        validate_hostname, validate_ip)

HOSTS = "/etc/hosts"
ICONS = {"on": "", "off": "", "add": "", "remove": "",
         "block": "", "edit": "", "backup": ""}


def read(path: str = HOSTS) -> HostsFile:
    try:
        with open(path, encoding="utf-8") as f:
            return HostsFile.parse(f.read())
    except OSError as e:
        raise HostsError(f"cannot read {path}: {e}") from e


def write(hosts: HostsFile, path: str = HOSTS, backup: bool = True) -> None:
    """Install the new file, keeping a copy of the old one."""
    text = hosts.render()
    if not any(isinstance(line, Entry) and line.enabled and line.ip in ("127.0.0.1", "::1")
               for line in hosts.lines):
        # Losing the loopback entry breaks name resolution for the local machine in
        # ways that are hard to connect back to a hosts file edit an hour later.
        raise HostsError("refusing to write a hosts file with no enabled loopback entry "
                         "(127.0.0.1 or ::1)")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    privileged.install(text, target=path, backup_suffix=f".bak-{stamp}" if backup else "")


def show(hosts: HostsFile) -> int:
    entries = hosts.entries
    if not entries:
        print("No entries.")
        return 0
    width = max(len(e.ip) for e in entries)
    for e in entries:
        mark = " " if e.enabled else "#"
        comment = f"   # {e.comment}" if e.comment else ""
        print(f"{mark} {e.ip:<{width}}  {' '.join(e.hostnames)}{comment}")
    return 0


# ---------------------------------------------------------------- commands

def cmd_list(args) -> int:
    return show(read(args.file))


def cmd_add(args) -> int:
    if not args.a or not args.rest:
        print("Usage: omarchy-hosts add <ip> <hostname> [hostname…]", file=sys.stderr)
        return 2
    hosts = read(args.file)
    entry = hosts.add(validate_ip(args.a), [validate_hostname(h) for h in args.rest],
                      comment=args.note or "")
    write(hosts, args.file)
    print(f"Added {entry.ip}  {' '.join(entry.hostnames)}")
    warn_about_mdns([h for h in entry.hostnames if mdns_shadowed(h)])
    menu.notify("Hosts", f"{' '.join(entry.hostnames)} → {entry.ip}")
    return 0


def warn_about_mdns(names: list[str]) -> None:
    if not names:
        return
    print(f"\nNote: {', '.join(names)} ends in .local, which this system answers over"
          f" mDNS\nbefore it ever looks at /etc/hosts. The entry is saved, but the name"
          f" will not\nresolve. Use .test, .internal or a domain you own instead.",
          file=sys.stderr)
    menu.notify("Hosts", f"{names[0]} is a .local name — mDNS answers it, not /etc/hosts")


def cmd_block(args) -> int:
    """Point a domain at nowhere — the one-liner people keep a hosts file for."""
    names = [args.a, *args.rest] if args.a else []
    if not names:
        print("Usage: omarchy-hosts block <domain> [domain…]", file=sys.stderr)
        return 2
    hosts = read(args.file)
    added = []
    for name in names:
        clean = validate_hostname(name)
        if hosts.find(clean):
            hosts.set_enabled(clean, True)
        else:
            hosts.add(BLOCK_IP, [clean], comment="blocked")
        added.append(clean)
    write(hosts, args.file)
    print(f"Blocked {', '.join(added)}")
    warn_about_mdns([n for n in added if mdns_shadowed(n)])
    menu.notify("Hosts", f"Blocked {', '.join(added)}")
    return 0


def cmd_remove(args) -> int:
    if not args.a:
        print("Usage: omarchy-hosts remove <hostname|ip>", file=sys.stderr)
        return 2
    hosts = read(args.file)
    gone = hosts.remove(args.a)
    if not gone:
        print(f"omarchy-hosts: nothing matches {args.a!r}", file=sys.stderr)
        return 1
    write(hosts, args.file)
    print(f"Removed {len(gone)} entr{'y' if len(gone) == 1 else 'ies'}")
    return 0


def cmd_toggle(args) -> int:
    if not args.a:
        print("Usage: omarchy-hosts toggle <hostname|ip>", file=sys.stderr)
        return 2
    hosts = read(args.file)
    changed = hosts.toggle(args.a)
    if not changed:
        print(f"omarchy-hosts: nothing matches {args.a!r}", file=sys.stderr)
        return 1
    write(hosts, args.file)
    for entry in changed:
        print(f"{'Enabled' if entry.enabled else 'Disabled'} "
              f"{entry.ip}  {' '.join(entry.hostnames)}")
    menu.notify("Hosts", f"{' '.join(changed[0].hostnames)} is now "
                         f"{'on' if changed[0].enabled else 'off'}")
    return 0


def cmd_enable(args) -> int:
    return _set(args, True)


def cmd_disable(args) -> int:
    return _set(args, False)


def _set(args, enabled: bool) -> int:
    if not args.a:
        print(f"Usage: omarchy-hosts {'enable' if enabled else 'disable'} <hostname|ip>",
              file=sys.stderr)
        return 2
    hosts = read(args.file)
    changed = hosts.set_enabled(args.a, enabled)
    if not changed:
        print(f"omarchy-hosts: nothing to change for {args.a!r}", file=sys.stderr)
        return 1
    write(hosts, args.file)
    print(f"{'Enabled' if enabled else 'Disabled'} {len(changed)} entr"
          f"{'y' if len(changed) == 1 else 'ies'}")
    return 0


def cmd_edit(args) -> int:
    """Open the file in your editor, but only install it if it still parses."""
    editor = os.environ.get("EDITOR") or ("nvim" if shutil.which("nvim") else "nano")
    original = read(args.file)
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        scratch = os.path.join(d, "hosts")
        with open(scratch, "w", encoding="utf-8") as f:
            f.write(original.render())
        before = os.path.getmtime(scratch)
        subprocess.run([editor, scratch], check=False)
        if os.path.getmtime(scratch) == before:
            print("Unchanged.")
            return 0
        with open(scratch, encoding="utf-8") as f:
            edited = HostsFile.parse(f.read())
    write(edited, args.file)
    print(f"Saved {len(edited.entries)} entr"
          f"{'y' if len(edited.entries) == 1 else 'ies'}")
    return 0


def cmd_backups(args) -> int:
    directory = os.path.dirname(args.file) or "/"
    base = os.path.basename(args.file)
    found = sorted(n for n in os.listdir(directory) if n.startswith(base + ".bak-"))
    if not found:
        print("No backups yet.")
        return 1
    for name in found:
        print(os.path.join(directory, name))
    return 0


# ---------------------------------------------------------------- the menu

def cmd_menu(args) -> int:
    hosts = read(args.file)
    rows = [(ICONS["add"], "Add an entry", "An IP and the names that point at it"),
            (ICONS["block"], "Block a domain", f"Point it at {BLOCK_IP}")]
    for entry in hosts.entries:
        icon = ICONS["on"] if entry.enabled else ICONS["off"]
        state = "on" if entry.enabled else "off"
        rows.append((icon, " ".join(entry.hostnames), f"{entry.ip} · {state} · click to toggle"))
    pick = menu.select("Hosts file", rows, width=680)
    if not pick:
        return 1
    label = pick.split("\t")[0]

    if label == "Add an entry":
        ip = menu.ask("IP address", ) or ""
        if not ip:
            return 1
        names = menu.ask(f"Hostnames for {ip} (separated by spaces)") or ""
        if not names.strip():
            return 1
        args.a, args.rest = ip, names.split()
        return cmd_add(args)
    if label == "Block a domain":
        domain = menu.ask(f"Domain to point at {BLOCK_IP}")
        if not domain:
            return 1
        args.a, args.rest = domain, []
        return cmd_block(args)

    args.a = label.split()[0]
    return cmd_toggle(args)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="omarchy-hosts",
        description="Edit /etc/hosts without opening a root editor.",
        epilog="With no command, the Omarchy menu opens.")
    p.add_argument("command", nargs="?",
                   help="list, add, remove, block, toggle, enable, disable, edit, backups")
    p.add_argument("a", nargs="?", help="an IP or a hostname, depending on the command")
    p.add_argument("rest", nargs="*", help="more hostnames")
    p.add_argument("--note", help="a comment to keep with the entry")
    p.add_argument("--file", default=HOSTS, help=f"which file (default {HOSTS})")
    p.add_argument("-V", "--version", action="version", version=f"omarchy-hosts {__version__}")
    args = p.parse_args(argv)

    commands = {"list": cmd_list, "add": cmd_add, "remove": cmd_remove, "block": cmd_block,
                "toggle": cmd_toggle, "enable": cmd_enable, "disable": cmd_disable,
                "edit": cmd_edit, "backups": cmd_backups, "menu": cmd_menu}
    try:
        if args.command is None:
            return cmd_menu(args)
        if args.command not in commands:
            print(f"omarchy-hosts: unknown command {args.command!r}", file=sys.stderr)
            return 2
        return commands[args.command](args)
    except HostsError as e:
        print(f"omarchy-hosts: {e}", file=sys.stderr)
        menu.notify("Hosts", str(e))
        return 1
    except privileged.PrivilegeError as e:
        print(f"omarchy-hosts: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
