"""
Тесты для roles.py — управление ролями, оркестратор, конфигурация.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

# Импортируем модуль с патчем SESSIONS_DIR чтобы не трогать реальные файлы
import roles


@pytest.fixture(autouse=True)
def tmp_sessions_dir(tmp_path, monkeypatch):
    """Перенаправляем все файлы ролей/оркестратора во временную директорию."""
    monkeypatch.setattr(roles, "SESSIONS_DIR", tmp_path)
    monkeypatch.setattr(roles, "ROLES_FILE", tmp_path / "roles.json")
    monkeypatch.setattr(roles, "ORCHESTRATOR_FILE", tmp_path / "orchestrator.json")
    return tmp_path


# =========================================
# Роли: ROLES dict
# =========================================

class TestRolesConfig:
    def test_all_roles_defined(self):
        assert set(roles.ROLES.keys()) == {"dev", "assistant", "ontologist", "editor"}

    def test_each_role_has_required_fields(self):
        for key, cfg in roles.ROLES.items():
            assert "name" in cfg, f"{key}: missing name"
            assert "emoji" in cfg, f"{key}: missing emoji"
            assert "work_dir" in cfg, f"{key}: missing work_dir"
            assert "model" in cfg, f"{key}: missing model"
            assert "description" in cfg, f"{key}: missing description"

    def test_default_role_exists(self):
        assert roles.DEFAULT_ROLE in roles.ROLES

    def test_default_role_is_dev(self):
        assert roles.DEFAULT_ROLE == "dev"


# =========================================
# get_current_role / set_current_role
# =========================================

class TestCurrentRole:
    def test_default_role_when_no_file(self):
        assert roles.get_current_role(111) == "dev"

    def test_set_and_get_role(self):
        roles.set_current_role(111, "assistant")
        assert roles.get_current_role(111) == "assistant"

    def test_set_role_persists_between_calls(self):
        roles.set_current_role(111, "editor")
        roles.set_current_role(222, "ontologist")
        assert roles.get_current_role(111) == "editor"
        assert roles.get_current_role(222) == "ontologist"

    def test_set_invalid_role_ignored(self):
        roles.set_current_role(111, "dev")
        roles.set_current_role(111, "nonexistent_role")
        assert roles.get_current_role(111) == "dev"

    def test_different_chat_ids_independent(self):
        roles.set_current_role(111, "assistant")
        roles.set_current_role(222, "editor")
        assert roles.get_current_role(111) == "assistant"
        assert roles.get_current_role(222) == "editor"
        assert roles.get_current_role(333) == "dev"  # default

    def test_corrupted_roles_file(self, tmp_sessions_dir):
        (tmp_sessions_dir / "roles.json").write_text("not json!!!")
        assert roles.get_current_role(111) == "dev"  # graceful fallback


# =========================================
# get_role_config / get_role_label
# =========================================

class TestRoleConfig:
    def test_get_known_role_config(self):
        cfg = roles.get_role_config("dev")
        assert cfg["name"] == "Разработчик"
        assert cfg["emoji"] == "🛠"

    def test_get_unknown_role_returns_default(self):
        cfg = roles.get_role_config("nonexistent")
        assert cfg == roles.ROLES[roles.DEFAULT_ROLE]

    def test_get_role_label_format(self):
        label = roles.get_role_label("assistant")
        assert "🧠" in label
        assert "Ассистент" in label

    def test_get_role_label_unknown_returns_default(self):
        label = roles.get_role_label("bogus")
        assert "🛠" in label  # default = dev


# =========================================
# Оркестратор: is_orchestrator_enabled / set_orchestrator_enabled
# =========================================

class TestOrchestrator:
    def test_enabled_by_default_no_file(self):
        assert roles.is_orchestrator_enabled(111) is True

    def test_set_disabled(self):
        roles.set_orchestrator_enabled(111, False)
        assert roles.is_orchestrator_enabled(111) is False

    def test_set_enabled(self):
        roles.set_orchestrator_enabled(111, False)
        roles.set_orchestrator_enabled(111, True)
        assert roles.is_orchestrator_enabled(111) is True

    def test_per_chat_independence(self):
        roles.set_orchestrator_enabled(111, False)
        roles.set_orchestrator_enabled(222, True)
        assert roles.is_orchestrator_enabled(111) is False
        assert roles.is_orchestrator_enabled(222) is True

    def test_unknown_chat_defaults_to_true(self):
        roles.set_orchestrator_enabled(111, False)
        assert roles.is_orchestrator_enabled(999) is True

    def test_corrupted_orchestrator_file(self, tmp_sessions_dir):
        (tmp_sessions_dir / "orchestrator.json").write_text("{broken json")
        assert roles.is_orchestrator_enabled(111) is True  # graceful fallback

    def test_toggle_orchestrator(self):
        """Проверяем типичный юзкейс: toggle ON->OFF->ON."""
        assert roles.is_orchestrator_enabled(111) is True
        roles.set_orchestrator_enabled(111, False)
        assert roles.is_orchestrator_enabled(111) is False
        roles.set_orchestrator_enabled(111, True)
        assert roles.is_orchestrator_enabled(111) is True


# =========================================
# Взаимодействия: роль + оркестратор
# =========================================

class TestRoleOrchestratorInteraction:
    def test_role_change_does_not_affect_orchestrator(self):
        """Смена роли не должна менять состояние оркестратора."""
        roles.set_orchestrator_enabled(111, True)
        roles.set_current_role(111, "editor")
        assert roles.is_orchestrator_enabled(111) is True

    def test_orchestrator_toggle_does_not_affect_role(self):
        """Переключение оркестратора не должно менять текущую роль."""
        roles.set_current_role(111, "ontologist")
        roles.set_orchestrator_enabled(111, False)
        assert roles.get_current_role(111) == "ontologist"

    def test_multiple_chats_full_scenario(self):
        """Полный сценарий с несколькими чатами."""
        # Чат 1: dev + orchestrator ON
        roles.set_current_role(1, "dev")
        roles.set_orchestrator_enabled(1, True)

        # Чат 2: assistant + orchestrator OFF
        roles.set_current_role(2, "assistant")
        roles.set_orchestrator_enabled(2, False)

        # Чат 3: defaults
        assert roles.get_current_role(1) == "dev"
        assert roles.is_orchestrator_enabled(1) is True
        assert roles.get_current_role(2) == "assistant"
        assert roles.is_orchestrator_enabled(2) is False
        assert roles.get_current_role(3) == "dev"  # default
        assert roles.is_orchestrator_enabled(3) is True  # default
