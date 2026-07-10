"""
Вспомогательные утилиты приложения.
Логирование, безопасные клики, парсинг ответов.
"""

import re
import sys
import time
import threading
from typing import List, Tuple, Optional

import pyautogui
import pyperclip

from state import state  # Единый объект состояния


# ── Логирование ───────────────────────────────────────────────────
def log(message: str) -> None:
    """
    Вывести сообщение с префиксом [BOT].
    В будущем можно заменить на модуль logging.
    """
    print(f"[BOT] {message}")


# ── Проверка остановки ────────────────────────────────────────────
def check_stop() -> None:
    """
    Проверить, запрошена ли остановка цикла.
    Выбрасывает исключение StopIteration для немедленного выхода из всех вложенных вызовов.
    """
    if state.loop.stop_requested:
        log("⛔ Принудительная остановка")
        raise StopIteration("Остановка по запросу пользователя")


# ── Работа с мышью ────────────────────────────────────────────────
class ClickFailedError(Exception):
    """Исключение: критический провал клика — приложение должно остановиться."""
    pass


def safe_click(
        point: Tuple[int, int],
        retries: int = 3,
        move_duration: float = 0.1,
        click_delay: float = 0.2
) -> bool:
    """
    Безопасный клик с проверкой попадания.

    Делает до retries попыток кликнуть в точку point.
    Если все попытки провалились — выбрасывает ClickFailedError,
    что приводит к полной остановке приложения.

    Args:
        point: Координаты (x, y) для клика.
        retries: Максимальное число попыток.
        move_duration: Длительность перемещения мыши.
        click_delay: Пауза после клика перед проверкой.

    Returns:
        True если клик успешен.

    Raises:
        ClickFailedError: Если все попытки провалились.

    Example:
        safe_click((500, 300))          # успех или остановка
        safe_click((100, 200), retries=5)
    """
    for attempt in range(1, retries + 1):
        pyautogui.moveTo(point, duration=move_duration)
        pyautogui.click()
        time.sleep(click_delay)

        if pyautogui.position() == point:
            return True

        log(f"⚠️ Клик не попал в цель (попытка {attempt}/{retries})")
        time.sleep(0.3)  # Дополнительная пауза перед повтором

    # Все попытки исчерпаны — критическая ошибка
    log(f"⛔ КРИТИЧЕСКАЯ ОШИБКА: клик не сработал за {retries} попыток: {point}")
    log("🛑 Приложение будет остановлено")
    raise ClickFailedError(
        f"Не удалось кликнуть в точку {point} после {retries} попыток"
    )


def move_to(point: Tuple[int, int], duration: float = 0.1) -> bool:
    """
    Переместить курсор в точку с проверкой.

    Returns:
        True если курсор достиг цели.
    """
    pyautogui.moveTo(point, duration=duration)
    time.sleep(0.05)
    return pyautogui.position() == point


# ── Парсинг ответов ───────────────────────────────────────────────
def parse_answers(text: Optional[str]) -> List[str]:
    """
    Извлечь ответы из текста в формате [ответ1][ответ2] или [ответ1, ответ2].

    Поддерживает разделители: запятая, вертикальная черта, точка с запятой.

    Args:
        text: Сырой текст для парсинга. Может быть None.

    Returns:
        Список очищенных строк-ответов. Если text пуст — пустой список.
    """
    if not text:
        return []

    matches = re.findall(r'\[(.*?)\]', text)
    if not matches:
        return []

    results = []
    for match in matches:
        parts = re.split(r'[,|;]', match)
        for part in parts:
            cleaned = part.strip()
            if cleaned:
                results.append(cleaned)

    return results


# ── Работа с буфером обмена ───────────────────────────────────────
def clipboard_get() -> str:
    """Получить текст из буфера обмена."""
    return pyperclip.paste()


def clipboard_set(text: str) -> None:
    """Поместить текст в буфер обмена."""
    pyperclip.copy(text)


# ── Декораторы ────────────────────────────────────────────────────
def stop_safe(func):
    """
    Декоратор, автоматически вызывающий check_stop() перед выполнением функции.
    """
    def wrapper(*args, **kwargs):
        check_stop()
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


# ── Форматирование ────────────────────────────────────────────────
def truncate(text: str, max_length: int = 100) -> str:
    """
    Обрезать строку до указанной длины с многоточием.
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."