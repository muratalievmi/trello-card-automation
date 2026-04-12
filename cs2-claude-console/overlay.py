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
"""

import os
import sys
import threading
import tkinter as tk
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


# --- конфигурация ----------------------------------------------------------

# Haiku 4.5 — самый быстрый ответ, важно во время матча.
# Можно переопределить через переменную окружения CS2_CLAUDE_MODEL.
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
MODEL = os.environ.get("CS2_CLAUDE_MODEL", DEFAULT_MODEL)
MAX_TOKENS = int(os.environ.get("CS2_CLAUDE_MAX_TOKENS", "1024"))

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

SYSTEM_PROMPT = (
    "Ты — внутриигровой ассистент игрока Counter-Strike 2. Отвечай коротко, "
    "без длинных вступлений и markdown-форматирования: оверлей показывает "
    "plain text. Если вопрос про тактику, раскидки, смоуки, флешки, "
    "экономику раундов, сетапы на картах — давай конкретику (карта, сторона, "
    "позиция, прицел по ориентирам). Если вопрос не про игру — отвечай как "
    "обычный ассистент, так же кратко. Язык ответа — тот же, что и у вопроса."
)


# --- логика общения с Claude ----------------------------------------------


class ClaudeChat:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.history = []  # [{"role": "user"|"assistant", "content": str}, ...]

    def stream_reply(self, user_text, on_delta, on_done, on_error):
        """Отправить сообщение и стримить ответ в колбэки.

        Колбэки вызываются из фонового потока — вызывающая сторона должна
        маршрутизировать их в UI-поток через root.after.
        """
        self.history.append({"role": "user", "content": user_text})

        def _run():
            try:
                pieces = []
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
                    messages=self.history,
                ) as stream:
                    for text in stream.text_stream:
                        pieces.append(text)
                        on_delta(text)
                reply = "".join(pieces)
                self.history.append({"role": "assistant", "content": reply})
                on_done()
            except Exception as exc:  # noqa: BLE001
                # откатим последнее сообщение пользователя, чтобы можно было повторить
                if self.history and self.history[-1]["role"] == "user":
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
        self.visible = True
        self._drag = {"x": 0, "y": 0}

        self._build_window()
        self._build_widgets()
        self._bind_keys()
        self._install_global_hotkey()

    # ---- построение окна --------------------------------------------------

    def _build_window(self):
        r = self.root
        r.title(WINDOW_TITLE)
        r.configure(bg=BG)
        r.overrideredirect(True)  # без рамки, без кнопок ОС
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
            state=tk.DISABLED,
            insertbackground=FG_ASSIST,
        )
        self.out.pack(fill=tk.BOTH, expand=True)
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
            "Shift+Enter — перенос  ·  Ctrl+L — сброс  ·  Ctrl+Q — выход\n\n",
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
        # локальный F8 — работает когда фокус в оверлее
        self.root.bind_all("<F8>", lambda e: self.toggle())

    def _install_global_hotkey(self):
        """Глобальный F8, работающий даже когда фокус в CS2."""
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

        def on_delta(chunk):
            self.root.after(0, lambda: self._append("assistant", chunk))

        def on_done():
            self.root.after(0, lambda: self._append("meta", "\n\n"))

        def on_error(msg):
            self.root.after(0, lambda: self._append("err", f"\n[ошибка] {msg}\n\n"))

        self.chat.stream_reply(text, on_delta, on_done, on_error)

    def _append(self, tag, text):
        self.out.configure(state=tk.NORMAL)
        self.out.insert(tk.END, text, tag)
        self.out.see(tk.END)
        self.out.configure(state=tk.DISABLED)

    def reset(self):
        self.chat.reset()
        self.out.configure(state=tk.NORMAL)
        self.out.delete("1.0", tk.END)
        self.out.configure(state=tk.DISABLED)
        self._append("meta", "История очищена.\n\n")

    def toggle(self):
        self.visible = not self.visible
        if self.visible:
            self.root.deiconify()
            self.root.attributes("-topmost", True)
            self.inp.focus_force()
        else:
            self.root.withdraw()

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
