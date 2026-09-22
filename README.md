# Hosts Editor for Omarchy

Add, block and toggle `/etc/hosts` entries from a menu, without opening a root editor. A port
of [PowerToys Hosts File Editor](https://learn.microsoft.com/windows/powertoys/hosts-file-editor)
to [Omarchy](https://omarchy.org).

*[Leia em português](README.pt-BR.md)*

```bash
omarchy-hosts                            # the menu: everything, one click to toggle
omarchy-hosts add 192.168.15.20 dev.local api.dev.local
omarchy-hosts block ads.example.com      # point it at 0.0.0.0
omarchy-hosts toggle dev.local           # off for now, still in the file
```

## What makes it safe to use on /etc/hosts

- **Your file comes back the way you left it.** Every line you did not touch is written back
  byte for byte — the distribution's header, your comments, blank lines, even the double tab
  someone lined `::1` up with. Only the lines you actually changed are re-spelled.
- **Turning an entry off keeps it.** A disabled entry is commented out, not deleted, so
  toggling it back on is one click and your note about why it exists survives.
- **Every save leaves a backup** next to the file (`/etc/hosts.bak-20260922-113000`), and
  `omarchy-hosts backups` lists them.
- **It refuses to write a hosts file with no loopback entry.** Deleting `127.0.0.1 localhost`
  breaks name resolution for the local machine in ways nobody connects back to a hosts edit an
  hour later, so that particular mistake is not available.
- **IPs and hostnames are validated** before anything is written, and a name that already
  points somewhere else is refused rather than silently shadowed.

## ⚠️ .local names will not resolve, and that is not this tool's fault

Arch — and so Omarchy — ships `/etc/nsswitch.conf` with `mdns_minimal [NOTFOUND=return]`
*before* `files`. Anything ending in `.local` is answered over mDNS and never reaches
`/etc/hosts`: the entry is there, it looks right, and the name still does not resolve.

`omarchy-hosts` says so the moment you type such a name. Use `.test`, `.internal`, or a
domain you actually own.

## Commands

```
omarchy-hosts                        the menu
omarchy-hosts list                   every entry, with the disabled ones marked
omarchy-hosts add <ip> <name…>       --note "why this exists"
omarchy-hosts block <domain…>        point them at 0.0.0.0
omarchy-hosts remove <name|ip>       take the line out
omarchy-hosts toggle <name|ip>       on ↔ off
omarchy-hosts enable|disable <name>  when you know which way you want it
omarchy-hosts edit                   your $EDITOR, but validated before it is installed
omarchy-hosts backups                the copies left by previous saves
```

Writing needs root: `sudo` when you are on a terminal, and the desktop's own password dialog
(`pkexec`) when you came from the menu. `$OMARCHY_HOSTS_ELEVATOR` overrides that for `doas`
or a passwordless setup.

## Install

### Arch / Omarchy

```bash
sudo pacman -U omarchy-hosts-editor-*-any.pkg.tar.zst   # from Releases
```

A keybinding, in `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + ALT + H", "Hosts file", "omarchy-hosts")
```

### Elsewhere

`pipx install git+https://github.com/andrebbruno/omarchy-hosts-editor`. Nothing here is
Hyprland-specific except the menu, which falls back to `gum` and then to a plain prompt.

## Development

```bash
python -m pytest tests -q     # 45 tests, none of them need root
```

`ohosts/hostsfile.py` parses into entries and *everything else*, and keeps the original text
of every line until something about it changes — that is what the byte-for-byte round-trip
test pins down. The whole suite runs against a temporary file with `$OMARCHY_HOSTS_ELEVATOR`
set to `env`, so the privileged path is exercised without ever being privileged.

## License

MIT © Andre Bruno
