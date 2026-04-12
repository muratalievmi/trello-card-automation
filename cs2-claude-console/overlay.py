"""
CS2 Claude Console — полупрозрачный оверлей для общения с Claude во время игры.

БЕЗОПАСНОСТЬ VAC
    Этот инструмент НЕ внедряется в процесс CS2, НЕ читает память игры,
    НЕ перехватывает Source/Steam DLL и не обращается к игровым файлам.
    Это обычное окно Tkinter "поверх всех" — такое же, как Steam- или
    Discord-оверлей. VAC это не трогает.

ТРЕБОВАНИЯ К CS2
    Запускайте CS2 в режиме "Оконный без рамки" (Fullscreen Windowed),
    иначе эксклюзивный полноэкранный режим будет закрывать любой оверлей.
    В CS2: Настройки → Видео → Режим отображения → "Оконный без рамки".

УСТАНОВКА (Windows)
    1. Поставьте Python 3.10+ с python.org (галка "Add python to PATH").
    2. В папке проекта выполните:
           py -m pip install -r requirements.txt
    3. Задайте ключ API в PowerShell (в той же сессии, где запускаете скрипт):
           $env:ANTHROPIC_API_KEY = "sk-ant-..."
    4. Запуск:
           py overlay.py

ГОРЯЧИЕ КЛАВИШИ
    F8            Показать/скрыть оверлей (глобально, работает даже из CS2)
    Enter         Отправить сообщение
    Shift+Enter   Перенос строки
    Esc           Очистить поле ввода
    Ctrl+L        Очистить историю диалога
    Ctrl+Q        Выйти

WORKSPACE (персональная папка ассистента)
    Claude ведёт твои заметки, задачи, проекты и идеи в песочнице
    %USERPROFILE%\claude-workspace (можно переопределить через
    CS2_CLAUDE_WORKSPACE). В этой папке он умеет:
        - list_directory    — смотреть содержимое
        - read_file         — читать файлы
        - write_file        — создавать и перезаписывать
        - append_to_file    — дописывать в конец
    Выйти за пределы папки Claude физически не может — все пути
    санитизируются перед исполнением. Всё остальное в файловой системе
    ему недоступно. Просто попроси: "добавь в todo встречу в пятницу",
    "что у нас по проекту X", "запиши идею про лендинг", "покажи
    заметки последней встречи" — он сам вызовет нужный инструмент.
"""

import json
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont

try:
    import anthropic
except ImportError:
    sys.stderr.write(
        "Не установлен пакет anthropic. Выполните:\n"
        "    py -m pip install -r requirements.txt\n"
    )
    raise

try:
    import keyboard  # глобальный хоткей F8 (работает, когда фокус в CS2)
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False


# --- Win32 helpers (для кражи foreground у CS2) ----------------------------

IS_WINDOWS = sys.platform.startswith("win")
if IS_WINDOWS:
    import ctypes

    _user32 = ctypes.windll.user32
else:
    _user32 = None


def _win_force_foreground(hwnd):
    """Перевести окно в foreground на Windows, обходя foreground lock.

    Используем AttachThreadInput — прикрепляем поток активного окна
    (CS2) к нашему, после чего SetForegroundWindow для нас становится
    легитимным. В отличие от трюка с keybd_event(Alt), это НЕ генерирует
    реального нажатия клавиши и не может мешать вводу в игре.
    """
    if not IS_WINDOWS or not hwnd:
        return
    try:
        kernel32 = ctypes.windll.kernel32
        current_tid = kernel32.GetCurrentThreadId()
        fg_window = _user32.GetForegroundWindow()
        fg_tid = 0
        if fg_window and fg_window != hwnd:
            fg_tid = _user32.GetWindowThreadProcessId(fg_window, None)

        attached = False
        if fg_tid and fg_tid != current_tid:
            attached = bool(_user32.AttachThreadInput(fg_tid, current_tid, True))

        try:
            _user32.BringWindowToTop(hwnd)
            _user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            _user32.SetForegroundWindow(hwnd)
            _user32.SetFocus(hwnd)
        finally:
            if attached:
                _user32.AttachThreadInput(fg_tid, current_tid, False)
    except Exception:
        pass


