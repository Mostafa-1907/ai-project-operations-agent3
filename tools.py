from datetime import date

from database import get_connection
from guardrails import (
    request_approval,
    approve_action,
    consume_approved_action,
)


VALID_PRIORITIES = {
    "Low",
    "Medium",
    "High",
    "Critical",
}

VALID_STATUSES = {
    "Pending",
    "In Progress",
    "Blocked",
    "Completed",
}


def validate_date(value):
    if value is None or value == "":
        return True

    try:
        date.fromisoformat(str(value)[:10])
        return True
    except ValueError:
        return False


# CREATE TASK

def create_task(
    title: str,
    description: str = "",
    priority: str = "Medium",
    due_date: str | None = None,
):
    title = (title or "").strip()
    priority = (priority or "Medium").strip().title()

    if not title:
        return {
            "success": False,
            "message": "Task title cannot be empty.",
        }

    if priority not in VALID_PRIORITIES:
        return {
            "success": False,
            "message": "Invalid priority.",
        }

    if not validate_date(due_date):
        return {
            "success": False,
            "message": "Date must use YYYY-MM-DD.",
        }

    return request_approval(
        "create_task",
        {
            "title": title,
            "description": (description or "").strip(),
            "priority": priority,
            "due_date": due_date or None,
        },
    )


# UPDATE TASK

