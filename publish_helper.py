"""Publishing helper utility for BUKVA-49."""
import subprocess
import sys
from pathlib import Path


def setup_encoding() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    setup_encoding()
    print("=" * 75)
    print("      ЦЕНТР ПУБЛИКАЦИИ BUKVA-49 (GITHUB & PYPI)")
    print("=" * 75)
    print("Текущая версия пакета: v0.7.0")
    print("Собранный wheel: dist/bukva49-0.7.0-py3-none-any.whl")
    print("\nВыберите действие:")
    print("  [1] Проверить пакет утилитой Twine (twine check)")
    print("  [2] Подключить удалённый репозиторий GitHub и отправить код (git push)")
    print("  [3] Опубликовать в TestPyPI (тестовый реестр Python)")
    print("  [4] Опубликовать в официальный PyPI (pip install bukva49)")
    print("  [0] Выход")
    print("-" * 75)

    choice = input("Введите номер [1-4] или 0 для выхода: ").strip()

    if choice == "1":
        print("\nЗапуск twine check dist/* ...")
        subprocess.run([sys.executable, "-m", "twine", "check", "dist/*"])
    elif choice == "2":
        repo_url = input("\nВставьте ссылку на ваш GitHub репозиторий (например, https://github.com/USER/bukva49.git):\n> ").strip()
        if repo_url:
            subprocess.run(["git", "remote", "remove", "origin"], capture_output=True)
            res1 = subprocess.run(["git", "remote", "add", "origin", repo_url])
            print("Отправка ветки main и тегов...")
            res2 = subprocess.run(["git", "push", "-u", "origin", "main", "--tags"])
            if res2.returncode == 0:
                print("\n[УСПЕХ] Код и тег v0.7.0 успешно опубликованы на GitHub!")
            else:
                print("\n[Внимание] Проверьте правильность ссылки и авторизацию в GitHub.")
    elif choice == "3":
        print("\nПубликация в TestPyPI:")
        print("Вам понадобится API-токен с сайта https://test.pypi.org/")
        subprocess.run([sys.executable, "-m", "twine", "upload", "--repository", "testpypi", "dist/*"])
    elif choice == "4":
        print("\nПубликация в официальный PyPI:")
        print("Вам понадобится API-токен с сайта https://pypi.org/manage/account/token/")
        print("При запросе имени пользователя введите: __token__")
        print("В качестве пароля вставьте скопированный токен: pypi-AgEI...")
        subprocess.run([sys.executable, "-m", "twine", "upload", "dist/*"])
    else:
        print("Выход.")


if __name__ == "__main__":
    main()
