"""
Глобальное состояние приложения.
Потокобезопасный менеджер состояния с документированным интерфейсом.
"""

import threading
from dataclasses import dataclass, field


@dataclass
class TaskState:
    """Состояние текущего задания."""
    text: str = ""
    detected_answer: str = ""

    def reset(self) -> None:
        self.text = ""
        self.detected_answer = ""


@dataclass
class LoopState:
    """Состояние цикла обработки."""
    active: bool = False
    stop_requested: bool = False

    @property
    def event(self) -> threading.Event:
        if not hasattr(self, '_event'):
            self._event = threading.Event()
        return self._event

    def start(self) -> None:
        self.active = True
        self.stop_requested = False
        self.event.clear()

    def stop(self) -> None:
        self.active = False
        self.stop_requested = True
        self.event.set()

    def is_running(self) -> bool:
        return self.active and not self.stop_requested


@dataclass
class AppState:
    """Корневое состояние приложения."""
    task: TaskState = field(default_factory=TaskState)
    loop: LoopState = field(default_factory=LoopState)
    auto_submit: bool = True

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def toggle_auto_submit(self) -> bool:
        with self._lock:
            self.auto_submit = not self.auto_submit
            return self.auto_submit

    def reset(self) -> None:
        with self._lock:
            self.task.reset()
            self.loop.stop()


# ── Экземпляр состояния (новый стиль) ────────────────────────────
state = AppState()

# ── Совместимость со старым кодом ─────────────────────────────────
# Прямые ссылки для тех, кто импортирует по-старому.
# В новом коде использовать state.task.text и т.д.

last_task_text = ""          # Устарело, использовать state.task.text
Switch_answer = ""           # Устарело, использовать state.task.detected_answer
running_loop = False         # Устарело, использовать state.loop.active
stop_event = state.loop.event  # Устарело, использовать state.loop.event
PUSH_ANSWER = True           # Устарело, использовать state.auto_submit
check_last_words_in_loop = False  # Устарело, исключено из логики


def _sync_legacy_state():
    """
    Синхронизировать устаревшие переменные с объектом state.
    Вызывать периодически в старом коде, который меняет переменные напрямую.
    В идеале — избавиться от этой функции после полного перехода на state.
    """
    state.task.text = last_task_text
    state.task.detected_answer = Switch_answer
    state.loop.active = running_loop
    state.auto_submit = PUSH_ANSWER