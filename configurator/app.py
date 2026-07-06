"""GUI-конфигуратор Mia (Tkinter).

Вкладки:
  - Управление: запуск/остановка/перезапуск бота, статусы.
  - Модели: список моделей Ollama, смена активной модели «на лету».
  - Обновления: проверка и применение обновлений из GitHub, автопроверка.
  - Логи: просмотр, отправка на GitHub, экспорт в ZIP.
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from config import runtime, settings
from configurator import log_sender, updater
from configurator.process_manager import BotProcessManager
from mia.core.llm import llm_client

logger = logging.getLogger(__name__)


class ConfiguratorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.bot = BotProcessManager()
        self._auto_update_job = None

        root.title("Mia — Конфигуратор")
        root.geometry("820x600")
        root.minsize(720, 520)

        self._build_statusbar()

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._build_control_tab(notebook)
        self._build_models_tab(notebook)
        self._build_update_tab(notebook)
        self._build_logs_tab(notebook)

        self._refresh_status()
        self._schedule_log_refresh()
        self._apply_auto_update_setting(initial=True)
        self._maybe_autostart_bot()

    def _maybe_autostart_bot(self) -> None:
        if runtime.get("autostart_bot", False) and not self.bot.is_running():
            self.root.after(500, self._start_bot)

    # ---------- Статус-бар ----------
    def _build_statusbar(self) -> None:
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=8, pady=6)
        self.status_var = tk.StringVar(value="…")
        ttk.Label(bar, textvariable=self.status_var).pack(side="left")

    def _refresh_status(self) -> None:
        ollama = "доступен" if llm_client.is_available() else "НЕ доступен"
        commit = updater.current_commit() or "—"
        self.status_var.set(
            f"Бот: {self.bot.status_text()}   |   Ollama: {ollama}   |   "
            f"Модель: {runtime.get_active_model()}   |   Версия: {commit}"
        )
        self.root.after(4000, self._refresh_status)

    # ---------- Вкладка: Управление ----------
    def _build_control_tab(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb)
        nb.add(tab, text="Управление")

        ttk.Label(tab, text="Управление ботом Mia", font=("", 13, "bold")).pack(
            anchor="w", padx=12, pady=(14, 8)
        )
        btns = ttk.Frame(tab)
        btns.pack(anchor="w", padx=12, pady=6)
        ttk.Button(btns, text="▶ Запустить", command=self._start_bot).grid(row=0, column=0, padx=4)
        ttk.Button(btns, text="■ Остановить", command=self._stop_bot).grid(row=0, column=1, padx=4)
        ttk.Button(btns, text="⟳ Перезапустить", command=self._restart_bot).grid(row=0, column=2, padx=4)

        deps = ttk.Frame(tab)
        deps.pack(anchor="w", padx=12, pady=6)
        ttk.Button(
            deps, text="Установить/обновить зависимости", command=self._install_deps
        ).grid(row=0, column=0, padx=4)

        self.autostart_var = tk.BooleanVar(value=bool(runtime.get("autostart_bot", False)))
        ttk.Checkbutton(
            tab, text="Запускать бота автоматически при старте конфигуратора",
            variable=self.autostart_var, command=self._toggle_autostart,
        ).pack(anchor="w", padx=12, pady=4)

        self.control_info = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self.control_info, foreground="#555", wraplength=760).pack(
            anchor="w", padx=12, pady=8
        )

    def _start_bot(self) -> None:
        ok, msg = self.bot.start()
        self.control_info.set(msg)

    def _stop_bot(self) -> None:
        ok, msg = self.bot.stop()
        self.control_info.set(msg)

    def _restart_bot(self) -> None:
        ok, msg = self.bot.restart()
        self.control_info.set(msg)

    def _install_deps(self) -> None:
        self.control_info.set("Устанавливаю зависимости, это может занять пару минут…")
        self._run_bg(updater.install_requirements, self._on_deps_result)

    def _on_deps_result(self, result) -> None:
        if isinstance(result, Exception):
            self.control_info.set(f"Ошибка: {result}")
            return
        ok, msg = result
        self.control_info.set(msg)

    def _toggle_autostart(self) -> None:
        runtime.set_value("autostart_bot", bool(self.autostart_var.get()))

    # ---------- Вкладка: Модели ----------
    def _build_models_tab(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb)
        nb.add(tab, text="Модели")

        ttk.Label(tab, text="Модели Ollama", font=("", 13, "bold")).pack(
            anchor="w", padx=12, pady=(14, 8)
        )

        row = ttk.Frame(tab)
        row.pack(fill="x", padx=12, pady=6)
        ttk.Label(row, text="Доступные модели:").pack(side="left")
        self.model_combo = ttk.Combobox(row, state="readonly", width=42)
        self.model_combo.pack(side="left", padx=8)
        ttk.Button(row, text="Обновить список", command=self._reload_models).pack(side="left")

        actions = ttk.Frame(tab)
        actions.pack(anchor="w", padx=12, pady=8)
        ttk.Button(actions, text="Сделать рабочей (чат)", command=self._set_chat_model).grid(
            row=0, column=0, padx=4
        )
        ttk.Button(actions, text="Сделать моделью эмбеддингов", command=self._set_embed_model).grid(
            row=0, column=1, padx=4
        )
        ttk.Button(actions, text="Сделать vision-моделью (OCR)", command=self._set_vision_model).grid(
            row=0, column=2, padx=4
        )

        self.models_info = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self.models_info, foreground="#555").pack(
            anchor="w", padx=12, pady=8
        )
        self._reload_models()

    def _reload_models(self) -> None:
        models = llm_client.list_models()
        self.model_combo["values"] = models
        active = runtime.get_active_model()
        if active in models:
            self.model_combo.set(active)
        elif models:
            self.model_combo.set(models[0])
        self.models_info.set(
            f"Чат: {runtime.get_active_model()} | "
            f"эмбеддинги: {runtime.get_active_embed_model()} | "
            f"vision: {runtime.get_active_vision_model()}"
        )

    def _set_chat_model(self) -> None:
        model = self.model_combo.get()
        if not model:
            return
        runtime.set_active_model(model)
        self.models_info.set(f"Рабочая модель переключена на: {model} (без перезапуска).")

    def _set_embed_model(self) -> None:
        model = self.model_combo.get()
        if not model:
            return
        runtime.set_active_embed_model(model)
        self.models_info.set(f"Модель эмбеддингов: {model}.")

    def _set_vision_model(self) -> None:
        model = self.model_combo.get()
        if not model:
            return
        runtime.set_active_vision_model(model)
        self.models_info.set(f"Vision-модель (OCR): {model}.")

    # ---------- Вкладка: Обновления ----------
    def _build_update_tab(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb)
        nb.add(tab, text="Обновления")

        ttk.Label(tab, text="Обновление из GitHub", font=("", 13, "bold")).pack(
            anchor="w", padx=12, pady=(14, 8)
        )

        btns = ttk.Frame(tab)
        btns.pack(anchor="w", padx=12, pady=6)
        ttk.Button(btns, text="Проверить обновления", command=self._check_updates).grid(
            row=0, column=0, padx=4
        )
        ttk.Button(btns, text="Обновить сейчас", command=self._apply_update).grid(
            row=0, column=1, padx=4
        )

        auto = ttk.Frame(tab)
        auto.pack(anchor="w", padx=12, pady=10)
        self.auto_update_var = tk.BooleanVar(value=settings.AUTO_UPDATE_INTERVAL_MIN > 0)
        ttk.Checkbutton(
            auto, text="Автопроверка каждые", variable=self.auto_update_var,
            command=self._apply_auto_update_setting,
        ).pack(side="left")
        self.interval_var = tk.StringVar(
            value=str(settings.AUTO_UPDATE_INTERVAL_MIN or 30)
        )
        ttk.Entry(auto, textvariable=self.interval_var, width=5).pack(side="left", padx=4)
        ttk.Label(auto, text="минут").pack(side="left")
        ttk.Button(auto, text="Применить", command=self._apply_auto_update_setting).pack(
            side="left", padx=8
        )

        self.update_info = tk.StringVar(
            value=f"Ветка обновлений: {settings.UPDATE_BRANCH or 'текущая'}"
        )
        ttk.Label(tab, textvariable=self.update_info, foreground="#555", wraplength=760).pack(
            anchor="w", padx=12, pady=8
        )

    def _check_updates(self) -> None:
        self.update_info.set("Проверяю обновления…")
        self._run_bg(updater.check_for_updates, self._on_update_result)

    def _apply_update(self) -> None:
        if not messagebox.askyesno(
            "Обновление",
            "Применить обновление? Бот будет перезапущен после установки.",
        ):
            return
        self.update_info.set("Устанавливаю обновление…")

        def task():
            was_running = self.bot.is_running()
            if was_running:
                self.bot.stop()
            status = updater.apply_update()
            if status.ok and not status.has_updates:
                # Обновление применено — доустановим зависимости на случай их изменения.
                updater.install_requirements()
            if status.ok and was_running:
                self.bot.start()
            return status

        self._run_bg(task, self._on_update_result)

    def _on_update_result(self, status) -> None:
        if isinstance(status, Exception):
            self.update_info.set(f"Ошибка: {status}")
            return
        self.update_info.set(status.message)

    def _apply_auto_update_setting(self, initial: bool = False) -> None:
        if self._auto_update_job is not None:
            self.root.after_cancel(self._auto_update_job)
            self._auto_update_job = None
        if not self.auto_update_var.get():
            if not initial:
                self.update_info.set("Автопроверка выключена.")
            return
        try:
            minutes = max(1, int(self.interval_var.get()))
        except ValueError:
            minutes = 30
            self.interval_var.set("30")
        if not initial:
            self.update_info.set(f"Автопроверка включена: каждые {minutes} мин.")
        self._schedule_auto_update(minutes)

    def _schedule_auto_update(self, minutes: int) -> None:
        def tick():
            self._run_bg(updater.check_for_updates, self._on_update_result)
            self._auto_update_job = self.root.after(minutes * 60_000, tick)

        self._auto_update_job = self.root.after(minutes * 60_000, tick)

    # ---------- Вкладка: Логи ----------
    def _build_logs_tab(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb)
        nb.add(tab, text="Логи")

        top = ttk.Frame(tab)
        top.pack(fill="x", padx=12, pady=(12, 4))
        ttk.Label(top, text="Логи и файлы", font=("", 13, "bold")).pack(side="left")
        ttk.Button(top, text="Отправить файл разработчику", command=self._send_file_to_dev).pack(
            side="right", padx=6
        )
        ttk.Button(top, text="Отправить логи на GitHub", command=self._send_logs).pack(side="right")
        ttk.Button(top, text="Экспорт логов в ZIP", command=self._export_logs).pack(
            side="right", padx=6
        )

        self.log_view = ScrolledText(tab, wrap="none", height=20, state="disabled")
        self.log_view.pack(fill="both", expand=True, padx=12, pady=6)

        self.logs_info = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self.logs_info, foreground="#555").pack(
            anchor="w", padx=12, pady=(0, 8)
        )

    def _schedule_log_refresh(self) -> None:
        self._refresh_logs()
        self.root.after(2000, self._schedule_log_refresh)

    def _refresh_logs(self) -> None:
        log_path = settings.LOGS_DIR / "mia.log"
        if not log_path.exists():
            return
        try:
            data = log_path.read_bytes()[-20_000:].decode("utf-8", errors="replace")
        except Exception:
            return
        self.log_view.configure(state="normal")
        self.log_view.delete("1.0", "end")
        self.log_view.insert("end", data)
        self.log_view.see("end")
        self.log_view.configure(state="disabled")

    def _send_logs(self) -> None:
        self.logs_info.set("Отправляю логи на GitHub…")
        self._run_bg(log_sender.send_logs_to_github, self._on_logs_action)

    def _export_logs(self) -> None:
        dest = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP-архив", "*.zip")],
            initialfile="mia-logs.zip",
        )
        if not dest:
            return
        ok, msg = log_sender.export_logs_zip(dest)
        self.logs_info.set(msg)

    def _send_file_to_dev(self) -> None:
        path = filedialog.askopenfilename(
            title="Выберите файл для отправки разработчику",
            filetypes=[
                ("Документы", "*.docx *.xlsx *.xlsm *.pdf *.doc *.xls"),
                ("Все файлы", "*.*"),
            ],
        )
        if not path:
            return
        if not settings.GITHUB_TOKEN:
            messagebox.showinfo(
                "Нужен токен",
                "Чтобы отправлять файлы через конфигуратор, впишите GITHUB_TOKEN в .env.\n\n"
                "Либо загрузите файлы через сайт GitHub (Add file → Upload files).",
            )
            return
        self.logs_info.set("Отправляю файл разработчику…")
        self._run_bg(lambda: log_sender.send_file_to_github(path), self._on_logs_action)

    def _on_logs_action(self, result) -> None:
        if isinstance(result, Exception):
            self.logs_info.set(f"Ошибка: {result}")
            return
        ok, msg = result
        self.logs_info.set(msg)

    # ---------- Утилита фоновых задач ----------
    def _run_bg(self, func, on_done) -> None:
        """Выполняет func в потоке и возвращает результат в GUI через after()."""

        def worker():
            try:
                result = func()
            except Exception as e:  # noqa: BLE001
                logger.exception("Фоновая задача упала")
                result = e
            self.root.after(0, lambda: on_done(result))

        threading.Thread(target=worker, daemon=True).start()


def main() -> None:
    from mia.core.logging_setup import setup_logging

    setup_logging()
    root = tk.Tk()
    ConfiguratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
