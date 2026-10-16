import gradio as gr

from workflows import run_project_workflow
from tools import approve_pending_action
from guardrails import reject_action
from database import initialize_database


def format_result(result):
    if not isinstance(result, dict):
        return str(result)

    if result.get("requires_approval"):
        approval_id = result.get("approval_id", "")

        return (
            "## ⏳ Approval Required\n\n"
            "Your request is waiting for human approval.\n\n"
            f"**Approval ID:** `{approval_id}`\n\n"
            f"To approve, enter: `approve {approval_id}`\n\n"
            f"To reject, enter: `reject {approval_id}`"
        )

    if result.get("success"):
        lines = ["## ✅ Operation Successful"]

        if result.get("task_id") is not None:
            lines.append(f"**Task ID:** #{result['task_id']}")

        if result.get("comment_id") is not None:
            lines.append(f"**Comment ID:** #{result['comment_id']}")

        if result.get("message"):
            lines.append(result["message"])

        return "\n\n".join(lines)

    return (
        "## ❌ Operation Failed\n\n"
        + result.get("message", "An error occurred.")
    )


async def chat(message, history):
    if not message or not message.strip():
        return "Please enter a message."

    message = message.strip()
    parts = message.split(maxsplit=1)
    command = parts[0].lower()

    # Handle approval commands
    if command in ("approve", "reject"):
        if len(parts) != 2:
            return (
                f"Usage: `{command} APPROVAL_ID`"
            )

        approval_id = parts[1].strip()

        if command == "approve":
            result = approve_pending_action(approval_id)
        else:
            result = reject_action(approval_id)

        return format_result(result)

    try:
        result = await run_project_workflow(message)
        return format_result(result)

    except Exception as exc:
        print(f"CHAT ERROR: {exc}")

        return (
            "## ❌ Something Went Wrong\n\n"
            "The request could not be processed. "
            "Check the terminal for the error details."
        )


demo = gr.ChatInterface(
    fn=chat,
    title="AI Project Operations Agent",
    description=(
        "An AI-powered project management assistant for tasks, "
        "team assignments, deadlines, blockers, and risks.\n\n"
        "**Create task:**\n"
        "`request_task | Title | Description | Priority | YYYY-MM-DD`\n\n"
        "**Update task:**\n"
        "`update_task | TASK_ID | FIELD | VALUE`\n\n"
        "**Assign task:**\n"
        "`assign_task | TASK_ID | MEMBER_ID`\n\n"
        "**Add comment:**\n"
        "`comment | TASK_ID or blank | Comment`\n\n"
        "**Reports:** Try `full report`, `overdue tasks`, "
        "`blocked tasks`, or `list all tasks`."
    ),
)


if __name__ == "__main__":
    initialize_database()
    demo.launch()