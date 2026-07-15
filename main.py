"""
Основной модуль автоматизации задач Квоки.
Архитектура: хоткеи → экшены → хелперы, минимум глобального состояния.
"""

import ctypes
import sys
import threading
import time
from typing import Optional, Dict, Tuple, Callable

import keyboard
import pyautogui
import pyperclip

from config import (
    CLICK_AREA_1, CLICK_AREA_2, ANSWER_AREA,
    DELAY_SHORT, DELAY_LONG, TEXT_TO_TYPE,
    HOTKEY_COPY, HOTKEY_POSITION, HOTKEY_LOOP,
    HOTKEY_STOP, HOTKEY_PUSH_ANSWER,
)
from state import state
from utils import (
    log, check_stop, safe_click, parse_answers,
    ClickFailedError, truncate, clipboard_get, clipboard_set
)

# ── Глобальные константы ──────────────────────────────────────────
pyautogui.PAUSE = 0.05
pyautogui.FAILSAFE = True

# ── Типы ответов ──────────────────────────────────────────────────
# Карты ответов — неизменяемые словари для быстрого поиска O(1)
DEFAULT_ANSWERS: Dict[str, int] = {
    "да": 2,
    "Да": 2,
    "первое": 2,
    "нет": 3,
    "Нет": 3,
    "второе": 3,
    "нельзя выбрать лучший": 4,
    "полностью одинаковые товары или с небольшими отличиями": 4,
    "совершенно разные товары или данных недостаточно для принятия решения": 5,
}

CLOTHES_ANSWERS: Dict[str, int] = {
    "полностью идентичные товары": 8,
    "различные варианты одной и той же модели одного бренда": 9,
    "полностью отличаются": 10,
    "недостаточно информации": 11,
    "категория товара неверна": 12,
    "указан 1 цвет": 13,
    "но указано несколько цветов": 14,
    "цвет не указан": 15,
    "указан 1 размер": 16,
    "но указано несколько размеров": 17,
    "размер не указан": 18,
}

MAKEUP_ANSWERS: Dict[str, int] = {
    "Оттенок товару нужен": 3,
    "Оттенок товару не нужен": 4,
}

# Фразы, которые не считаются новым текстом при ожидании
SKIP_PHRASES: Tuple[str, ...] = (
    "Возникли сложности с заполнением характеристики? Нужны пояснения?",
    "Нужны пояснения?",
)


# ── Утилиты ввода ─────────────────────────────────────────────────
def tap_tab(count: int = 1, delay: float = 0.15) -> None:
    """Нажать Tab count раз с задержкой."""
    for _ in range(count):
        keyboard.press_and_release("tab")
        time.sleep(delay)


def tap_space(delay: float = 0.2) -> None:
    """Нажать пробел."""
    keyboard.press_and_release("space")
    time.sleep(delay)


def submit() -> None:
    """Ctrl+Enter для отправки формы."""
    keyboard.press_and_release("ctrl+enter")


def focus() -> None:
    """Клик для фокуса на элементе."""
    pyautogui.click()
    time.sleep(DELAY_SHORT)


def copy_selected() -> str:
    """Ctrl+A, Ctrl+C → вернуть текст из буфера."""
    keyboard.press_and_release("ctrl+a")
    time.sleep(0.2)
    keyboard.press_and_release("ctrl+c")
    time.sleep(0.3)
    return pyperclip.paste()