def _win_is_foreground(hwnd):
    if not IS_WINDOWS or not hwnd:
        return False
    try:
        return _user32.GetForegroundWindow() == hwnd
    except Exception:
        return False


def _strip_caption(hwnd):
    """Убрать системный title bar через SetWindowLong, СОХРАНИВ окну
    нормальную обработку фокуса в Windows.

    Альтернативный путь — tk.overrideredirect(True) — на Windows ломает
    фокус-цепочку: окно перестаёт получать WM_ACTIVATE, из-за чего Tk
    не роутит keyboard-события в виджеты. Поэтому мы выключаем только
    WS_CAPTION / WS_THICKFRAME / WS_SYSMENU через Win32 напрямую.
    """
    if not IS_WINDOWS or not hwnd:
        return
    GWL_STYLE = -16
    WS_CAPTION = 0x00C00000
    WS_THICKFRAME = 0x00040000
    WS_SYSMENU = 0x00080000
    WS_MINIMIZEBOX = 0x00020000
    WS_MAXIMIZEBOX = 0x00010000
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOZORDER = 0x0004
    SWP_FRAMECHANGED = 0x0020
    try:
        style = _user32.GetWindowLongW(hwnd, GWL_STYLE)
        style &= ~(
            WS_CAPTION
            | WS_THICKFRAME
            | WS_SYSMENU
            | WS_MINIMIZEBOX
            | WS_MAXIMIZEBOX
        )
        _user32.SetWindowLongW(hwnd, GWL_STYLE, style)
        _user32.SetWindowPos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
        )
    except Exception:
        pass


# --- конфигурация ----------------------------------------------------------

# Haiku 4.5 — самый быстрый ответ, важно во время матча.
# Можно переопределить через переменную окружения CS2_CLAUDE_MODEL.
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
MODEL = os.environ.get("CS2_CLAUDE_MODEL", DEFAULT_MODEL)
MAX_TOKENS = int(os.environ.get("CS2_CLAUDE_MAX_TOKENS", "2048"))
MAX_AGENT_TURNS = int(os.environ.get("CS2_CLAUDE_MAX_TURNS", "8"))

# Рабочая папка-песочница. Все инструменты ограничены ею — выйти нельзя.
# Можно переопределить через CS2_CLAUDE_WORKSPACE.
WORKSPACE = Path(
    os.environ.get("CS2_CLAUDE_WORKSPACE", Path.home() / "claude-workspace")
).expanduser().resolve()
WORKSPACE.mkdir(parents=True, exist_ok=True)

WINDOW_TITLE = "CS2 Claude Console"
WINDOW_W = 520
WINDOW_H = 380
DEFAULT_ALPHA = 0.85

BG = "#0b0b0f"
BG_TITLE = "#151520"
BG_INPUT = "#111118"
FG_USER = "#9cd7ff"
FG_ASSIST = "#e6e6c8"
FG_META = "#7a7a7a"
FG_ERR = "#ff6b6b"

