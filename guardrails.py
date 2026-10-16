from uuid import uuid4

pending_actions = {}


def request_approval(action, params):
    allowed_actions = {
        "create_task",
        "update_task",
        "assign_task",
    }

    if action not in allowed_actions:
        return {
            "success": False,
            "message": "Unsupported action.",
        }

    approval_id = uuid4().hex[:8].upper()

    pending_actions[approval_id] = {
        "action": action,
        "params": params.copy(),
        "approved": False,
    }

    return {
        "success": True,
        "requires_approval": True,
        "approval_id": approval_id,
        "message": (
            f"Approval required. "
            f"Type approve {approval_id} to approve "
            f"or reject {approval_id} to reject."
        ),
    }


def approve_action(approval_id):
    approval_id = str(approval_id).strip().upper()

    request = pending_actions.get(approval_id)

    if request is None:
        return {
            "success": False,
            "message": "Approval request not found or already processed.",
        }

    request["approved"] = True

    return {
        "success": True,
        "message": "Approval recorded.",
    }


def reject_action(approval_id):
    approval_id = str(approval_id).strip().upper()

    request = pending_actions.pop(approval_id, None)

    if request is None:
        return {
            "success": False,
            "message": "Approval request not found or already processed.",
        }

    return {
        "success": True,
        "message": "Action rejected. No changes were made.",
    }


def consume_approved_action(approval_id):
    approval_id = str(approval_id).strip().upper()

    request = pending_actions.get(approval_id)

    if request is None or not request["approved"]:
        return None

    return pending_actions.pop(approval_id)