"""Project membership and role checks.

Single source of truth for "who may do what inside a project":

* global roles on ``fyndnote_users.global_role`` — ``system_admin`` sees and
  manages every project, ``annotator`` only sees projects they were granted.
* per-project roles on ``fyndnote_project_permissions.role`` — ``project_admin``
  manages the project (including its members), ``annotator`` labels rows.
"""

from ..database import get_db

PROJECT_ROLES = ("project_admin", "annotator")
GLOBAL_ROLES = ("system_admin", "annotator")
ADMIN_GLOBAL_ROLE = "system_admin"

_CANDIDATE_LIMIT = 20


class PermissionService:
    # ---- role checks -------------------------------------------------------

    @staticmethod
    def get_user(user_id: str) -> dict | None:
        db = get_db()
        try:
            row = db.execute(
                "SELECT id, name, global_role FROM fyndnote_users WHERE id = ?",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            db.close()

    @staticmethod
    def get_project_role(pid: str, user_id: str) -> str | None:
        db = get_db()
        try:
            row = db.execute(
                "SELECT role FROM fyndnote_project_permissions"
                " WHERE user_id = ? AND project_id = ?",
                (user_id, pid),
            ).fetchone()
            return row["role"] if row else None
        finally:
            db.close()

    @staticmethod
    def is_system_admin(user_id: str) -> bool:
        user = PermissionService.get_user(user_id)
        return bool(user and user["global_role"] == ADMIN_GLOBAL_ROLE)

    @staticmethod
    def effective_role(pid: str, user_id: str) -> str | None:
        """The caller's role in ``pid``, honouring the global admin override.

        Returns ``system_admin``, ``project_admin``, ``annotator`` or ``None``
        when the user has no access to the project at all.
        """
        if PermissionService.is_system_admin(user_id):
            return ADMIN_GLOBAL_ROLE
        return PermissionService.get_project_role(pid, user_id)

    @staticmethod
    def can_view_project(pid: str, user_id: str) -> bool:
        if PermissionService.is_system_admin(user_id):
            return True
        return PermissionService.get_project_role(pid, user_id) is not None

    @staticmethod
    def can_manage_project(pid: str, user_id: str) -> bool:
        """Global admins and project admins may configure the project."""
        if PermissionService.is_system_admin(user_id):
            return True
        return PermissionService.get_project_role(pid, user_id) == "project_admin"

    # ---- membership --------------------------------------------------------

    @staticmethod
    def list_members(pid: str) -> list[dict]:
        db = get_db()
        try:
            rows = db.execute(
                """
                SELECT pp.user_id, u.name, u.global_role, pp.role
                FROM fyndnote_project_permissions pp
                JOIN fyndnote_users u ON u.id = pp.user_id
                WHERE pp.project_id = ?
                ORDER BY u.name
                """,
                (pid,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            db.close()

    @staticmethod
    def list_candidates(pid: str, q: str = "") -> list[dict]:
        """Users who are *not* members yet, for the settings-page picker."""
        like = f"%{q.strip().lower()}%"
        db = get_db()
        try:
            rows = db.execute(
                """
                SELECT u.id AS user_id, u.name, u.global_role
                FROM fyndnote_users u
                WHERE u.id NOT IN (
                    SELECT user_id FROM fyndnote_project_permissions WHERE project_id = ?
                )
                AND (lower(u.id) LIKE ? OR lower(u.name) LIKE ?)
                ORDER BY u.name
                LIMIT ?
                """,
                (pid, like, like, _CANDIDATE_LIMIT),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            db.close()

    @staticmethod
    def count_admins(pid: str) -> int:
        db = get_db()
        try:
            return db.execute(
                "SELECT COUNT(*) FROM fyndnote_project_permissions"
                " WHERE project_id = ? AND role = 'project_admin'",
                (pid,),
            ).fetchone()[0]
        finally:
            db.close()

    @staticmethod
    def assign_role(pid: str, user_id: str, role: str) -> str | None:
        """Grant ``role`` on ``pid``, inserting or updating the membership row.

        Returns ``"added"``/``"updated"``, or ``None`` when ``user_id`` is not a
        known user (membership rows must reference ``fyndnote_users``).
        """
        db = get_db()
        try:
            if not db.execute(
                "SELECT 1 FROM fyndnote_users WHERE id = ?", (user_id,)
            ).fetchone():
                return None
            existing = db.execute(
                "SELECT role FROM fyndnote_project_permissions"
                " WHERE user_id = ? AND project_id = ?",
                (user_id, pid),
            ).fetchone()
            if existing:
                db.execute(
                    "UPDATE fyndnote_project_permissions SET role = ?"
                    " WHERE user_id = ? AND project_id = ?",
                    (role, user_id, pid),
                )
                status = "updated"
            else:
                db.execute(
                    "INSERT INTO fyndnote_project_permissions (user_id, project_id, role)"
                    " VALUES (?, ?, ?)",
                    (user_id, pid, role),
                )
                status = "added"
            db.commit()
            return status
        finally:
            db.close()

    @staticmethod
    def revoke(pid: str, user_id: str) -> bool:
        """Remove membership. Returns False when the user was not a member."""
        db = get_db()
        try:
            cursor = db.execute(
                "DELETE FROM fyndnote_project_permissions"
                " WHERE user_id = ? AND project_id = ?",
                (user_id, pid),
            )
            db.commit()
            return cursor.rowcount > 0
        finally:
            db.close()