SYSTEM_PROMPT = f"""Ты — персональный ассистент по бизнесу и личным делам. Помогаешь пользователю вести проекты, задачи, заметки, идеи, планы и решения. Общаешься через полупрозрачный оверлей, открытый поверх его рабочих приложений.

ФОРМАТ ОТВЕТОВ
- Коротко и по делу. Без длинных вступлений, без воды, без повторения вопроса.
- Plain text, без markdown: оверлей не рендерит ** _ # ` и т.п.
- Язык ответа — тот же, что у пользователя.
- НЕ представляйся и не рассказывай о себе, если об этом явно не спросили. Сразу переходи к сути.

РАБОЧАЯ ПАПКА (WORKSPACE)
У тебя есть собственная папка-песочница: {WORKSPACE}
Это твоё постоянное хранилище, переживающее перезапуски сессии. Твоя память между разговорами живёт только там — всё остальное из файловой системы тебе недоступно.

ДОСТУПНЫЕ ИНСТРУМЕНТЫ
- list_directory(path)            — посмотреть содержимое папки ('.' = корень)
- read_file(path)                 — прочитать файл
- write_file(path, content)       — создать или перезаписать файл
- append_to_file(path, content)   — дописать в конец файла

КАК ОРГАНИЗОВАН WORKSPACE
Структурируй файлы по смыслу, не сваливай всё в один. Разумная раскладка:
- todo.md                 — текущие задачи
- ideas.md                — копилка идей
- projects/<name>.md      — отдельный файл на каждый проект
- meetings/YYYY-MM-DD.md  — заметки со встреч с датой в имени
- contacts.md             — люди и их контакты
- journal/YYYY-MM.md      — дневник/лог по месяцам
- decisions.md            — принятые решения и их обоснование
- finances.md             — финансовые пометки
Это дефолт, а не догма — заводи свои файлы и папки, когда нужна новая тема.

КОГДА ИСПОЛЬЗОВАТЬ ИНСТРУМЕНТЫ
- Пользователь просит запомнить / записать / сохранить → write_file или append_to_file (append, если это дополнение к уже существующему файлу).
- Пользователь спрашивает "что у нас по...", "что я записывал про...", "покажи заметки" → СНАЧАЛА list_directory, чтобы понять что вообще есть, потом read_file нужного.
- Перед тем как сказать "у нас нет файла X" или "я этого не помню" — ОБЯЗАТЕЛЬНО проверь через list_directory и read_file. Не полагайся на память текущей сессии: файлы переживают её, ты — нет.
- НЕ спрашивай разрешения перед чтением или записью в workspace. Это твоё пространство, пользователь тебя для этого и позвал.
- После вызова инструмента КРАТКО подтверди ("Записал в todo.md", "Добавил в ideas.md"), не пересказывай весь контент файла.

ТОН
Профессиональный, но не формальный. Дружелюбный, но без воды. Если пользователь просит совета — давай прямую рекомендацию, а не перечень опций. Если вопрос правда неоднозначный — задай ОДИН уточняющий вопрос, а не пять."""


# --- инструменты для Claude (песочница в WORKSPACE) ------------------------

TOOLS_SCHEMA = [
    {
        "name": "list_directory",
        "description": (
            "Показать содержимое папки внутри рабочего пространства. "
            "Используй '.' для корня workspace. Возвращает по одной строке "
            "на элемент с префиксом 'd' (папка) или 'f' (файл)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Относительный путь внутри workspace. '.' = корень.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "read_file",
        "description": "Прочитать текстовый файл из workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Относительный путь к файлу внутри workspace.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Создать или перезаписать файл в workspace. Автоматически "
            "создаёт недостающие родительские папки."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Относительный путь."},
                "content": {"type": "string", "description": "Новое содержимое файла."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "append_to_file",
        "description": (
            "Дописать текст в конец файла в workspace. Если файла нет — "
            "создаст. Полезно для логов, заметок, todo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Относительный путь."},
                "content": {"type": "string", "description": "Что дописать."},
            },
            "required": ["path", "content"],
        },
    },
]


def _safe_path(rel):
    """Разрешить относительный путь в WORKSPACE, кидая ошибку если он
    пытается уйти наружу (через .., абсолютный путь и т.п.).
    """
    if rel is None:
        raise ValueError("путь не задан")
    rel = str(rel).strip()
    if not rel or rel in (".", "./"):
        return WORKSPACE
    candidate = (WORKSPACE / rel).resolve()
    try:
        candidate.relative_to(WORKSPACE)
    except ValueError:
        raise ValueError(f"путь вне workspace: {rel}")
    return candidate