def update_task(
    task_id: int,
    title: str | None = None,
    description: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    due_date: str | None = None,
):
    try:
        task_id = int(task_id)
    except (TypeError, ValueError):
        return {
            "success": False,
            "message": "Task ID must be a number.",
        }

    with get_connection() as conn:
        task = conn.execute(
            "SELECT id FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

    if task is None:
        return {
            "success": False,
            "message": f"Task #{task_id} not found.",
        }

    params = {"task_id": task_id}

    values = {
        "title": title,
        "description": description,
        "status": status,
        "priority": priority,
        "due_date": due_date,
    }

    for key, value in values.items():
        if value is not None:
            params[key] = (
                value.strip()
                if isinstance(value, str)
                else value
            )

    if len(params) == 1:
        return {
            "success": False,
            "message": "No updates provided.",
        }

    if "title" in params and not params["title"]:
        return {
            "success": False,
            "message": "Task title cannot be empty.",
        }

    if (
        "status" in params
        and params["status"] not in VALID_STATUSES
    ):
        return {
            "success": False,
            "message": "Invalid task status.",
        }

    if (
        "priority" in params
        and params["priority"] not in VALID_PRIORITIES
    ):
        return {
            "success": False,
            "message": "Invalid task priority.",
        }

    if (
        "due_date" in params
        and not validate_date(params["due_date"])
    ):
        return {
            "success": False,
            "message": "Date must use YYYY-MM-DD.",
        }

    return request_approval("update_task", params)


# ASSIGN TASK

def assign_task(task_id: int, member_id: int):
    try:
        task_id = int(task_id)
        member_id = int(member_id)
    except (TypeError, ValueError):
        return {
            "success": False,
            "message": "Task ID and member ID must be numbers.",
        }

    with get_connection() as conn:
        task = conn.execute(
            "SELECT id FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        member = conn.execute(
            """
            SELECT id
            FROM team_members
            WHERE id = ? AND available = 1
            """,
            (member_id,),
        ).fetchone()

    if task is None:
        return {
            "success": False,
            "message": f"Task #{task_id} not found.",
        }

    if member is None:
        return {
            "success": False,
            "message": "Available team member not found.",
        }

    return request_approval(
        "assign_task",
        {
            "task_id": task_id,
            "member_id": member_id,
        },
    )


# CREATE PROJECT COMMENT

def create_project_comment(
    comment: str,
    task_id: int | None = None,
):
    comment = (comment or "").strip()

    if not comment:
        return {
            "success": False,
            "message": "Comment cannot be empty.",
        }

    if task_id is not None:
        try:
            task_id = int(task_id)
        except (TypeError, ValueError):
            return {
                "success": False,
                "message": "Task ID must be a number.",
            }

    with get_connection() as conn:
        if task_id is not None:
            task = conn.execute(
                "SELECT id FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()

            if task is None:
                return {
                    "success": False,
                    "message": "Task not found.",
                }

        cursor = conn.execute(
            """
            INSERT INTO project_comments (task_id, comment)
            VALUES (?, ?)
            """,
            (task_id, comment),
        )

        comment_id = cursor.lastrowid

    return {
        "success": True,
        "comment_id": comment_id,
        "message": "Comment created successfully.",
    }


# GET PROJECT TASKS

def get_project_tasks(status: str | None = None):
    with get_connection() as conn:
        if status:
            rows = conn.execute(
                """
                SELECT *
                FROM tasks
                WHERE lower(status) = lower(?)
                ORDER BY id
                """,
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY id"
            ).fetchall()

    return [dict(row) for row in rows]


# GET ONE TASK

def get_task(task_id: int):
    try:
        task_id = int(task_id)
    except (TypeError, ValueError):
        return {
            "success": False,
            "message": "Task ID must be a number.",
        }

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

    if row is None:
        return {
            "success": False,
            "message": "Task not found.",
        }

    return dict(row)


# GET TEAM MEMBERS

def get_team_members():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM team_members ORDER BY id"
        ).fetchall()

    return [dict(row) for row in rows]


# GET PROJECT DEADLINE

def get_project_deadline():
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT MAX(due_date) AS project_deadline
            FROM tasks
            WHERE due_date IS NOT NULL
            """
        ).fetchone()

    return {
        "project_deadline": (
            row["project_deadline"] if row else None
        )
    }


# EXECUTE AN APPROVED ACTION

def approve_pending_action(approval_id: str):
    approval_result = approve_action(approval_id)

    if not approval_result["success"]:
        return approval_result

    request = consume_approved_action(approval_id)

    if request is None:
        return {
            "success": False,
            "message": "Approval could not be processed.",
        }

    action = request["action"]
    params = request["params"]

    # CREATE

    if action == "create_task":
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO tasks (
                    title,
                    description,
                    priority,
                    due_date
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    params["title"],
                    params.get("description", ""),
                    params["priority"],
                    params.get("due_date"),
                ),
            )

            task_id = cursor.lastrowid

        return {
            "success": True,
            "task_id": task_id,
            "message": "Task created successfully.",
        }

    # UPDATE

    if action == "update_task":
        allowed_fields = {
            "title",
            "description",
            "status",
            "priority",
            "due_date",
        }

        fields = {
            key: value
            for key, value in params.items()
            if key in allowed_fields and value is not None
        }

        if not fields:
            return {
                "success": False,
                "message": "No updates provided.",
            }

        with get_connection() as conn:
            task = conn.execute(
                "SELECT id FROM tasks WHERE id = ?",
                (params["task_id"],),
            ).fetchone()

            if task is None:
                return {
                    "success": False,
                    "message": "Task not found.",
                }

            query = (
                "UPDATE tasks SET "
                + ", ".join(
                    f"{field} = ?" for field in fields
                )
                + " WHERE id = ?"
            )

            conn.execute(
                query,
                (*fields.values(), params["task_id"]),
            )

        return {
            "success": True,
            "task_id": params["task_id"],
            "message": "Task updated successfully.",
        }

    # ASSIGN

    if action == "assign_task":
        with get_connection() as conn:
            member = conn.execute(
                """
                SELECT id
                FROM team_members
                WHERE id = ? AND available = 1
                """,
                (params["member_id"],),
            ).fetchone()

            if member is None:
                return {
                    "success": False,
                    "message": "Available team member not found.",
                }

            cursor = conn.execute(
                """
                UPDATE tasks
                SET assigned_to = ?
                WHERE id = ?
                """,
                (
                    params["member_id"],
                    params["task_id"],
                ),
            )

            if cursor.rowcount == 0:
                return {
                    "success": False,
                    "message": "Task not found.",
                }

        return {
            "success": True,
            "task_id": params["task_id"],
            "member_id": params["member_id"],
            "message": "Task assigned successfully.",
        }

    return {
        "success": False,
        "message": "Unknown action.",
    }


def test_approval_request():
    return create_task(
        title="Approval Test Task",
        description="Testing human approval",
        priority="Medium",
        due_date="2026-10-20",
    )