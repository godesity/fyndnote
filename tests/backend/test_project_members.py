"""Project membership + permission enforcement on the /projects/{pid}/members routes."""

import csv
import tempfile


def _make_project(client, name="members-proj"):
    """Project created by alice (creator becomes project_admin via user_id)."""
    _, path = tempfile.mkstemp(suffix=".csv")
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "text"])
        writer.writeheader()
        writer.writerows([{"id": 1, "text": "hello"}, {"id": 2, "text": "world"}])
    dresp = client.post("/api/v1/datasets/load?user_id=alice", json={"source": f"file://{path}"})
    assert dresp.status_code == 200

    tresp = client.post(
        "/api/v1/templates", json={"name": "tpl", "source": "<div>{data.text}</div>"}
    )
    presp = client.post(
        "/api/v1/projects",
        json={
            "name": name,
            "dataset_id": dresp.json()["id"],
            "template_id": tresp.json()["id"],
            "user_id": "alice",
        },
    )
    assert presp.status_code == 201
    return presp.json()["id"]


# ---- listing / discovery ----------------------------------------------------


def test_members_lists_creator_with_role(client):
    pid = _make_project(client, "m-list")
    resp = client.get(f"/api/v1/projects/{pid}/members?user_id=alice")
    assert resp.status_code == 200
    assert resp.json() == [
        {"user_id": "alice", "name": "Alice", "global_role": "system_admin", "role": "project_admin"}
    ]

def _ensure_user(user_id, name, global_role="annotator"):
    from fyndnote.database import get_db

    db = get_db()
    try:
        db.execute(
            "INSERT OR IGNORE INTO fyndnote_users (id, name, global_role) VALUES (?, ?, ?)",
            (user_id, name, global_role),
        )
        db.commit()
    finally:
        db.close()


def test_member_list_forbidden_for_outsider(client):
    pid = _make_project(client, "m-outsider")
    # carol is neither a global admin nor a member of this project
    _ensure_user("carol", "Carol")
    resp = client.get(f"/api/v1/projects/{pid}/members?user_id=carol")
    assert resp.status_code == 403


def test_candidates_exclude_existing_members(client):
    pid = _make_project(client, "m-cand")
    resp = client.get(f"/api/v1/projects/{pid}/member-candidates?user_id=alice")
    assert resp.status_code == 200
    ids = [c["user_id"] for c in resp.json()]
    assert "alice" not in ids  # already a member
    assert "bob" in ids

    # Search narrows by id or name, case-insensitively.
    assert [c["user_id"] for c in client.get(
        f"/api/v1/projects/{pid}/member-candidates?user_id=alice&q=BOB"
    ).json()] == ["bob"]


def test_candidates_require_manager(client):
    pid = _make_project(client, "m-cand-authz")
    client.put(f"/api/v1/projects/{pid}/members", json={
        "user_id": "bob", "role": "annotator", "actor": "alice"
    })
    # bob is a plain annotator -> may not even enumerate candidates
    assert client.get(
        f"/api/v1/projects/{pid}/member-candidates?user_id=bob"
    ).status_code == 403


# ---- granting / updating ----------------------------------------------------


def test_add_member_then_they_can_see_project(client):
    pid = _make_project(client, "m-add")
    resp = client.put(f"/api/v1/projects/{pid}/members", json={
        "user_id": "bob", "role": "annotator", "actor": "alice"
    })
    assert resp.status_code == 200

    members = client.get(f"/api/v1/projects/{pid}/members?user_id=alice").json()
    assert {m["user_id"]: m["role"] for m in members} == {
        "alice": "project_admin",
        "bob": "annotator",
    }
    # Membership is what makes the project appear for a global annotator.
    assert pid in [p["id"] for p in client.get("/api/v1/projects?user_id=bob").json()["projects"]]


def test_reassigning_role_updates_instead_of_duplicating(client):
    pid = _make_project(client, "m-role")
    client.put(f"/api/v1/projects/{pid}/members", json={
        "user_id": "bob", "role": "annotator", "actor": "alice"
    })
    client.put(f"/api/v1/projects/{pid}/members", json={
        "user_id": "bob", "role": "project_admin", "actor": "alice"
    })
    members = client.get(f"/api/v1/projects/{pid}/members?user_id=alice").json()
    assert [m["role"] for m in members if m["user_id"] == "bob"] == ["project_admin"]


def test_project_admin_can_manage_members_without_global_admin(client):
    pid = _make_project(client, "m-padmin")
    client.put(f"/api/v1/projects/{pid}/members", json={
        "user_id": "bob", "role": "project_admin", "actor": "alice"
    })
    # bob is only a *project* admin on this project but may still add members.
    resp = client.put(f"/api/v1/projects/{pid}/members", json={
        "user_id": "carol", "role": "annotator", "actor": "bob"
    })
    assert resp.status_code == 200


def test_add_member_rejects_unknown_user(client):
    pid = _make_project(client, "m-unknown")
    resp = client.put(f"/api/v1/projects/{pid}/members", json={
        "user_id": "nobody", "role": "annotator", "actor": "alice"
    })
    assert resp.status_code == 404


