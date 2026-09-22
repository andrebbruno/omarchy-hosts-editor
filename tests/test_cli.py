import os

import pytest

from ohosts import cli
from ohosts.hostsfile import HostsError, HostsFile

SAMPLE = """\
# The distribution's header
127.0.0.1\tlocalhost
::1\t\tlocalhost ip6-localhost
192.168.15.20\tdev.local\t# the laptop
"""


@pytest.fixture
def hosts(tmp_path, monkeypatch):
    """A hosts file we own, so nothing here needs root."""
    path = tmp_path / "hosts"
    path.write_text(SAMPLE, encoding="utf-8")
    monkeypatch.setenv("OMARCHY_HOSTS_ELEVATOR", "env")     # a prefix that changes nothing
    monkeypatch.setattr(cli.menu, "notify", lambda *a, **k: None)
    return path


def text(path):
    return path.read_text(encoding="utf-8")


def run(path, *args):
    return cli.main([*args, "--file", str(path)])


def test_list(hosts, capsys):
    assert run(hosts, "list") == 0
    out = capsys.readouterr().out
    assert "dev.local" in out and "127.0.0.1" in out


def test_add(hosts):
    assert run(hosts, "add", "10.0.0.5", "nas", "nas.local") == 0
    assert "10.0.0.5\tnas nas.local" in text(hosts)
    assert "# The distribution's header" in text(hosts)


def test_add_refuses_a_name_that_already_points_elsewhere(hosts, capsys):
    assert run(hosts, "add", "10.0.0.9", "dev.local") == 1
    assert "already points at" in capsys.readouterr().err
    assert text(hosts) == SAMPLE


def test_add_refuses_a_bad_ip(hosts, capsys):
    assert run(hosts, "add", "999.1.1.1", "x.local") == 1
    assert text(hosts) == SAMPLE


def test_add_refuses_a_bad_hostname(hosts):
    assert run(hosts, "add", "10.0.0.5", "not_a_host") == 1
    assert text(hosts) == SAMPLE


def test_block_points_a_domain_at_nowhere(hosts):
    assert run(hosts, "block", "ads.example.com") == 0
    assert "0.0.0.0\tads.example.com\t# blocked" in text(hosts)


def test_blocking_something_already_there_turns_it_back_on(hosts):
    run(hosts, "block", "ads.example.com")
    run(hosts, "toggle", "ads.example.com")
    assert "# 0.0.0.0\tads.example.com" in text(hosts)
    run(hosts, "block", "ads.example.com")
    assert "\n0.0.0.0\tads.example.com" in text(hosts)


def test_toggle_off_and_on(hosts):
    assert run(hosts, "toggle", "dev.local") == 0
    assert "# 192.168.15.20\tdev.local" in text(hosts)
    assert run(hosts, "toggle", "dev.local") == 0
    assert "\n192.168.15.20\tdev.local" in text(hosts)


def test_toggle_something_absent(hosts, capsys):
    assert run(hosts, "toggle", "nothing.here") == 1
    assert "nothing matches" in capsys.readouterr().err


def test_remove(hosts):
    assert run(hosts, "remove", "dev.local") == 0
    assert "dev.local" not in text(hosts)
    assert "127.0.0.1" in text(hosts)


def test_the_loopback_entry_cannot_be_removed(hosts, capsys):
    """Losing it breaks name resolution in ways nobody connects back to this tool."""
    run(hosts, "remove", "::1")
    assert run(hosts, "remove", "127.0.0.1") == 1
    assert "loopback" in capsys.readouterr().err
    assert "127.0.0.1" in text(hosts)


def test_the_loopback_entry_cannot_be_disabled_away(hosts):
    run(hosts, "remove", "::1")
    assert run(hosts, "toggle", "127.0.0.1") == 1
    assert "\n127.0.0.1\tlocalhost" in text(hosts)


def test_disabling_ipv4_loopback_is_fine_while_ipv6_is_there(hosts):
    assert run(hosts, "toggle", "127.0.0.1") == 0


def test_a_backup_is_left_behind(hosts, tmp_path):
    run(hosts, "add", "10.0.0.5", "nas")
    backups = list(tmp_path.glob("hosts.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == SAMPLE


def test_backups_are_listed(hosts, capsys):
    run(hosts, "add", "10.0.0.5", "nas")
    assert run(hosts, "backups") == 0
    assert "hosts.bak-" in capsys.readouterr().out


def test_an_unknown_command_is_reported(hosts, capsys):
    assert run(hosts, "frobnicate") == 2


def test_a_missing_file_is_reported_not_raised(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("OMARCHY_HOSTS_ELEVATOR", "env")
    assert cli.main(["list", "--file", str(tmp_path / "nope")]) == 1
    assert "cannot read" in capsys.readouterr().err


def test_editing_keeps_every_untouched_line(hosts):
    """The save path is the same one the menu uses, so this covers both."""
    parsed = HostsFile.parse(text(hosts))
    parsed.toggle("dev.local")
    cli.write(parsed, str(hosts))
    saved = text(hosts)
    assert "# The distribution's header" in saved
    assert "::1\t\tlocalhost ip6-localhost" in saved          # the double tab survives


def test_a_dot_local_name_is_saved_but_flagged(hosts, capsys):
    """Arch resolves .local over mDNS before it reads /etc/hosts, so the entry works
    perfectly and the name still does not resolve. Saying so is the whole point."""
    assert run(hosts, "add", "10.0.0.7", "nas.local") == 0
    err = capsys.readouterr().err
    assert ".local" in err and "mDNS" in err
    assert "10.0.0.7\tnas.local" in text(hosts)


def test_an_ordinary_name_gets_no_warning(hosts, capsys):
    assert run(hosts, "add", "10.0.0.8", "dev.test") == 0
    assert "mDNS" not in capsys.readouterr().err


def test_blocking_a_dot_local_domain_is_flagged_too(hosts, capsys):
    assert run(hosts, "block", "printer.local") == 0
    assert "mDNS" in capsys.readouterr().err