# ── Раскладка ─────────────────────────────────────────────────────
def ensure_english_layout() -> None:
    """Принудительно переключить раскладку на EN, если сейчас RU."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    hwnd = user32.GetForegroundWindow()
    thread_id = user32.GetWindowThreadProcessId(hwnd, 0)
    layout_id = user32.GetKeyboardLayout(thread_id)
    if (layout_id & 0xFFFF) == 0x0419:  # Русская раскладка
        log("🔤 Переключаю раскладку на EN")
        pyautogui.hotkey("alt", "shift")
        time.sleep(0.3)


# ── Определение типа задания ─────────────────────────────────────
def is_priority_task(text: str) -> bool:
    """Является ли текст приоритетным заданием."""
    return "приоритетное задание" in text.lower()


def is_receipt_task(text: str) -> bool:
    """Задание связано с чеками."""
    return any(word in text.lower() for word in ("чек", "чеки"))


def is_clothing_task() -> bool:
    """Текущее задание — матчинг одежды."""
    return "Матчинг. одежда и обувь" in state.task.text

def is_narushenia_task() -> bool:
    """Текущее задание — матчинг одежды."""
    return "Проверь пост на наличие нарушений" in state.task.text

def is_makeup_task() -> bool:
    """Текущее задание — оттенки косметики."""
    return "Задача: найти и заполнить номера и названия оттенков" in state.task.text


# ── Ожидания ──────────────────────────────────────────────────────
def wait_for_new_task(timeout: int = 15) -> str:
    """
    Ждать появления нового текста задания (отличного от предыдущего).
    Возвращает текст задания или пустую строку по таймауту.
    """
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        check_stop()
        current = copy_selected().strip()
        if current and current != state.task.text:
            state.task.text = current
            log("🆕 Новое задание получено")
            return current
        log("⏳ Ожидание нового задания...")
        time.sleep(1)

    log("⛔ Таймаут ожидания нового задания")
    return pyperclip.paste()


def wait_for_new_text(area: Tuple[int, int], timeout: int = 60) -> bool:
    """
    Кликать в область, нажимать пробел, пока не появится новый значимый текст.
    Возвращает True, если ответ распознан.
    """
    deadline = time.monotonic() + timeout
    previous = pyperclip.paste()

    while time.monotonic() < deadline:
        check_stop()
        safe_click(area)
        tap_space()

        current = pyperclip.paste()
        if current == previous or not current.strip():
            time.sleep(0.5)
            continue

        # Игнорируем системные сообщения
        if any(phrase in current for phrase in SKIP_PHRASES):
            previous = current
            time.sleep(0.5)
            continue

        # Пытаемся распознать ответ
        result = _detect_makeup_answer(current)
        if result is not None:
            state.task.detected_answer = str(result)
            log(f"🎯 Найден ответ: {state.task.detected_answer}")
            return True

        result2 = _detect_narushenia_answer(current)
        if result2 is not None:
            state.task.detected_answer = str(result2)
            log(f"🎯 Найден ответ: {state.task.detected_answer}")
            return True

        log(f"❓ Не удалось распознать ответ: {current}")
        time.sleep(0.5)

    log("⛔ Таймаут ожидания текста")
    return False


def _detect_makeup_answer(text: str) -> Optional[int]:
    """Поиск ключа макияжа в тексте. None если не найдено."""
    clean = text.strip()
    for key, tabs in MAKEUP_ANSWERS.items():
        if key in clean:
            return tabs
    return None

def _detect_narushenia_answer(text: str) -> Optional[int]:
    """Поиск ключа макияжа в тексте. None если не найдено."""
    clean = text.strip()
    for key, tabs in DEFAULT_ANSWERS.items():
        if key in clean:
            return tabs
    return None

# ── Обработчики заданий ───────────────────────────────────────────
def handle_priority_flow() -> None:
    """
    Обработка приоритетных заданий:
    - поле «не найдено» (3 таба → пробел → отправка)
    - цикл исправления ошибок (2 таба → пробел → отправка)
    """
    text = copy_selected()

    if "не найдено" in text:
        log("📍 Обрабатываю 'не найдено'")
        tap_tab(3)
        tap_space()
        submit()
        time.sleep(1)

    # Цикл исправления ошибок
    while True:
        check_stop()
        text = copy_selected()
        if "вы допустили ошибку" in text:
            log("❌ Ошибка — исправляю")
            tap_tab(2)
            tap_space()
            submit()
            time.sleep(1)
        elif "полностью одинаковые товары или с небольшими отличиями" in text:
            break
        else:
            log("✅ Ошибок больше нет")
            break


def handle_clothing_task() -> None:
    """Задание по одежде: последовательный выбор ответов табами."""
    raw_answers = parse_answers(pyperclip.paste())
    log(f"👕 Ответы: {raw_answers}")

    position = 0  # текущая позиция в форме
    for answer in raw_answers:
        check_stop()
        target = CLOTHES_ANSWERS.get(answer)
        if target is None:
            log(f"⚠️ Пропущен неизвестный ответ: {answer}")
            continue

        delta = target - position
        if delta < 0:
            log(f"⚠️ Назад не двигаемся: {position} → {target}")
            continue

        log(f"➡️ {answer}: {position} → {target} (нажать {delta})")
        tap_tab(delta)
        tap_space()
        position = target

    if state.auto_submit:
        submit()

def handle_narushenia_task() -> None:
    raw_answers = pyperclip.paste()
    log(f" Ответ: {raw_answers}")


    check_stop()
    target = DEFAULT_ANSWERS.get(raw_answers)
    if target is None:
        log(f"⚠️ Пропущен неизвестный ответ: {raw_answers}")
    tap_tab(target)
    tap_space()

    if state.auto_submit:
        submit()

def handle_makeup_task() -> None:
    """Задание по макияжу: оттенок + коды."""
    raw = pyperclip.paste()
    answers = [a.strip() for a in parse_answers(raw)]
    answers.extend([""] * (4 - len(answers)))  # Дополняем до 4
    log(f"💄 Ответы makeup: {answers}")

    # 1. Выбор «нужен/не нужен оттенок»
    shade_tabs = MAKEUP_ANSWERS.get(answers[0])
    if shade_tabs is None:
        log(f"⚠️ Неизвестный ответ по оттенку: {answers[0]}")
        return
    tap_tab(shade_tabs)
    tap_space()

    # 2. Возврат в якорную позицию
    tap_tab(2)

    # 3. Заполнение кодов: code, en, ru
    for field_value in answers[1:4]:
        if field_value:
            pyperclip.copy(field_value)
            keyboard.press_and_release("ctrl+v")
        tap_tab()

    if state.auto_submit:
        submit()

# ── Безопасная обёртка для основных экшенов ───────────────────────
def safe_execute(action: Callable, action_name: str) -> None:
    """
    Выполнить действие с перехватом критических ошибок.
    При ClickFailedError — останавливает приложение полностью.
    """
    try:
        action()
    except ClickFailedError as e:
        log(f"💀 Критический сбой в '{action_name}': {e}")
        log("🛑 Аварийная остановка приложения")
        state.loop.stop()
        sys.exit(1)
    except StopIteration:
        log(f"⏹️ Действие '{action_name}' прервано пользователем")
        state.loop.stop()
    except Exception as e:
        log(f"❌ Неожиданная ошибка в '{action_name}': {e}")
        state.loop.stop()

# ── Основные экшены ───────────────────────────────────────────────
def copy_action() -> bool:
    """
    Основной рабочий цикл одного задания.
    Возвращает True, если нужно прервать цикл.
    """
    ensure_english_layout()
    time.sleep(DELAY_SHORT)

    # 1. Копирование задания
    safe_click(CLICK_AREA_1)  # Если клик не сработает — приложение остановится
    task_text = wait_for_new_task()
    log(f"📋 Задание: {truncate(task_text, 100)}")

    # 2. Проверка приоритетного задания
    if is_priority_task(task_text):
        if is_receipt_task(task_text):
            log("🧾 Чек — обычная логика")
        else:
            log("🔥 Приоритетное задание — специальная обработка")
            handle_priority_flow()
            return True

    # 3. Вставка во вторую область
    safe_click(CLICK_AREA_2)  # Критический клик
    focus()
    keyboard.press_and_release("ctrl+v")
    time.sleep(0.5)
    pyautogui.press("enter")
    time.sleep(1)

    # 4. Обработка ответов
    switch_action()
    return False


def switch_action() -> None:
    """Определить тип задания и запустить соответствующий обработчик."""
    check_stop()
    wait_for_new_text(ANSWER_AREA)
    safe_click(CLICK_AREA_1)
    time.sleep(DELAY_SHORT)


    if is_clothing_task():
        handle_clothing_task()
    elif is_narushenia_task():
        handle_narushenia_task()
    elif is_makeup_task():
        handle_makeup_task()
    else:
        if state.auto_submit:
            submit()



def clip_action() -> None:
    """Вставка заготовленного текста."""
    pyperclip.copy(TEXT_TO_TYPE)
    time.sleep(DELAY_SHORT)
    focus()
    keyboard.press_and_release("ctrl+v")


def get_position() -> None:
    """Вывести текущие координаты курсора."""
    log(f"📍 {pyautogui.position()}")


# ── Управление циклом ─────────────────────────────────────────────
def start_loop() -> None:
    """Запустить цикл обработки заданий в фоновом потоке."""
    if state.loop.is_running():
        log("⚠️ Цикл уже запущен")
        return

    state.loop.start()

    def _worker() -> None:
        total = 300
        for i in range(total):
            if state.loop.stop_requested:
                log("🛑 Цикл прерван пользователем")
                break
            log(f"🔄 Итерация {i + 1}/{total}")

            # Безопасное выполнение с остановкой при критическом сбое
            try:
                should_stop = copy_action()
                if should_stop:
                    log("🛑 Цикл завершён: приоритетное задание")
                    break
            except ClickFailedError as e:
                log(f"💀 Критический сбой в цикле: {e}")
                log("🛑 Аварийная остановка приложения")
                break
            except StopIteration:
                log("⏹️ Цикл прерван")
                break
            except Exception as e:
                log(f"❌ Неожиданная ошибка: {e}")
                break

            time.sleep(DELAY_LONG)

        state.loop.stop()
        log("✅ Цикл завершён")

    threading.Thread(target=_worker, daemon=True).start()
    log("🚀 Цикл запущен")


def stop_loop() -> None:
    """Остановить активный цикл."""
    state.loop.stop()
    log("⏹️ Цикл остановлен")


def toggle_auto_submit() -> None:
    """Включить/выключить автоотправку."""
    new_state = state.toggle_auto_submit()
    log(f"📤 Автоотправка: {'ВКЛ' if new_state else 'ВЫКЛ'}")


# ── Точка входа ───────────────────────────────────────────────────
def main() -> None:
    """Регистрация горячих клавиш и запуск ожидания."""
    bindings: Dict[str, Callable[[], None]] = {
        HOTKEY_COPY: copy_action,
        HOTKEY_POSITION: get_position,
        HOTKEY_LOOP: start_loop,
        HOTKEY_STOP: stop_loop,
        HOTKEY_PUSH_ANSWER: toggle_auto_submit,
        "esc": lambda: exit(),
    }

    for hotkey, handler in bindings.items():
        keyboard.add_hotkey(hotkey, handler)

    log("⌨️  Горячие клавиши зарегистрированы")
    log(f"   {HOTKEY_COPY} — выполнить задание")
    log(f"   {HOTKEY_POSITION} — координаты курсора")
    log(f"   {HOTKEY_LOOP} — запустить цикл")
    log(f"   {HOTKEY_STOP} — остановить цикл")
    log(f"   {HOTKEY_PUSH_ANSWER} — автоотправка")
    keyboard.wait()


if __name__ == "__main__":
    main()