def test_add_member_rejects_unknown_role(client):
    pid = _make_project(client, "m-badrole")
    resp = client.put(f"/api/v1/projects/{pid}/members", json={
        "user_id": "bob", "role": "owner", "actor": "alice"
    })
    assert resp.status_code == 400


def test_annotator_cannot_manage_members(client):
    pid = _make_project(client, "m-authz")
    client.put(f"/api/v1/projects/{pid}/members", json={
        "user_id": "bob", "role": "annotator", "actor": "alice"
    })
    resp = client.put(f"/api/v1/projects/{pid}/members", json={
        "user_id": "carol", "role": "project_admin", "actor": "bob"
    })
    assert resp.status_code == 403
    assert "carol" not in [m["user_id"] for m in
                           client.get(f"/api/v1/projects/{pid}/members?user_id=alice").json()]


def test_member_routes_404_for_unknown_project(client):
    resp = client.put("/api/v1/projects/nope/members", json={
        "user_id": "bob", "role": "annotator", "actor": "alice"
    })
    assert resp.status_code == 404
    assert client.get("/api/v1/projects/nope/members?user_id=alice").status_code == 404


# ---- removal ----------------------------------------------------------------


def test_remove_member(client):
    pid = _make_project(client, "m-remove")
    client.put(f"/api/v1/projects/{pid}/members", json={
        "user_id": "bob", "role": "annotator", "actor": "alice"
    })
    resp = client.delete(f"/api/v1/projects/{pid}/members/bob?user_id=alice")
    assert resp.status_code == 200
    assert "bob" not in [m["user_id"] for m in
                         client.get(f"/api/v1/projects/{pid}/members?user_id=alice").json()]
    # Revoking again is a 404, and the project disappears from bob's list.
    assert client.delete(
        f"/api/v1/projects/{pid}/members/bob?user_id=alice"
    ).status_code == 404
    assert pid not in [p["id"] for p in client.get("/api/v1/projects?user_id=bob").json()["projects"]]


def test_last_project_admin_cannot_be_removed_by_a_peer(client):
    pid = _make_project(client, "m-lastadmin")
    client.put(f"/api/v1/projects/{pid}/members", json={
        "user_id": "bob", "role": "project_admin", "actor": "alice"
    })
    # Two admins: bob (who is only a *project* admin) may demote alice.
    assert client.delete(
        f"/api/v1/projects/{pid}/members/alice?user_id=bob"
    ).status_code == 200

    # bob is now the sole project_admin and not a global admin -> stranded.
    resp = client.delete(f"/api/v1/projects/{pid}/members/bob?user_id=bob")
    assert resp.status_code == 409
    assert [m["user_id"] for m in
            client.get(f"/api/v1/projects/{pid}/members?user_id=bob").json()] == ["bob"]


def test_global_admin_may_remove_last_project_admin(client):
    pid = _make_project(client, "m-lastadmin-global")
    client.put(f"/api/v1/projects/{pid}/members", json={
        "user_id": "bob", "role": "project_admin", "actor": "alice"
    })
    # alice drops her own membership; bob becomes the only project_admin.
    assert client.delete(
        f"/api/v1/projects/{pid}/members/alice?user_id=alice"
    ).status_code == 200

    # alice is a global admin, so the single-admin guard does not apply to her.
    assert client.delete(
        f"/api/v1/projects/{pid}/members/bob?user_id=alice"
    ).status_code == 200
    assert client.get(f"/api/v1/projects/{pid}/members?user_id=alice").json() == []


# ---- project write endpoints now require a manager --------------------------


def test_update_project_requires_manager(client):
    pid = _make_project(client, "m-update")
    client.put(f"/api/v1/projects/{pid}/members", json={
        "user_id": "bob", "role": "annotator", "actor": "alice"
    })
    assert client.put(f"/api/v1/projects/{pid}?user_id=bob", json={
        "name": "hijacked"
    }).status_code == 403

    assert client.put(f"/api/v1/projects/{pid}?user_id=alice", json={
        "name": "renamed"
    }).status_code == 200


def test_project_detail_exposes_role_flags(client):
    pid = _make_project(client, "m-flags")
    as_admin = client.get(f"/api/v1/projects/{pid}?user_id=alice").json()
    assert (as_admin["my_role"], as_admin["can_manage"], as_admin["can_view"]) == (
        "system_admin",
        True,
        True,
    )

    client.put(f"/api/v1/projects/{pid}/members", json={
        "user_id": "bob", "role": "annotator", "actor": "alice"
    })
    as_annotator = client.get(f"/api/v1/projects/{pid}?user_id=bob").json()
    assert (as_annotator["my_role"], as_annotator["can_manage"], as_annotator["can_view"]) == (
        "annotator",
        False,
        True,
    )

    outsider = client.get(f"/api/v1/projects/{pid}?user_id=carol").json()
    assert (outsider["my_role"], outsider["can_manage"], outsider["can_view"]) == (
        None,
        False,
        False,
    )
