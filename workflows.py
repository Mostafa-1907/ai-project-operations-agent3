import asyncio
from datetime import date, timedelta

from openai import AsyncOpenAI
from agents import (
    Runner,
    set_default_openai_client,
    set_default_openai_api,
    set_tracing_disabled,
)

from agents_setup import project_orchestrator, evaluator_agent

from tools import (
    get_project_tasks,
    get_team_members,
    get_project_deadline,
    create_task,
    update_task,
    assign_task,
    create_project_comment,
)


# Ollama local model configuration
client = AsyncOpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
    timeout=120.0,
)

set_default_openai_client(client)
set_default_openai_api("chat_completions")
set_tracing_disabled(True)


def normalize_status(status):
    return str(status or "").strip().lower()


def is_completed(task):
    return normalize_status(task.get("status")) == "completed"


def is_blocked(task):
    return normalize_status(task.get("status")) == "blocked"


def is_overdue(task, today=None):
    today = today or date.today()

    if is_completed(task):
        return False

    due_date = task.get("due_date")

    if not due_date:
        return False

    try:
        parsed_date = date.fromisoformat(str(due_date)[:10])
        return parsed_date < today
    except (ValueError, TypeError):
        return False


def build_report(tasks, deadline, team_members):
    today = date.today()
    upcoming_limit = today + timedelta(days=7)

    completed_tasks = [
        task for task in tasks if is_completed(task)
    ]

    overdue_tasks = [
        task for task in tasks if is_overdue(task, today)
    ]

    blocked_tasks = [
        task for task in tasks if is_blocked(task)
    ]

    pending_tasks = [
        task
        for task in tasks
        if normalize_status(task.get("status")) == "pending"
    ]

    upcoming_tasks = []

    for task in tasks:
        if is_completed(task):
            continue

        due_date = task.get("due_date")

        if not due_date:
            continue

        try:
            parsed_date = date.fromisoformat(str(due_date)[:10])

            if today <= parsed_date <= upcoming_limit:
                upcoming_tasks.append(task)

        except (ValueError, TypeError):
            continue

    available_members = [
        member
        for member in team_members
        if member.get("available") == 1
    ]

    lines = [
        "# Project Health Report",
        "",
        f"**Report date:** {today.isoformat()}",
        f"**Total tasks:** {len(tasks)}",
        f"**Completed tasks:** {len(completed_tasks)}",
        f"**Pending tasks:** {len(pending_tasks)}",
        f"**Overdue tasks:** {len(overdue_tasks)}",
        f"**Blocked tasks:** {len(blocked_tasks)}",
        f"**Upcoming deadlines (next 7 days):** {len(upcoming_tasks)}",
        f"**Team members:** {len(team_members)}",
        f"**Available team members:** {len(available_members)}",
        f"**Project deadline:** {deadline.get('project_deadline') or 'Not available'}",
    ]

    if overdue_tasks:
        lines.extend(["", "## Overdue Tasks"])

        for task in overdue_tasks:
            lines.append(
                f"- #{task['id']} {task['title']} "
                f"(due: {task.get('due_date')})"
            )

    if blocked_tasks:
        lines.extend(["", "## Blocked Tasks"])

        for task in blocked_tasks:
            lines.append(
                f"- #{task['id']} {task['title']} "
                f"(priority: {task.get('priority', 'Unknown')})"
            )

    if upcoming_tasks:
        lines.extend(["", "## Upcoming Deadlines"])

        for task in upcoming_tasks:
            lines.append(
                f"- #{task['id']} {task['title']} "
                f"(due: {task.get('due_date')})"
            )

    if not overdue_tasks and not blocked_tasks:
        lines.extend(
            [
                "",
                "## Risk Overview",
                "No overdue or explicitly blocked tasks were found "
                "in the available database records.",
            ]
        )

    return "\n".join(lines)


def get_task_status_summary(tasks, question):
    question = question.lower()

    if any(word in question for word in (
        "overdue",
        "late task",
        "late tasks",
        "past deadline",
        "متأخر",
        "متأخرة",
    )):
        selected = [
            task for task in tasks
            if is_overdue(task)
        ]

        title = "Overdue Tasks"

    elif any(word in question for word in (
        "blocked",
        "blocker",
        "blockers",
        "blocking",
        "معطل",
        "متوقفة",
    )):
        selected = [
            task for task in tasks
            if is_blocked(task)
        ]

        title = "Blocked Tasks"

    elif any(word in question for word in (
        "pending",
        "waiting tasks",
        "not started",
        "معلقة",
        "منتظرة",
    )):
        selected = [
            task for task in tasks
            if normalize_status(task.get("status")) == "pending"
        ]

        title = "Pending Tasks"

    else:
        return None

    if not selected:
        return f"## {title}\n\nNo matching tasks were found."

    lines = [f"## {title}", ""]

    for task in selected:
        lines.append(
            f"- **#{task['id']} — {task['title']}**\n"
            f"  - Status: {task.get('status', 'Unknown')}\n"
            f"  - Priority: {task.get('priority', 'Unknown')}\n"
            f"  - Due date: {task.get('due_date') or 'Not set'}"
        )

    return "\n".join(lines)


def format_task_list(tasks):
    if not tasks:
        return "No tasks found in the project database."

    lines = ["## Project Tasks", ""]

    for task in tasks:
        lines.append(
            f"- **#{task['id']} — {task['title']}**\n"
            f"  - Status: {task.get('status', 'Unknown')}\n"
            f"  - Priority: {task.get('priority', 'Unknown')}\n"
            f"  - Assigned member ID: "
            f"{task.get('assigned_to') or 'Unassigned'}\n"
            f"  - Due date: {task.get('due_date') or 'Not set'}"
        )

    return "\n".join(lines)


