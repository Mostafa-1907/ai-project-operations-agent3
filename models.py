from dataclasses import dataclass
from typing import Optional


@dataclass
class Task:
    id: int
    title: str
    description: str = ""
    assigned_to: Optional[int] = None
    status: str = "Pending"
    priority: str = "Medium"
    due_date: Optional[str] = None


@dataclass
class TeamMember:
    id: int
    name: str
    role: str
    available: bool = True