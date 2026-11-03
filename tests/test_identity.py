from backend.identity import is_admin_user, me_from_headers, roles_for_user, username_from_headers


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
    assert is_admin_user(me["groups"], ["admin"]) is True
    assert "admin" in roles_for_user(me["groups"], is_admin=True)
