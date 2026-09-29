# -*- coding: utf-8 -*-
"""Interactive launcher for BUKVA-49 Benchmark supporting multiple models."""
import os
import subprocess
import sys
from pathlib import Path

MODELS = {
    "1": ("qwen3.5:9b", "llm_result_9b.json"),
    "2": ("hf.co/mradermacher/Qwen3.5-4B-SOMPOA-heresy-v2-GGUF:Q4_K_M", "llm_result_4b.json"),
}


def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass
        os.system("title БУКВА-49 — Стенд тестирования моделей ИИ")

    script_dir = Path(__file__).parent.resolve()
    os.chdir(script_dir)

    print("=" * 78)
    print("           БУКВА-49: Стенд проверки гипотезы мышления ИИ")
    print("=" * 78)
    print("Режимы:")
    print("  1) direct - Прямой ответ без подсказок шагов")
    print("  2) cot    - Стандартная пошаговая инструкция (контроль без букв)")
    print("  3) 297    - Триада Буквицы 297 (Вѣди - Фита - Земля)")
    print("  4) full   - Полный цикл Буквицы (Вѣди - Есть - Мыслите - Кси - Фита - Земля)")
    print()
    print("Категории задач с ловушками:")
    print("  - Выбор поставщика (с лимитом срока доставки и проверкой подтверждения)")
    print("  - Пересчёт остатков склада (с фильтрацией отмен и учётом резервов)")
    print("  - Шахматный рейтинг (по правилам турнира и с бонусом за победную серию)")
    print("  - Выбор источника (актуальная дата только среди утверждённых версий)")
    print("=" * 78)
    print()

    print("Выберите модель для тестирования:")
    print("  [1] qwen3.5:9b    (Большая модель 9B)")
    print("  [2] Qwen3.5-4B    (Компактная модель 4B, 100% GPU, быстрая)")
    try:
        m_choice = input("Модель (1 или 2, Enter = 2): ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    model_name, output_file = MODELS.get(m_choice, MODELS["2"])
    print(f"\nВыбрана модель: {model_name}")

    print("\nВыберите вариант запуска:")
    print("  [1] Быстрый тест    (1 задача на категорию = 16 запросов к модели)")
    print("  [2] Стандартный     (2 задачи на категорию = 32 запроса) [Рекомендуется]")
    print("  [3] Глубокий тест   (3 задачи на категорию = 48 запросов)")
    print("  [4] Выход")
    print()

    try:
        choice = input("Ваш выбор (1, 2, 3 или 4, Enter = 2): ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if choice == "1":
        per_family = 1
    elif choice == "3":
        per_family = 3
    elif choice == "4":
        print("Выход.")
        return
    else:
        per_family = 2

    cmd = [
        sys.executable,
        str(script_dir / "llm_benchmark.py"),
        "--model", model_name,
        "--per-family", str(per_family),
        "--output", str(script_dir / output_file),
    ]

    print()
    print(f"[*] Запуск бенчмарка для {model_name} (--per-family {per_family})...")
    print("-" * 78)
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n[!] Процесс остановлен пользователем.")
    except Exception as e:
        print(f"\n[!] Ошибка запуска: {e}")

    print()
    print("=" * 78)
    print(f"Работа завершена. Результаты сохранены в {output_file}")
    print("=" * 78)
    input("\nНажмите Enter для закрытия окна...")


if __name__ == "__main__":
    main()
