import json
from pathlib import Path

SESSIONS_DIR = Path.home() / ".claude-tg-sessions"
ROLES_FILE = SESSIONS_DIR / "roles.json"

ROLES = {
    "dev": {
        "name": "Разработчик",
        "emoji": "🛠",
        "work_dir": "/home/ec2-user/agent",
        "model": "",  # default = Opus 4.6
        "description": "Код, сервер, деплой, проекты",
    },
    "assistant": {
        "name": "Ассистент",
        "emoji": "🧠",
        "work_dir": "/home/ec2-user/assistant",
        "model": "claude-sonnet-4-5-20250929",
        "description": "Планы, анализ, советы, личные задачи",
    },
    "ontologist": {
        "name": "Методист онтологий",
        "emoji": "🔬",
        "work_dir": "/home/ec2-user/ontologist",
        "model": "",  # Opus 4.6 — нужна глубина мышления
        "description": "Онтологический редизайн, ΔELTA методология",
    },
    "editor": {
        "name": "Редактор",
        "emoji": "✍️",
        "work_dir": "/home/ec2-user/editor",
        "model": "claude-sonnet-4-5-20250929",  # Sonnet — быстрая проверка текстов
        "description": "Редактура русского текста по Мильчину и Чельцовой",
    },
}

DEFAULT_ROLE = "dev"

# --- Оркестратор (автомаршрутизация) ---
ORCHESTRATOR_FILE = SESSIONS_DIR / "orchestrator.json"

def is_orchestrator_enabled(chat_id: int) -> bool:
    if ORCHESTRATOR_FILE.exists():
        try:
            data = json.loads(ORCHESTRATOR_FILE.read_text())
            return data.get(str(chat_id), True)
        except:
            pass
    return True  # включён по умолчанию

def set_orchestrator_enabled(chat_id: int, enabled: bool):
    data = {}
    if ORCHESTRATOR_FILE.exists():
        try:
            data = json.loads(ORCHESTRATOR_FILE.read_text())
        except:
            pass
    data[str(chat_id)] = enabled
    ORCHESTRATOR_FILE.write_text(json.dumps(data))

def _load_roles() -> dict:
    if ROLES_FILE.exists():
        try:
            return json.loads(ROLES_FILE.read_text())
        except:
            pass
    return {}

def _save_roles(data: dict):
    ROLES_FILE.write_text(json.dumps(data))

def get_current_role(chat_id: int) -> str:
    data = _load_roles()
    return data.get(str(chat_id), DEFAULT_ROLE)

def set_current_role(chat_id: int, role: str):
    if role not in ROLES:
        return
    data = _load_roles()
    data[str(chat_id)] = role
    _save_roles(data)

def get_role_config(role: str) -> dict:
    return ROLES.get(role, ROLES[DEFAULT_ROLE])

def get_role_label(role: str) -> str:
    cfg = get_role_config(role)
    return f"{cfg['emoji']} {cfg['name']}"