def _execute_tool(name, args):
    """Выполнить инструмент и вернуть строку-результат для модели."""
    if name == "list_directory":
        p = _safe_path(args.get("path", "."))
        if not p.exists():
            return f"[не найдено] {p.relative_to(WORKSPACE) if p != WORKSPACE else '.'}"
        if not p.is_dir():
            return f"[не папка] {p.relative_to(WORKSPACE)}"
        items = []
        for child in sorted(p.iterdir(), key=lambda c: (not c.is_dir(), c.name.lower())):
            kind = "d" if child.is_dir() else "f"
            size = "" if child.is_dir() else f"  ({child.stat().st_size}b)"
            items.append(f"{kind} {child.name}{size}")
        rel = "." if p == WORKSPACE else str(p.relative_to(WORKSPACE))
        header = f"{rel}:"
        return header + "\n" + ("\n".join(items) if items else "(пусто)")

    if name == "read_file":
        p = _safe_path(args["path"])
        if not p.exists():
            return f"[не найдено] {args['path']}"
        if not p.is_file():
            return f"[не файл] {args['path']}"
        try:
            return p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"[бинарный файл, не читается как текст] {args['path']}"

    if name == "write_file":
        p = _safe_path(args["path"])
        p.parent.mkdir(parents=True, exist_ok=True)
        content = args.get("content", "")
        p.write_text(content, encoding="utf-8")
        return f"[записано] {p.relative_to(WORKSPACE)} ({len(content)} символов)"

    if name == "append_to_file":
        p = _safe_path(args["path"])
        p.parent.mkdir(parents=True, exist_ok=True)
        content = args.get("content", "")
        with p.open("a", encoding="utf-8") as f:
            f.write(content)
        return f"[дописано] {p.relative_to(WORKSPACE)} (+{len(content)} символов)"

    raise ValueError(f"неизвестный инструмент: {name}")


# --- логика общения с Claude ----------------------------------------------


class ClaudeChat:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.history = []  # [{"role": "user"|"assistant", "content": [...blocks...]}, ...]

    def agentic_turn(self, user_text, on_text, on_tool_call, on_tool_result, on_done, on_error):
        """Один ход пользователя → цикл: стрим текста + вызовы инструментов,
        пока Claude не остановится на end_turn (или max_turns).

        Все колбэки вызываются из фонового потока. Вызывающая сторона
        маршрутизирует их в UI-поток через root.after.
        """
        self.history.append({"role": "user", "content": user_text})

        def _run():
            try:
                for turn in range(MAX_AGENT_TURNS):
                    assistant_blocks = []
                    current = None  # текущий content block, который собираем

                    with self.client.messages.stream(
                        model=MODEL,
                        max_tokens=MAX_TOKENS,
                        system=[
                            {
                                "type": "text",
                                "text": SYSTEM_PROMPT,
                                "cache_control": {"type": "ephemeral"},
                            }
                        ],
                        tools=TOOLS_SCHEMA,
                        messages=self.history,
                    ) as stream:
                        for event in stream:
                            et = getattr(event, "type", None)
                            if et == "content_block_start":
                                cb = event.content_block
                                if cb.type == "text":
                                    current = {"type": "text", "text": ""}
                                elif cb.type == "tool_use":
                                    current = {
                                        "type": "tool_use",
                                        "id": cb.id,
                                        "name": cb.name,
                                        "_json": "",  # собирается из partial_json дельт
                                    }
                            elif et == "content_block_delta":
                                d = event.delta
                                if getattr(d, "type", None) == "text_delta":
                                    if current and current["type"] == "text":
                                        current["text"] += d.text
                                        on_text(d.text)
                                elif getattr(d, "type", None) == "input_json_delta":
                                    if current and current["type"] == "tool_use":
                                        current["_json"] += d.partial_json
                            elif et == "content_block_stop":
                                if current is None:
                                    continue
                                if current["type"] == "tool_use":
                                    raw = current.pop("_json") or "{}"
                                    try:
                                        current["input"] = json.loads(raw)
                                    except json.JSONDecodeError:
                                        current["input"] = {}
                                assistant_blocks.append(current)
                                current = None

                    # Сохраняем ход ассистента целиком (текст + tool_use блоки)
                    self.history.append({"role": "assistant", "content": assistant_blocks})

                    tool_uses = [b for b in assistant_blocks if b["type"] == "tool_use"]
                    if not tool_uses:
                        on_done()
                        return

                    # Выполняем все инструменты этого хода и отправляем результаты
                    tool_results = []
                    for tu in tool_uses:
                        on_tool_call(tu["name"], tu.get("input", {}))
                        try:
                            result = _execute_tool(tu["name"], tu.get("input", {}))
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tu["id"],
                                    "content": result,
                                }
                            )
                            on_tool_result(tu["name"], True, result)
                        except Exception as exc:  # noqa: BLE001
                            msg = f"{type(exc).__name__}: {exc}"
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tu["id"],
                                    "content": msg,
                                    "is_error": True,
                                }
                            )
                            on_tool_result(tu["name"], False, msg)

                    self.history.append({"role": "user", "content": tool_results})
                    # следующий виток цикла — модель увидит результаты и продолжит

                # дошли до лимита turns — всё равно считаем завершённым
                on_done()
            except Exception as exc:  # noqa: BLE001
                # откатим последнее сообщение пользователя, чтобы можно было повторить
                if self.history and self.history[-1]["role"] == "user" and isinstance(
                    self.history[-1]["content"], str
                ):
                    self.history.pop()
                on_error(f"{type(exc).__name__}: {exc}")

        threading.Thread(target=_run, daemon=True).start()

    def reset(self):
        self.history.clear()


