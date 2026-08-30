from app.paths import frontend_dist, is_frozen, sqlite_path


def test_not_frozen_in_pytest():
    assert is_frozen() is False


def test_sqlite_path_is_under_data():
    path = sqlite_path()
    assert path.name == "inventory.db"
    assert path.parent.name == "data"


def test_frontend_dist_points_at_web_build():
    dist = frontend_dist()
    assert dist.name == "dist"
    assert dist.parent.name == "frontend"
