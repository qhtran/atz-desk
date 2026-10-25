from backend.identity import me_from_headers, username_from_headers


def test_username_from_headers():
    assert username_from_headers({"X-Authentik-Username": " hoai "}) == "hoai"
    assert username_from_headers({}) == "local"


def test_me_from_headers_groups():
    me = me_from_headers(
        {
            "x-authentik-username": "u",
            "x-authentik-groups": "admin|members",
        }
    )
    assert me is not None
    assert me["username"] == "u"
    assert me["groups"] == ["admin", "members"]
