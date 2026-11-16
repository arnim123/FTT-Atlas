from tests.helpers import CSRF, assert_error, google_login, identity, login


def test_listing_users_follows_the_role_rules(api, org):
    assert_error(api.get("/api/v1/users"), 401, "UNAUTHENTICATED")

    login(api, org.admin.email)
    sales = api.get("/api/v1/users?department_id=" + str(org.sales.id))
    assert {item["email"] for item in sales.json()["items"]} == {org.guest.email, org.sales_employee.email, org.sales_manager.email}

    invited = api.get("/api/v1/users?status=invited").json()
    assert {item["email"] for item in invited["items"]} == {org.employee.email}
    assert invited["items"][0]["status"] == "invited"

    active = {item["email"] for item in api.get("/api/v1/users?status=active").json()["items"]}
    assert org.employee.email not in active
    assert org.deactivated.email not in active
    assert org.bot.email in active

    deactivated = {item["email"] for item in api.get("/api/v1/users?status=deactivated").json()["items"]}
    assert deactivated == {org.deactivated.email}

    bots = {item["email"] for item in api.get("/api/v1/users?is_bot=true").json()["items"]}
    assert bots == {org.bot.email}

    guests = {item["email"] for item in api.get("/api/v1/users?role=guest").json()["items"]}
    assert guests == {org.guest.email}

    found = api.get("/api/v1/users?search=noah").json()
    assert [item["email"] for item in found["items"]] == [org.guest.email]

    page = api.get(f"/api/v1/users?department_id={org.sales.id}&page=2&page_size=1").json()
    assert page["total"] == 3
    assert page["page"] == 2
    assert [item["name"] for item in page["items"]] == ["Pat Sales"]

    login(api, org.manager.email)
    own = api.get("/api/v1/users")
    assert own.status_code == 200, own.text
    own_emails = {item["email"] for item in own.json()["items"]}
    assert own_emails == {
        org.super_admin.email,
        org.admin.email,
        org.manager.email,
        org.employee.email,
        org.bot.email,
        org.deactivated.email,
    }
    assert own.json()["total"] == 6
    assert_error(api.get(f"/api/v1/users?department_id={org.sales.id}"), 403, "FORBIDDEN")

    for email in (org.guest.email, org.employee.email):
        login(api, email)
        assert_error(api.get("/api/v1/users"), 403, "FORBIDDEN")
        api.cookies.clear()


def test_invite_rules(api, org):
    login(api, org.employee.email)
    denied = _invite(api, email="new.person@company.com", role="employee", department_id=str(org.product.id))
    assert_error(denied, 403, "FORBIDDEN")

    login(api, org.manager.email)
    created = _invite(api, email="new.person@company.com", role="employee", department_id=str(org.product.id))
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "invited"
    assert created.json()["name"] == "New Person"
    assert created.json()["invited_by"] == str(org.manager.id)
    assert_error(_invite(api, email="other.person@company.com", role="employee", department_id=str(org.sales.id)), 403, "FORBIDDEN")
    assert_error(_invite(api, email="lead@company.com", role="manager", department_id=str(org.product.id)), 403, "FORBIDDEN")
    assert_error(_invite(api, email="guest.two@partner.co", role="guest", department_id=str(org.product.id)), 403, "FORBIDDEN")
    assert_error(_invite(api, email="new.person@company.com", role="employee", department_id=str(org.product.id)), 409, "EMAIL_EXISTS")

    login(api, org.admin.email)
    guest = _invite(api, email="guest.two@partner.co", role="guest", department_id=str(org.sales.id))
    assert guest.status_code == 201, guest.text
    assert guest.json()["role"] == "guest"
    assert_error(_invite(api, email="bob@gmail.com", role="employee", department_id=str(org.product.id)), 403, "DOMAIN_NOT_ALLOWED")
    assert_error(_invite(api, email="another.admin@company.com", role="admin", department_id=str(org.product.id)), 403, "FORBIDDEN")
    assert_error(_invite(api, email="bot.guest@company.com", role="guest", department_id=str(org.product.id), is_bot=True), 422, "INVALID_ACCOUNT")
    missing = _invite(api, email="missing.dept@company.com", role="employee", department_id="00000000-0000-0000-0000-000000000000")
    assert_error(missing, 404, "NOT_FOUND")

    blocked = api.post(
        "/api/v1/users/invite",
        json={"email": "csrf.person@company.com", "role": "employee", "department_id": str(org.product.id)},
    )
    assert_error(blocked, 403, "CSRF_REQUIRED")

    login(api, org.super_admin.email)
    admin = _invite(api, email="another.admin@company.com", role="admin", department_id=str(org.sales.id))
    assert admin.status_code == 201, admin.text
    assert admin.json()["role"] == "admin"
    bot = _invite(api, email="runner@company.com", role="employee", department_id=str(org.product.id), is_bot=True)
    assert bot.status_code == 201, bot.text
    assert bot.json()["is_bot"] is True
    assert bot.json()["status"] == "active"
    assert_error(google_login(api, identity("runner@company.com", sub="sub-runner")), 403, "BOT_LOGIN_FORBIDDEN")


