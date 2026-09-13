# Roles & Permissions

Users are defined in `data/users.json` and assigned a **global role** plus per-project **project roles**.

## Global roles

| Role | Meaning |
|------|---------|
| `system_admin` | Can see and manage **all** projects. |
| `annotator` | Only sees projects they have explicit permission for. |

## Project roles

Project roles are stored per user per project and control what a user can do inside a specific project.

| Role | Meaning |
|------|---------|
| `project_admin` | Manage the project (rename, configure, delete) and manage its members. |
| `annotator` | Label rows in the project. |

## Managing members

Membership is edited on the project **Settings** page (project list → **Settings**),
in the **Members** section: search a user by id or name, pick a project role, and add
them; change a role from the dropdown or remove someone with **Remove**.

Only a `project_admin` of that project — or any `system_admin` — may open the
settings page or change membership. `annotator`s see a message explaining they need
the `project_admin` role instead. A global `system_admin` can always manage a
project, even after its last project admin is removed, so a project can never be
stranded without someone who can manage it (removing the last `project_admin` by a
peer returns `409`).

The same rules are enforced by the API, not just the UI — see
[API → Project members](/api/#project-members).

## Seed file format

```json
{
  "users": [
    { "id": "alice", "name": "Alice", "global_role": "system_admin" },
    { "id": "bob", "name": "Bob", "global_role": "annotator",
      "project_roles": { "proj-1": "project_admin", "proj-2": "annotator" } }
  ]
}
```

## Login

Login is by **user ID** only (no password in the default setup). The backend returns the user's global role and the mapping of project IDs to project roles. The frontend then shows only the projects you are allowed to open.

By default (`SSO_ENABLED=false`) the login screen shows this user-ID form. Set
`SSO_ENABLED=true` (plus the `KEYCLOAK_*` vars, see [Install](/install)) to swap
it for the **Sign in with SSO** button — the screen asks the backend via
`GET /api/v1/auth/config` which mode to show.
