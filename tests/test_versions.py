from hearthwatch import versions


def test_minimum_versions_pass():
    assert versions.problems((3, 12, 0), (4, 12, 0), (1, 4, 0)) == []
    assert versions.problems((3, 14, 4), (4, 20, 1), (1, 8, 0)) == []


def test_too_old_versions_are_reported():
    found = versions.problems((3, 11, 2), (4, 8, 3), (1, 2, 0))
    assert len(found) == 3
    assert "Python 3.11.2" in found[0] and "3.12" in found[0]
    assert "GTK 4.8.3" in found[1]
    assert "libadwaita 1.2.0" in found[2]


def test_unknown_gui_versions_are_ignored():
    assert versions.problems((3, 12, 1), None, None) == []