def handle_explicit_command(message):
    """
    Handle reliable, structured commands without depending
    on the LLM to interpret action parameters.
    """

    parts = [part.strip() for part in message.split("|")]
    command = parts[0].lower()

    if command == "request_task":
        if len(parts) != 5:
            return (
                "Use this format:\n\n"
                "`request_task | Title | Description | Priority | YYYY-MM-DD`"
            )

        _, title, description, priority, due_date = parts

        result = create_task(
            title=title,
            description=description,
            priority=priority,
            due_date=due_date or None,
        )

        return result

    if command == "update_task":
        if len(parts) != 4:
            return (
                "Use this format:\n\n"
                "`update_task | TASK_ID | FIELD | VALUE`\n\n"
                "Allowed fields: title, description, status, priority, due_date."
            )

        _, task_id, field, value = parts

        try:
            task_id = int(task_id)
        except ValueError:
            return {
                "success": False,
                "message": "Task ID must be a number.",
            }

        field = field.lower()

        allowed_fields = {
            "title",
            "description",
            "status",
            "priority",
            "due_date",
        }

        if field not in allowed_fields:
            return {
                "success": False,
                "message": (
                    "Invalid field. Choose title, description, "
                    "status, priority, or due_date."
                ),
            }

        return update_task(
            task_id=task_id,
            **{field: value or None},
        )

    if command == "assign_task":
        if len(parts) != 3:
            return {
                "success": False,
                "message": (
                    "Use this format: "
                    "`assign_task | TASK_ID | MEMBER_ID`"
                ),
            }

        try:
            task_id = int(parts[1])
            member_id = int(parts[2])
        except ValueError:
            return {
                "success": False,
                "message": "Task ID and member ID must be numbers.",
            }

        return assign_task(task_id, member_id)

    if command == "comment":
        if len(parts) != 3:
            return {
                "success": False,
                "message": (
                    "Use this format: `comment | TASK_ID or blank | Comment`"
                ),
            }

        task_id_text = parts[1]
        comment_text = parts[2]

        try:
            task_id = int(task_id_text) if task_id_text else None
        except ValueError:
            return {
                "success": False,
                "message": "Task ID must be a number or blank.",
            }

        return create_project_comment(
            comment=comment_text,
            task_id=task_id,
        )

    return None


async def run_project_workflow(message):
    message = message.strip()

    if not message:
        return "Please enter a message."

    lowered = message.lower()

    # Handle greetings
    if lowered in {
        "hi",
        "hello",
        "hey",
        "hi there",
        "hello there",
    }:
        return (
            "Hello! I'm your AI Project Operations Agent.\n\n"
            "I can help you review tasks, identify risks, "
            "check deadlines, and request project changes."
        )

    # Handle structured actions deterministically
    action_result = handle_explicit_command(message)

    if action_result is not None:
        return action_result

    # Load current project information
    try:
        tasks, team_members, deadline = await asyncio.gather(
            asyncio.to_thread(get_project_tasks),
            asyncio.to_thread(get_team_members),
            asyncio.to_thread(get_project_deadline),
        )
    except Exception as exc:
        print(f"DATABASE ERROR: {exc}")
        return (
            "I couldn't retrieve project information from the database. "
            "Please check the terminal for the error."
        )

    # Full report
    if any(
        phrase in lowered
        for phrase in (
            "full report",
            "project report",
            "project health",
            "project status report",
            "management report",
            "تقرير المشروع",
            "حالة المشروع",
        )
    ):
        return build_report(tasks, deadline, team_members)

    # List tasks
    if any(
        phrase in lowered
        for phrase in (
            "list all tasks",
            "show all tasks",
            "all project tasks",
            "show tasks",
            "عرض المهام",
            "كل المهام",
        )
    ):
        return format_task_list(tasks)

    # Deterministic status and risk questions
    status_summary = get_task_status_summary(tasks, message)

    if status_summary is not None:
        return status_summary

    # Ask the orchestrator for other questions
    context = (
        f"Today's date: {date.today().isoformat()}\n\n"
        f"Project deadline information:\n{deadline}\n\n"
        f"Team members:\n{team_members}\n\n"
        f"Project tasks:\n{tasks}\n\n"
        f"User request:\n{message}\n\n"
        "Use only the project data provided. "
        "Do not invent task IDs, team members, statuses, or deadlines. "
        "Do not claim an action was completed unless confirmed."
    )

    try:
        result = await Runner.run(
            project_orchestrator,
            input=context,
        )

        response = str(result.final_output)

    except Exception as exc:
        print(f"AGENT ERROR: {exc}")

        return (
            "I couldn't process this question using the local AI model.\n\n"
            "You can still use these supported commands:\n"
            "- `request_task | Title | Description | Priority | YYYY-MM-DD`\n"
            "- `update_task | TASK_ID | FIELD | VALUE`\n"
            "- `assign_task | TASK_ID | MEMBER_ID`\n"
            "- `comment | TASK_ID or blank | Comment`\n\n"
            "For project analysis, try `full report`, `overdue tasks`, "
            "`blocked tasks`, or `list all tasks`."
        )

    # Best-effort evaluator check
    try:
        evaluation = await Runner.run(
            evaluator_agent,
            input=(
                f"Project data:\n{tasks}\n\n"
                f"Proposed response:\n{response}\n\n"
                "Evaluate whether the response is grounded in the data."
            ),
        )

        evaluation_text = str(evaluation.final_output)

        if "REVISE" in evaluation_text.upper():
            print("Evaluator flagged the response for review.")

    except Exception as exc:
        # Evaluator failure must not destroy an otherwise useful answer.
        print(f"EVALUATOR ERROR: {exc}")

    return response