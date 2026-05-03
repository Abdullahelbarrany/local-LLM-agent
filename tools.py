from typing import Any
from database import query

# ---------------------------------------------------------------------------
# Ollama-compatible tool definitions
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_all_projects",
            "description": "Fetch all projects with their name, status, progress percentage, and team members.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_project_details",
            "description": "Get full details of a single project by its ID, including description and timestamps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer", "description": "The numeric project ID."},
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_project_sprints",
            "description": "List all sprints for a given project, ordered by start date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer", "description": "The numeric project ID."},
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sprint_tasks",
            "description": "Get all tasks belonging to a specific sprint.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sprint_id": {"type": "integer", "description": "The numeric sprint ID."},
                },
                "required": ["sprint_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_project_tasks",
            "description": "Get all tasks for a project across all sprints, sorted by priority then status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer", "description": "The numeric project ID."},
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_team_members",
            "description": "Fetch all team members with their name, role, and email.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tasks_by_assignee",
            "description": "Get all tasks assigned to a specific team member by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "assignee_name": {
                        "type": "string",
                        "description": "The full name of the team member as stored in the tasks table.",
                    },
                },
                "required": ["assignee_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_sprints",
            "description": "List all currently active sprints across all projects, including the project name.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

# ---------------------------------------------------------------------------
# Handler implementations (read-only queries)
# ---------------------------------------------------------------------------

def get_all_projects() -> list[dict]:
    return query(
        "SELECT id, name, description, team_members, progress, status, created_at FROM projects"
    )


def get_project_details(project_id: int) -> dict | None:
    rows = query("SELECT * FROM projects WHERE id = %s", (project_id,))
    return rows[0] if rows else None


def get_project_sprints(project_id: int) -> list[dict]:
    return query(
        "SELECT * FROM sprints WHERE project_id = %s ORDER BY start_date",
        (project_id,),
    )


def get_sprint_tasks(sprint_id: int) -> list[dict]:
    return query(
        "SELECT * FROM tasks WHERE sprint_id = %s ORDER BY priority, status",
        (sprint_id,),
    )


def get_project_tasks(project_id: int) -> list[dict]:
    return query(
        "SELECT * FROM tasks WHERE project_id = %s ORDER BY priority, status",
        (project_id,),
    )


def get_team_members() -> list[dict]:
    return query("SELECT * FROM team_members")


def get_tasks_by_assignee(assignee_name: str) -> list[dict]:
    return query(
        "SELECT * FROM tasks WHERE assigned_to = %s ORDER BY priority, status",
        (assignee_name,),
    )


def get_active_sprints() -> list[dict]:
    return query(
        """
        SELECT s.*, p.name AS project_name
        FROM sprints s
        JOIN projects p ON s.project_id = p.id
        WHERE s.status = 'active'
        ORDER BY s.start_date
        """
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_HANDLERS: dict[str, Any] = {
    "get_all_projects":    lambda a: get_all_projects(),
    "get_project_details": lambda a: get_project_details(a["project_id"]),
    "get_project_sprints": lambda a: get_project_sprints(a["project_id"]),
    "get_sprint_tasks":    lambda a: get_sprint_tasks(a["sprint_id"]),
    "get_project_tasks":   lambda a: get_project_tasks(a["project_id"]),
    "get_team_members":    lambda a: get_team_members(),
    "get_tasks_by_assignee": lambda a: get_tasks_by_assignee(a["assignee_name"]),
    "get_active_sprints":  lambda a: get_active_sprints(),
}


def execute_tool(name: str, args: dict) -> Any:
    handler = _HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"Unknown tool: {name!r}")
    return handler(args)
