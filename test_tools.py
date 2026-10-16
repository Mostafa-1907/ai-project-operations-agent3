from database import initialize_database, get_connection

from tools import (
    create_task,
    update_task,
    assign_task,
    create_project_comment,
    get_project_tasks,
    get_task,
    get_team_members,
    get_project_deadline,
    approve_pending_action,
)


def print_result(title, result):
    print(f"\n--- {title} ---")
    print(result)


def run_tests():
    initialize_database()

    print("Starting tools tests...")

    # Create a test team member only if one does not already exist.
    with get_connection() as conn:
        member = conn.execute(
            """
            SELECT id
            FROM team_members
            WHERE name = ? AND role = ?
            LIMIT 1
            """,
            ("Test Member", "Tester"),
        ).fetchone()

        if member:
            member_id = member["id"]
        else:
            cursor = conn.execute(
                """
                INSERT INTO team_members (name, role, available)
                VALUES (?, ?, ?)
                """,
                ("Test Member", "Tester", 1),
            )
            member_id = cursor.lastrowid

    print(f"Test member ID: {member_id}")

    # Create task
    result = create_task(
        title="Automated Test Task",
        description="Created by test_tools.py",
        priority="Medium",
        due_date="2026-10-20",
    )

    print_result("Create task request", result)

    if not result.get("requires_approval"):
        print("Task creation did not return an approval request.")
        return

    approval_id = result["approval_id"]

    result = approve_pending_action(approval_id)
    print_result("Approve task creation", result)

    if not result.get("success"):
        print("Task creation failed.")
        return

    task_id = result["task_id"]

    # Update task
    result = update_task(
        task_id=task_id,
        status="In Progress",
    )

    print_result("Update task request", result)

    if result.get("requires_approval"):
        result = approve_pending_action(result["approval_id"])
        print_result("Approve task update", result)

    # Assign task
    result = assign_task(
        task_id=task_id,
        member_id=member_id,
    )

    print_result("Assign task request", result)

    if result.get("requires_approval"):
        result = approve_pending_action(result["approval_id"])
        print_result("Approve task assignment", result)

    # Add a comment
    result = create_project_comment(
        comment="Automated test comment",
        task_id=task_id,
    )

    print_result("Create project comment", result)

    # Read task
    result = get_task(task_id)
    print_result("Read task", result)

    # Read all tasks
    result = get_project_tasks()
    print_result("All tasks", result)

    # Read team members
    result = get_team_members()
    print_result("Team members", result)

    # Read project deadline
    result = get_project_deadline()
    print_result("Project deadline", result)

    print("\nAll test steps finished.")


if __name__ == "__main__":
    run_tests()