# --- UI --------------------------------------------------------------------


class OverlayApp:
    def __init__(self, root):
        self.root = root
        self.chat = ClaudeChat()
        self._drag = {"x": 0, "y": 0}
        self._hwnd = 0

        self._build_window()
        self._build_widgets()
        self._bind_keys()
        self._install_global_hotkey()

        # Реализуем окно, срежем системный title bar через Win32 (не через
        # overrideredirect — он ломает фокус на Windows), потом покажем.
        self.root.update_idletasks()
        try:
            self._hwnd = self.root.winfo_id()
            _strip_caption(self._hwnd)
        except Exception:
            self._hwnd = 0
        self.root.deiconify()
        self.root.after(30, self.inp.focus_force)

    # ---- построение окна --------------------------------------------------

    def _build_window(self):
        r = self.root
        r.title(WINDOW_TITLE)
        r.configure(bg=BG)
        # Прячем до тех пор, пока не срежем title bar через Win32,
        # чтобы нативная рамка не мелькнула при старте.
        r.withdraw()
        r.attributes("-topmost", True)
        r.attributes("-alpha", DEFAULT_ALPHA)
        sw = r.winfo_screenwidth()
        x = sw - WINDOW_W - 20
        y = 60
        r.geometry(f"{WINDOW_W}x{WINDOW_H}+{x}+{y}")

    def _build_widgets(self):
        mono = tkfont.Font(family="Consolas", size=10)
        mono_family = mono.actual("family")

        # заголовок — зона перетаскивания + крестик
        title = tk.Frame(self.root, bg=BG_TITLE, height=22)
        title.pack(fill=tk.X, side=tk.TOP)
        title.pack_propagate(False)

        lbl = tk.Label(
            title,
            text=f"CS2 · Claude  [{MODEL}]",
            bg=BG_TITLE,
            fg=FG_META,
            font=(mono_family, 9, "bold"),
            padx=8,
        )
        lbl.pack(side=tk.LEFT)

        btn_close = tk.Label(
            title,
            text="×",
            bg=BG_TITLE,
            fg=FG_META,
            font=(mono_family, 12, "bold"),
            padx=10,
            cursor="hand2",
        )
        btn_close.pack(side=tk.RIGHT)
        btn_close.bind("<Button-1>", lambda e: self.quit())

        for widget in (title, lbl):
            widget.bind("<Button-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)

        # область вывода
        # state=NORMAL (а не DISABLED) — иначе Tk блокирует не только ввод,
        # но и выделение текста мышью, и ничего нельзя скопировать.
        # Редактирование глушим биндингом <Key> ниже; мигающий курсор
        # прячем через insertwidth=0. Явные bg/fg выделения — чтобы оно
        # было видно на тёмном фоне (дефолт на Windows почти сливается).
        self.out = tk.Text(
            self.root,
            bg=BG,
            fg=FG_ASSIST,
            font=mono,
            wrap=tk.WORD,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            padx=10,
            pady=8,
            insertwidth=0,
            cursor="xterm",
            selectbackground="#3d5a7c",
            selectforeground="#ffffff",
            exportselection=True,
        )
        self.out.pack(fill=tk.BOTH, expand=True)

        # Блокируем редактирование, но явно включаем шорткаты копирования.
        # Специфичные биндинги (<Control-c> и т.п.) перекрывают общий <Key>
        # по правилам специфичности Tk в пределах одного тега.
        self.out.bind("<Key>", lambda e: "break")
        self.out.bind("<Control-c>", self._out_copy_selection)
        self.out.bind("<Control-C>", self._out_copy_selection)
        self.out.bind("<Control-Insert>", self._out_copy_selection)
        self.out.bind("<Control-a>", self._out_select_all)
        self.out.bind("<Control-A>", self._out_select_all)
        self.out.bind("<Button-3>", self._show_out_ctxmenu)

        # Контекстное меню по правой кнопке — как в любом нормальном текст-поле.
        self._out_ctxmenu = tk.Menu(
            self.root, tearoff=0, bg=BG_INPUT, fg="#ffffff",
            activebackground="#3d5a7c", activeforeground="#ffffff",
            borderwidth=0,
        )
        self._out_ctxmenu.add_command(
            label="Копировать      Ctrl+C", command=self._out_copy_selection
        )
        self._out_ctxmenu.add_command(
            label="Выделить всё    Ctrl+A", command=self._out_select_all
        )

        self.out.tag_configure("user", foreground=FG_USER)
        self.out.tag_configure("assistant", foreground=FG_ASSIST)
        self.out.tag_configure("meta", foreground=FG_META)
        self.out.tag_configure("err", foreground=FG_ERR)

        sep = tk.Frame(self.root, bg="#22222c", height=1)
        sep.pack(fill=tk.X)

        # поле ввода
        self.inp = tk.Text(
            self.root,
            bg=BG_INPUT,
            fg="#ffffff",
            font=mono,
            height=3,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            padx=10,
            pady=6,
            insertbackground="#ffffff",
            wrap=tk.WORD,
        )
        self.inp.pack(fill=tk.X, side=tk.BOTTOM)
        self.inp.focus_set()

        self._append(
            "meta",
            "F8 — показать/скрыть  ·  Enter — отправить  ·  "
            "Shift+Enter — перенос  ·  Ctrl+L — сброс  ·  Ctrl+Q — выход\n"
            f"workspace: {WORKSPACE}\n\n",
        )

    # ---- клавиши ---------------------------------------------------------

    def _bind_keys(self):
        # Enter отправляет, Shift+Enter — обычный перенос строки
        self.inp.bind("<Return>", self._on_enter)
        self.inp.bind("<Shift-Return>", lambda e: None)
        self.inp.bind("<Escape>", lambda e: (self.inp.delete("1.0", tk.END), "break"))
        self.root.bind_all("<Control-l>", lambda e: self.reset())
        self.root.bind_all("<Control-L>", lambda e: self.reset())
        self.root.bind_all("<Control-q>", lambda e: self.quit())
        self.root.bind_all("<Control-Q>", lambda e: self.quit())
        # F8 как локальный fallback — работает, только если keyboard не поставился.
        # При активном глобальном хоткее этот bind не будет вызываться (suppress=True).
        self.root.bind_all("<F8>", lambda e: self.toggle())

    def _install_global_hotkey(self):
        """Глобальный F8, работающий даже когда фокус в CS2.

        БЕЗ suppress=True — с suppress на некоторых Windows-конфигурациях
        low-level keyboard hook глушит ввод во всех приложениях сразу.
        Пусть F8 летит и в CS2 тоже: если у тебя на F8 что-то забинжено
        в игре — ребинди на неиспользуемую клавишу через консоль CS2.
        """
        if not HAS_KEYBOARD:
            self._append(
                "meta",
                "[keyboard не установлен — F8 будет работать только в оверлее]\n\n",
            )
            return
        try:
            keyboard.add_hotkey("f8", lambda: self.root.after(0, self.toggle))
        except Exception as exc:  # noqa: BLE001
            self._append("meta", f"[глобальный F8 недоступен: {exc}]\n\n")

    # ---- перетаскивание --------------------------------------------------

    def _drag_start(self, event):
        self._drag["x"] = event.x_root - self.root.winfo_x()
        self._drag["y"] = event.y_root - self.root.winfo_y()

    def _drag_move(self, event):
        new_x = event.x_root - self._drag["x"]
        new_y = event.y_root - self._drag["y"]
        self.root.geometry(f"+{new_x}+{new_y}")

    # ---- события ---------------------------------------------------------

    def _on_enter(self, event):
        # Shift-маска в tkinter — бит 0x0001
        if event.state & 0x0001:
            return  # дать стандартному обработчику вставить перенос
        text = self.inp.get("1.0", tk.END).strip()
        if not text:
            return "break"
        self.inp.delete("1.0", tk.END)
        self.send(text)
        return "break"

    def send(self, text):
        self._append("user", f"» {text}\n")

        def on_text(chunk):
            self.root.after(0, lambda: self._append("assistant", chunk))

        def on_tool_call(name, args):
            # короткая превью-строка аргументов, чтобы пользователь видел что делается
            preview = ""
            if "path" in args:
                preview = args["path"]
                if "content" in args:
                    n = len(args["content"])
                    preview += f", {n} симв."
            line = f"\n→ {name}({preview})"
            self.root.after(0, lambda: self._append("meta", line))

        def on_tool_result(name, ok, result):
            mark = " ✓" if ok else f" ✗ {result}"
            self.root.after(0, lambda: self._append("meta", mark + "\n"))

        def on_done():
            self.root.after(0, lambda: self._append("meta", "\n\n"))

        def on_error(msg):
            self.root.after(0, lambda: self._append("err", f"\n[ошибка] {msg}\n\n"))

        self.chat.agentic_turn(
            text, on_text, on_tool_call, on_tool_result, on_done, on_error
        )

    def _append(self, tag, text):
        self.out.insert(tk.END, text, tag)
        self.out.see(tk.END)

    def _out_copy_selection(self, event=None):
        """Скопировать выделение из self.out в системный буфер обмена."""
        try:
            text = self.out.get(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            return "break"  # ничего не выделено
        if not text:
            return "break"
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        # update() нужен, чтобы буфер был доступен другим приложениям
        # после закрытия/скрытия Tk-окна — иначе Windows иногда держит
        # clipboard только пока жив владелец.
        self.root.update()
        return "break"

    def _out_select_all(self, event=None):
        self.out.tag_remove(tk.SEL, "1.0", tk.END)
        self.out.tag_add(tk.SEL, "1.0", tk.END)
        return "break"

    def _show_out_ctxmenu(self, event):
        try:
            self._out_ctxmenu.tk_popup(event.x_root, event.y_root)
        finally:
            self._out_ctxmenu.grab_release()

    def reset(self):
        self.chat.reset()
        self.out.delete("1.0", tk.END)
        self._append("meta", "История очищена.\n\n")

    def toggle(self):
        """Умный toggle как в консоли CS2.

        - Окно скрыто        → показать, забрать foreground, фокус в input.
        - Видимо, но не в fg → забрать foreground, фокус в input.
        - Видимо и в fg      → спрятать (фокус вернётся к CS2 автоматически).
        """
        hidden = self.root.state() == "withdrawn"
        if hidden or not _win_is_foreground(self._hwnd):
            self._show_and_focus()
        else:
            self.root.withdraw()

    def _show_and_focus(self):
        r = self.root
        r.deiconify()
        r.attributes("-topmost", True)
        r.lift()
        r.update_idletasks()
        # освежим HWND — на всякий случай, если Tk пересоздал окно
        try:
            self._hwnd = r.winfo_id()
        except Exception:
            pass
        _win_force_foreground(self._hwnd)
        r.focus_force()
        # Небольшая задержка: focus на виджет надо ставить после того,
        # как SetForegroundWindow реально перекинул активное окно,
        # иначе Tk может "откатить" фокус при следующем событии.
        r.after(30, self.inp.focus_force)

    def quit(self):
        if HAS_KEYBOARD:
            try:
                keyboard.unhook_all()
            except Exception:
                pass
        self.root.destroy()


# --- точка входа -----------------------------------------------------------


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.stderr.write(
            "ANTHROPIC_API_KEY не задан. В PowerShell выполните:\n"
            '    $env:ANTHROPIC_API_KEY = "sk-ant-..."\n'
            "и запустите скрипт снова в той же сессии.\n"
        )
        sys.exit(1)

    root = tk.Tk()
    app = OverlayApp(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.quit()


if __name__ == "__main__":
    main()