def test_updates_follow_role_rules_and_emit_access_changes(api, org, events):
    login(api, org.manager.email)
    renamed = api.patch(f"/api/v1/users/{org.employee.id}", json={"name": "Emma D."}, headers=CSRF)
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Emma D."
    assert events == []
    assert_error(
        api.patch(f"/api/v1/users/{org.employee.id}", json={"department_id": str(org.sales.id)}, headers=CSRF),
        403,
        "FORBIDDEN",
    )
    assert_error(api.patch(f"/api/v1/users/{org.sales_employee.id}", json={"name": "Sam"}, headers=CSRF), 403, "FORBIDDEN")
    assert_error(api.patch(f"/api/v1/users/{org.employee.id}", json={"role": "manager"}, headers=CSRF), 403, "FORBIDDEN")
    assert_error(api.patch(f"/api/v1/users/{org.admin.id}", json={"name": "Sarah"}, headers=CSRF), 403, "FORBIDDEN")

    login(api, org.admin.email)
    promoted = api.patch(f"/api/v1/users/{org.employee.id}", json={"role": "manager"}, headers=CSRF)
    assert promoted.status_code == 200, promoted.text
    assert events == [{"user_id": str(org.employee.id), "changes": {"role": {"from": "employee", "to": "manager"}}}]
    assert_error(api.patch(f"/api/v1/users/{org.sales_employee.id}", json={"role": "admin"}, headers=CSRF), 403, "FORBIDDEN")
    assert_error(api.patch(f"/api/v1/users/{org.super_admin.id}", json={"name": "Alex"}, headers=CSRF), 403, "FORBIDDEN")
    moved = api.patch(f"/api/v1/users/{org.sales_employee.id}", json={"department_id": str(org.product.id)}, headers=CSRF)
    assert moved.status_code == 200, moved.text
    assert events[1]["changes"]["department_id"] == {"from": str(org.sales.id), "to": str(org.product.id)}
    assert_error(api.patch(f"/api/v1/users/{org.guest.id}", json={"role": "employee"}, headers=CSRF), 403, "DOMAIN_NOT_ALLOWED")

    login(api, org.super_admin.email)
    renamed_admin = api.patch(f"/api/v1/users/{org.admin.id}", json={"name": "Sarah C."}, headers=CSRF)
    assert renamed_admin.status_code == 200, renamed_admin.text
    assert len(events) == 2
    assert_error(api.patch(f"/api/v1/users/{org.super_admin.id}", json={"role": "admin"}, headers=CSRF), 409, "LAST_SUPER_ADMIN")
    second = _invite(api, email="second.admin@company.com", role="super_admin", department_id=str(org.product.id))
    assert second.status_code == 201, second.text
    demoted = api.patch(f"/api/v1/users/{org.super_admin.id}", json={"role": "employee"}, headers=CSRF)
    assert demoted.status_code == 200, demoted.text
    assert events[-1]["changes"]["role"] == {"from": "super_admin", "to": "employee"}


def test_deactivate_and_reactivate(api, org, events):
    login(api, org.super_admin.email)
    assert_error(api.post(f"/api/v1/users/{org.super_admin.id}/deactivate", headers=CSRF), 409, "LAST_SUPER_ADMIN")

    login(api, org.manager.email)
    assert_error(api.post(f"/api/v1/users/{org.manager.id}/deactivate", headers=CSRF), 403, "FORBIDDEN")
    assert_error(api.post(f"/api/v1/users/{org.admin.id}/deactivate", headers=CSRF), 403, "FORBIDDEN")
    assert_error(api.post(f"/api/v1/users/{org.sales_employee.id}/deactivate", headers=CSRF), 403, "FORBIDDEN")

    deactivated = api.post(f"/api/v1/users/{org.employee.id}/deactivate", headers=CSRF)
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["status"] == "deactivated"
    assert events == [{"user_id": str(org.employee.id), "changes": {"is_active": {"from": True, "to": False}}}]
    again = api.post(f"/api/v1/users/{org.employee.id}/deactivate", headers=CSRF)
    assert again.status_code == 200, again.text
    assert len(events) == 1
    restored = api.post(f"/api/v1/users/{org.employee.id}/reactivate", headers=CSRF)
    assert restored.status_code == 200, restored.text
    assert restored.json()["status"] == "invited"
    assert events[-1]["changes"]["is_active"] == {"from": False, "to": True}

    login(api, org.super_admin.email)
    second = _invite(api, email="second.admin@company.com", role="super_admin", department_id=str(org.product.id))
    assert second.status_code == 201, second.text
    assert_error(api.post(f"/api/v1/users/{org.super_admin.id}/deactivate", headers=CSRF), 403, "SELF_DEACTIVATE")
    removed = api.post(f"/api/v1/users/{second.json()['id']}/deactivate", headers=CSRF)
    assert removed.status_code == 200, removed.text
    assert_error(api.post(f"/api/v1/users/{org.super_admin.id}/deactivate", headers=CSRF), 409, "LAST_SUPER_ADMIN")


def _invite(api, **body):
    return api.post("/api/v1/users/invite", json=body, headers=CSRF)
