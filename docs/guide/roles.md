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
| `project_admin` | Manage the project (rename, configure, delete). |
| `annotator` | Label rows in the project. |

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
