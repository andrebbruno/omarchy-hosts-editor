import pytest

from ohosts.hostsfile import Entry, HostsError, HostsFile, Other, validate_hostname, validate_ip

SAMPLE = """\
# Static table lookup for hostnames.
# See hosts(5) for details.

127.0.0.1\tlocalhost
::1\t\tlocalhost ip6-localhost
127.0.1.1\tomarchy-vm.localdomain omarchy-vm

# my project
192.168.15.20\tdev.local api.dev.local\t# the laptop
# 0.0.0.0\tads.example.com
"""


def parse(text=SAMPLE):
    return HostsFile.parse(text)


# ---------------------------------------------------------------- reading

def test_entries_are_found():
    hosts = parse()
    assert [e.ip for e in hosts.entries] == [
        "127.0.0.1", "::1", "127.0.1.1", "192.168.15.20", "0.0.0.0"]


def test_hostnames_are_split():
    assert parse().entries[1].hostnames == ["localhost", "ip6-localhost"]


def test_a_trailing_comment_is_kept_apart_from_the_names():
    entry = parse().find("dev.local")[0]
    assert entry.hostnames == ["dev.local", "api.dev.local"]
    assert entry.comment == "the laptop"


def test_a_commented_out_entry_is_an_entry_that_is_off():
    entry = parse().find("ads.example.com")[0]
    assert entry.enabled is False
    assert entry.ip == "0.0.0.0"


def test_a_plain_comment_is_not_an_entry():
    hosts = parse()
    assert isinstance(hosts.lines[0], Other)
    assert "# my project" in [line.text for line in hosts.lines if isinstance(line, Other)]


def test_finding_by_ip_or_by_name():
    hosts = parse()
    assert len(hosts.find("192.168.15.20")) == 1
    assert len(hosts.find("API.DEV.LOCAL")) == 1
    assert hosts.find("nothing.here") == []


def test_a_line_that_is_not_an_entry_is_left_alone():
    hosts = HostsFile.parse("garbage line here\n1.2.3.4 ok\n")
    assert len(hosts.entries) == 1
    assert isinstance(hosts.lines[0], Other)


def test_a_bad_ip_is_not_read_as_an_entry():
    assert HostsFile.parse("999.1.1.1 nope\n").entries == []


def test_a_hostname_with_illegal_characters_is_not_read_as_an_entry():
    assert HostsFile.parse("1.2.3.4 not_a_hostname\n").entries == []


# ---------------------------------------------------------------- writing

def test_an_untouched_file_round_trips_byte_for_byte():
    """Comments, blank lines and the distribution's header all survive a save."""
    assert parse().render() == SAMPLE


def test_toggling_only_changes_that_line():
    hosts = parse()
    hosts.toggle("dev.local")
    out = hosts.render()
    assert "# 192.168.15.20\tdev.local api.dev.local\t# the laptop" in out
    assert "# Static table lookup" in out
    assert out.count("127.0.0.1\tlocalhost") == 1


def test_enabling_a_disabled_entry():
    hosts = parse()
    hosts.set_enabled("ads.example.com", True)
    assert "0.0.0.0\tads.example.com" in hosts.render()
    assert "# 0.0.0.0" not in hosts.render()


def test_enabling_something_already_enabled_changes_nothing():
    hosts = parse()
    assert hosts.set_enabled("dev.local", True) == []
    assert hosts.render() == SAMPLE


def test_adding_an_entry_puts_it_after_the_last_one():
    hosts = parse()
    hosts.add("10.0.0.5", ["nas"], comment="the box in the cupboard")
    lines = hosts.render().splitlines()
    assert lines[-1] == "# 0.0.0.0\tads.example.com" or "nas" in "\n".join(lines)
    assert "10.0.0.5\tnas\t# the box in the cupboard" in hosts.render()


def test_adding_a_name_that_already_points_somewhere_else_is_refused():
    hosts = parse()
    with pytest.raises(HostsError) as e:
        hosts.add("10.0.0.9", ["dev.local"])
    assert "already points at" in str(e.value)


def test_adding_the_same_name_to_the_same_ip_is_allowed():
    hosts = parse()
    hosts.add("192.168.15.20", ["dev.local"])          # a second line, same target
    assert len(hosts.find("dev.local")) == 2


def test_removing_takes_the_whole_line():
    hosts = parse()
    assert len(hosts.remove("dev.local")) == 1
    assert hosts.find("api.dev.local") == []
    assert "# my project" in hosts.render()            # its comment stays


def test_removing_something_absent_says_so():
    assert parse().remove("nothing.here") == []


def test_an_added_entry_survives_a_round_trip():
    hosts = parse()
    hosts.add("10.1.2.3", ["a.test", "b.test"])
    again = HostsFile.parse(hosts.render())
    entry = again.find("b.test")[0]
    assert entry.ip == "10.1.2.3"
    assert entry.hostnames == ["a.test", "b.test"]


def test_a_disabled_entry_survives_a_round_trip():
    hosts = parse()
    hosts.toggle("dev.local")
    again = HostsFile.parse(hosts.render())
    assert again.find("dev.local")[0].enabled is False


# ---------------------------------------------------------------- validation

def test_ip_validation():
    assert validate_ip(" 192.168.0.1 ") == "192.168.0.1"
    assert validate_ip("::1") == "::1"
    for bad in ("", "1.2.3", "300.1.1.1", "hello"):
        with pytest.raises(HostsError):
            validate_ip(bad)


def test_hostname_validation():
    assert validate_hostname("Dev.Local.") == "Dev.Local"
    for bad in ("", "-bad.com", "bad-.com", "a_b.com", "a" * 64 + ".com", "with space"):
        with pytest.raises(HostsError):
            validate_hostname(bad)


def test_an_entry_needs_a_hostname():
    with pytest.raises(HostsError):
        HostsFile.parse("").add("1.2.3.4", [])


def test_entry_render_is_what_parse_reads_back():
    entry = Entry(ip="1.2.3.4", hostnames=["a.b"], comment="note")
    assert HostsFile.parse(entry.render()).entries[0].comment == "note"
