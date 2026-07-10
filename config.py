"""
Конфигурация приложения.
Все настройки вынесены в dataclass для строгой типизации и удобного импорта.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ScreenRegions:
    """Координаты ключевых областей интерфейса."""
    task_area: Tuple[int, int] = (321, 421)        # Основное задание
    answer_area: Tuple[int, int] = (3406, 917)     # Поле ввода ответа
    response_area: Tuple[int, int] = (3302, 842)   # Область копирования ответов
    result_area: Tuple[int, int] = (857, 643)      # Результат проверки


@dataclass(frozen=True)
class Hotkeys:
    """Горячие клавиши управления."""
    copy: str = "alt+1"            # Выполнить одно задание
    input: str = "alt+2"           # Ввод ответа
    clip: str = "alt+3"            # Работа с буфером обмена
    position: str = "p"            # Координаты курсора
    loop_start: str = "alt+r"      # Запустить цикл
    loop_stop: str = "alt+s"       # Остановить цикл
    toggle_submit: str = "alt+q"   # Вкл/выкл автоотправку


@dataclass(frozen=True)
class Timing:
    """Временные задержки (в секундах)."""
    short: float = 0.1
    medium: float = 0.3
    long: float = 1.0


@dataclass(frozen=True)
class Defaults:
    """Значения по умолчанию."""
    fallback_text: str = "неизвестно"   # Текст-заглушка для ввода
    auto_submit: bool = True            # Автоотправка после заполнения


# ── Экспортируемые экземпляры ─────────────────────────────────────
# Используем синглтоны — конфиг неизменяем, создаётся единожды
regions = ScreenRegions()
hotkeys = Hotkeys()
timing = Timing()
defaults = Defaults()

# Для обратной совместимости — алиасы в стиле старых имён
CLICK_AREA_1 = regions.task_area
CLICK_AREA_2 = regions.answer_area
ANSWER_AREA = regions.response_area
RESULT_AREA = regions.result_area

HOTKEY_COPY = hotkeys.copy
HOTKEY_INPUT = hotkeys.input
HOTKEY_CLIP = hotkeys.clip
HOTKEY_POSITION = hotkeys.position
HOTKEY_LOOP = hotkeys.loop_start
HOTKEY_STOP = hotkeys.loop_stop
HOTKEY_PUSH_ANSWER = hotkeys.toggle_submit

TEXT_TO_TYPE = defaults.fallback_text
PUSH_ANSWER = defaults.auto_submit

DELAY_SHORT = timing.short
DELAY_MED = timing.medium
DELAY_LONG = timing.long

# Флаг, управляемый извне (не константа)
check_last_words_in_loop: bool = False


# ── Валидация при импорте ─────────────────────────────────────────
def validate() -> None:
    """
    Проверить корректность конфигурации.
    Вызывается при старте приложения.
    """
    assert all(isinstance(coord, tuple) and len(coord) == 2
               for coord in (regions.task_area, regions.answer_area,
                             regions.response_area, regions.result_area)), \
        "Все координаты должны быть кортежами из двух целых чисел"

    assert timing.short > 0 and timing.medium > 0 and timing.long > 0, \
        "Задержки должны быть положительными"

    assert defaults.fallback_text, "Текст-заглушка не может быть пустым"


if __name__ == "__main__":
    validate()
    print("✅ Конфигурация валидна")
    print(f"   Регионы: {regions}")
    print(f"   Хоткеи:  {hotkeys}")
    print(f"   Тайминги: {timing}")
    print(f"   По умолчанию: {defaults}")