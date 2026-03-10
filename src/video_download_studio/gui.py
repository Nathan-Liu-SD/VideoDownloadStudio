#!/usr/bin/env python3
"""Modern desktop GUI for Video Download Studio based on PySide6."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from html import escape
from pathlib import Path

from PySide6.QtCore import QObject, QLocale, Qt, QThread, Signal
from PySide6.QtGui import QCloseEvent, QColor, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .client import DetectionResult, DownloadJob, VideoClient


I18N: dict[str, dict[str, str]] = {
    "zh": {
        "title": "Video Download Studio",
        "subtitle": "URL 检测下载 + 直播实时录制 + 批量任务管理",
        "url": "URL",
        "mode": "模式",
        "duration": "直播时长(秒，可空)",
        "browse": "浏览",
        "add": "添加任务",
        "batch": "批量添加",
        "remove": "删除选中",
        "clear": "清空队列",
        "start": "开始执行",
        "stop": "停止",
        "queue": "任务队列",
        "log": "运行日志",
        "batch_title": "批量添加 URL",
        "batch_hint": "每行一个 URL",
        "confirm_add": "确认添加",
        "cancel": "取消",
        "optional": "可空",
        "info": "提示",
        "error": "错误",
        "confirm": "确认",
        "exit": "退出",
        "idle": "空闲",
        "running": "运行中",
        "done": "已完成",
        "stopping": "正在停止",
        "stopped": "已停止",
        "no_url": "请输入 URL",
        "invalid_duration": "直播时长必须是正整数",
        "batch_empty": "没有可添加的 URL",
        "already_running": "任务正在执行中",
        "no_jobs": "请先添加任务",
        "clear_confirm": "确定清空任务队列吗?",
        "exit_confirm": "任务仍在运行，确定退出吗?",
        "pick_output": "选择输出目录",
        "placeholder_url": "输入视频页 URL 或直播 URL",
        "placeholder_duration": "直播时长(秒，可空)",
        "status_queued": "排队中",
        "status_detecting": "检测中",
        "status_not_found": "未找到资源",
        "status_done": "完成",
        "status_stopped": "已停止",
        "status_running_mode": "执行中({mode})",
        "status_failed": "失败({code})",
        "col_id": "#",
        "col_url": "URL",
        "col_mode": "模式",
        "col_duration": "时长",
        "col_progress": "进度",
        "col_speed": "速率",
        "col_status": "状态",
    },
    "en": {
        "title": "Video Download Studio",
        "subtitle": "URL detection + VOD download + live recording + task queue",
        "url": "URL",
        "mode": "Mode",
        "duration": "Live Duration (seconds, optional)",
        "browse": "Browse",
        "add": "Add Task",
        "batch": "Batch Add",
        "remove": "Remove Selected",
        "clear": "Clear Queue",
        "start": "Start",
        "stop": "Stop",
        "queue": "Task Queue",
        "log": "Runtime Log",
        "batch_title": "Batch Add URLs",
        "batch_hint": "One URL per line",
        "confirm_add": "Confirm",
        "cancel": "Cancel",
        "optional": "Optional",
        "info": "Info",
        "error": "Error",
        "confirm": "Confirm",
        "exit": "Exit",
        "idle": "Idle",
        "running": "Running",
        "done": "Done",
        "stopping": "Stopping",
        "stopped": "Stopped",
        "no_url": "Please enter a URL",
        "invalid_duration": "Live duration must be a positive integer",
        "batch_empty": "No URLs to add",
        "already_running": "Task is already running",
        "no_jobs": "Please add at least one task",
        "clear_confirm": "Clear all queued tasks?",
        "exit_confirm": "Tasks are still running. Exit anyway?",
        "pick_output": "Select output folder",
        "placeholder_url": "Enter video page URL or live stream URL",
        "placeholder_duration": "Live duration in seconds (optional)",
        "status_queued": "Queued",
        "status_detecting": "Detecting",
        "status_not_found": "Not Found",
        "status_done": "Done",
        "status_stopped": "Stopped",
        "status_running_mode": "Running ({mode})",
        "status_failed": "Failed ({code})",
        "col_id": "#",
        "col_url": "URL",
        "col_mode": "Mode",
        "col_duration": "Duration",
        "col_progress": "Progress",
        "col_speed": "Speed",
        "col_status": "Status",
    },
}

I18N["ja"] = {
    **I18N["en"],
    "subtitle": "URL 検出 + 動画保存 + ライブ録画 + タスク管理",
    "browse": "参照",
    "add": "追加",
    "batch": "一括追加",
    "remove": "選択削除",
    "clear": "キューをクリア",
    "start": "開始",
    "stop": "停止",
    "queue": "タスクキュー",
    "log": "ログ",
    "idle": "待機中",
    "running": "実行中",
    "done": "完了",
    "stopping": "停止中",
    "stopped": "停止済み",
    "status_queued": "待機",
    "status_detecting": "検出中",
    "status_not_found": "未検出",
    "status_done": "完了",
    "status_stopped": "停止済み",
    "status_running_mode": "実行中 ({mode})",
    "status_failed": "失敗 ({code})",
    "col_mode": "モード",
    "col_duration": "時間",
    "col_progress": "進捗",
    "col_speed": "速度",
    "col_status": "状態",
}

I18N["es"] = {
    **I18N["en"],
    "subtitle": "Deteccion de URL + descarga VOD + grabacion en vivo + cola",
    "browse": "Examinar",
    "add": "Agregar",
    "batch": "Lote",
    "remove": "Eliminar",
    "clear": "Limpiar cola",
    "start": "Iniciar",
    "stop": "Detener",
    "queue": "Cola",
    "log": "Registro",
    "idle": "En espera",
    "running": "Ejecutando",
    "done": "Finalizado",
    "stopping": "Deteniendo",
    "stopped": "Detenido",
    "status_queued": "En cola",
    "status_detecting": "Detectando",
    "status_not_found": "No encontrado",
    "status_done": "Finalizado",
    "status_stopped": "Detenido",
    "status_running_mode": "Ejecutando ({mode})",
    "status_failed": "Fallo ({code})",
    "col_duration": "Duracion",
    "col_progress": "Progreso",
    "col_speed": "Velocidad",
    "col_status": "Estado",
}

I18N["de"] = {
    **I18N["en"],
    "subtitle": "URL-Erkennung + VOD-Download + Live-Aufnahme + Warteschlange",
    "browse": "Durchsuchen",
    "add": "Hinzufugen",
    "batch": "Stapel",
    "remove": "Auswahl loschen",
    "clear": "Warteschlange leeren",
    "start": "Starten",
    "stop": "Stoppen",
    "queue": "Warteschlange",
    "log": "Protokoll",
    "idle": "Bereit",
    "running": "Lauft",
    "done": "Fertig",
    "stopping": "Wird gestoppt",
    "stopped": "Gestoppt",
    "status_queued": "Wartet",
    "status_detecting": "Prufe",
    "status_not_found": "Nicht gefunden",
    "status_done": "Fertig",
    "status_stopped": "Gestoppt",
    "status_running_mode": "Lauft ({mode})",
    "status_failed": "Fehlgeschlagen ({code})",
    "col_duration": "Dauer",
    "col_progress": "Fortschritt",
    "col_speed": "Geschwindigkeit",
    "col_status": "Status",
}

def resource_path(relative: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")) / relative
    return Path(__file__).resolve().parents[2] / relative


def detect_lang() -> str:
    locale_name = QLocale.system().name().lower()
    prefix = locale_name.split("_", 1)[0]
    mapping = {
        "zh": "zh",
        "en": "en",
        "ja": "ja",
        "es": "es",
        "de": "de",
    }
    return mapping.get(prefix, "en")


def tr(lang: str, key: str, **kwargs: object) -> str:
    table = I18N.get(lang, I18N["en"])
    text = table.get(key, I18N["en"].get(key, key))
    return text.format(**kwargs) if kwargs else text


@dataclass
class QueueItem:
    row: int
    job: DownloadJob


class BatchAddDialog(QDialog):
    def __init__(self, lang: str, mode: str, duration: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle(tr(self.lang, "batch_title"))
        self.resize(680, 460)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr(self.lang, "batch_hint")))

        self.urls_edit = QTextEdit()
        self.urls_edit.setPlaceholderText("https://example.com/video1\nhttps://example.com/video2")
        layout.addWidget(self.urls_edit, 1)

        form = QGridLayout()
        form.addWidget(QLabel(tr(self.lang, "mode")), 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["auto", "vod", "live"])
        self.mode_combo.setCurrentText(mode)
        form.addWidget(self.mode_combo, 0, 1)

        form.addWidget(QLabel(tr(self.lang, "duration")), 0, 2)
        self.duration_edit = QLineEdit(duration)
        self.duration_edit.setPlaceholderText(tr(self.lang, "optional"))
        form.addWidget(self.duration_edit, 0, 3)
        layout.addLayout(form)

        row = QHBoxLayout()
        row.addStretch(1)
        ok_btn = QPushButton(tr(self.lang, "confirm_add"))
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(tr(self.lang, "cancel"))
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(ok_btn)
        row.addWidget(cancel_btn)
        layout.addLayout(row)

    def get_values(self) -> tuple[list[str], str, str]:
        urls = [line.strip() for line in self.urls_edit.toPlainText().splitlines() if line.strip()]
        return urls, self.mode_combo.currentText(), self.duration_edit.text().strip()


class JobWorker(QObject):
    log = Signal(str)
    status_changed = Signal(int, str)
    row_metrics = Signal(int, str, str)
    finished = Signal(int, int, bool)

    def __init__(self, items: list[QueueItem], output_dir: str, lang: str):
        super().__init__()
        self.items = items
        self.output_dir = output_dir
        self.lang = lang
        self.stop_event = threading.Event()
        self.current_process: subprocess.Popen | None = None
        self.client: VideoClient | None = None

    def _tr(self, zh: str, en: str) -> str:
        return zh if self.lang == "zh" else en

    def request_stop(self) -> None:
        self.stop_event.set()

        if self.client is not None:
            self.client.request_stop()

        process = self.current_process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass

    def run(self) -> None:
        client = VideoClient(output_dir=self.output_dir, stop_event=self.stop_event)
        self.client = client

        success = 0
        failed = 0
        stopped = False

        try:
            for index, item in enumerate(self.items, start=1):
                if self.stop_event.is_set():
                    stopped = True
                    self.log.emit(self._tr("任务已停止", "Task stopped"))
                    break

                client.progress_callback = lambda payload, row=item.row: self._emit_row_metrics(row, payload)

                self.row_metrics.emit(item.row, "0%", "-")
                self.status_changed.emit(item.row, "detecting")
                self.log.emit(
                    self._tr(
                        f"[{index}/{len(self.items)}] 检测 URL: {item.job.url}",
                        f"[{index}/{len(self.items)}] Detecting URL: {item.job.url}",
                    )
                )

                detection = client.detect(item.job.url)
                if not detection.supported:
                    failed += 1
                    self.status_changed.emit(item.row, "not_found")
                    self.log.emit(
                        self._tr(
                            f"未检测到可下载视频: {item.job.url}",
                            f"No downloadable media found: {item.job.url}",
                        )
                    )
                    continue

                mode = item.job.mode
                if mode == "auto":
                    mode = "live" if detection.is_live else "vod"

                self.status_changed.emit(item.row, f"running:{mode}")
                self.log.emit(
                    self._tr(
                        f"模式={mode} 标题={detection.title or 'N/A'}",
                        f"Mode={mode} Title={detection.title or 'N/A'}",
                    )
                )

                if mode == "live":
                    rc = self._run_live_job(client, item.job, detection, item.row)
                else:
                    rc = client.download_vod(item.job.url, detection)

                if rc == 0:
                    success += 1
                    self.row_metrics.emit(item.row, "100%", "-")
                    self.status_changed.emit(item.row, "done")
                    self.log.emit(self._tr(f"完成: {item.job.url}", f"Done: {item.job.url}"))
                elif self.stop_event.is_set() or rc == 130:
                    stopped = True
                    self.status_changed.emit(item.row, "stopped")
                    self.log.emit(self._tr(f"已停止: {item.job.url}", f"Stopped: {item.job.url}"))
                    break
                else:
                    failed += 1
                    self.status_changed.emit(item.row, f"failed({rc})")
                    self.log.emit(self._tr(f"失败: {item.job.url} (code={rc})", f"Failed: {item.job.url} (code={rc})"))
                    if client.last_error:
                        self.log.emit(self._tr(f"原因: {client.last_error}", f"Reason: {client.last_error}"))
        except Exception as exc:
            failed += 1
            self.log.emit(self._tr(f"执行异常: {exc}", f"Runtime exception: {exc}"))
        finally:
            self.client = None
            self.finished.emit(success, failed, stopped)

    def _run_live_job(self, client: VideoClient, job: DownloadJob, detection: DetectionResult, row: int) -> int:
        stream_url = detection.stream_url
        if not stream_url and detection.raw_info:
            stream_url = client._pick_stream_url(detection.raw_info, prefer_live=True)
        if not stream_url:
            stream_url = job.url

        if not client._ffmpeg_exists():
            self.log.emit(self._tr("ffmpeg 不可用，无法录制直播", "ffmpeg unavailable; cannot record live stream"))
            return 2

        safe_title = client._sanitize_filename(detection.title or "live")
        ts = time.strftime("%Y%m%d_%H%M%S")
        output_file = client.output_dir / f"{safe_title}_{ts}.ts"

        cmd = [
            client.ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "warning",
            "-y",
            "-i",
            stream_url,
            "-c",
            "copy",
        ]
        if job.duration and job.duration > 0:
            cmd.extend(["-t", str(job.duration)])
        cmd.extend(["-f", "mpegts", str(output_file)])

        popen_kwargs: dict[str, object] = {}
        if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW")
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            popen_kwargs["startupinfo"] = startupinfo

        self.log.emit(self._tr(f"开始录制直播 -> {output_file}", f"Start recording live -> {output_file}"))
        process = subprocess.Popen(cmd, **popen_kwargs)
        self.current_process = process

        start_time = time.time()
        last_time = start_time
        last_size = 0

        try:
            while True:
                if self.stop_event.is_set():
                    process.terminate()
                    try:
                        process.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    self.log.emit(self._tr(f"已停止直播录制，文件已保存: {output_file}", f"Live recording stopped, saved: {output_file}"))
                    return 130

                rc = process.poll()
                now = time.time()

                if output_file.exists() and now - last_time >= 1.0:
                    try:
                        current_size = output_file.stat().st_size
                    except OSError:
                        current_size = last_size

                    delta_bytes = max(0, current_size - last_size)
                    delta_time = max(0.001, now - last_time)
                    speed = delta_bytes / delta_time

                    if job.duration and job.duration > 0:
                        elapsed = max(0.0, now - start_time)
                        pct = min(100.0, (elapsed * 100.0) / float(job.duration))
                        progress_text = f"{pct:.1f}%"
                    else:
                        progress_text = "LIVE"

                    self.row_metrics.emit(row, progress_text, self._format_speed_mb(speed))
                    last_time = now
                    last_size = current_size

                if rc is not None:
                    if rc == 0:
                        self.log.emit(self._tr(f"直播录制完成: {output_file}", f"Live recording finished: {output_file}"))
                    return rc

                time.sleep(0.35)
        finally:
            self.current_process = None

    def _emit_row_metrics(self, row: int, payload: dict[str, object]) -> None:
        if payload.get("status") == "stopped":
            self.row_metrics.emit(row, "-", "-")
            return

        percent = payload.get("percent")
        if isinstance(percent, (int, float)):
            progress = f"{max(0.0, min(100.0, float(percent))):.1f}%"
        else:
            progress = "..."

        speed = payload.get("speed")
        bitrate = self._format_speed_mb(float(speed)) if isinstance(speed, (int, float)) else "-"
        self.row_metrics.emit(row, progress, bitrate)

    @staticmethod
    def _format_speed_mb(speed_bytes_per_sec: float) -> str:
        if speed_bytes_per_sec <= 0:
            return "-"
        mbs = speed_bytes_per_sec / 1_048_576.0
        if mbs < 0.01:
            return "-"
        return f"{mbs:.2f} MB/s"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.lang = detect_lang()

        self.setWindowTitle(tr(self.lang, "title"))
        self.resize(1280, 840)

        icon_path = resource_path("assets/video_download_studio.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.next_id = 1
        self.worker_thread: QThread | None = None
        self.worker: JobWorker | None = None

        self.url_edit = QLineEdit()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["auto", "vod", "live"])
        self.duration_edit = QLineEdit()
        self.duration_edit.setPlaceholderText(tr(self.lang, "placeholder_duration"))
        self.output_edit = QLineEdit(str(Path.cwd() / "downloads"))

        self.table = QTableWidget(0, 7)
        self.log_box = QTextEdit()
        self.status_label = QLabel(tr(self.lang, "idle"))
        self.progress = QProgressBar()

        self.run_btn = QPushButton(tr(self.lang, "start"))
        self.stop_btn = QPushButton(tr(self.lang, "stop"))
        self.stop_btn.setEnabled(False)

        self._build_ui()
        self._apply_styles()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        title = QLabel(tr(self.lang, "title"))
        title.setObjectName("Title")
        subtitle = QLabel(tr(self.lang, "subtitle"))
        subtitle.setObjectName("Subtitle")
        root_layout.addWidget(title)
        root_layout.addWidget(subtitle)

        body = QHBoxLayout()
        body.setSpacing(14)
        root_layout.addLayout(body, 1)

        left = QWidget()
        left.setObjectName("Panel")
        left.setFixedWidth(360)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(10)

        left_layout.addWidget(QLabel(tr(self.lang, "url")))
        self.url_edit.setPlaceholderText(tr(self.lang, "placeholder_url"))
        left_layout.addWidget(self.url_edit)

        left_layout.addWidget(QLabel(tr(self.lang, "mode")))
        left_layout.addWidget(self.mode_combo)

        left_layout.addWidget(QLabel(tr(self.lang, "duration")))
        left_layout.addWidget(self.duration_edit)

        out_row = QHBoxLayout()
        out_row.addWidget(self.output_edit)
        browse_btn = QPushButton(tr(self.lang, "browse"))
        browse_btn.setObjectName("SecondaryBtn")
        browse_btn.clicked.connect(self._choose_output_dir)
        out_row.addWidget(browse_btn)
        left_layout.addLayout(out_row)

        row1 = QHBoxLayout()
        add_btn = QPushButton(tr(self.lang, "add"))
        add_btn.setObjectName("PrimaryBtn")
        add_btn.clicked.connect(self._add_single_job)
        batch_btn = QPushButton(tr(self.lang, "batch"))
        batch_btn.setObjectName("InfoBtn")
        batch_btn.clicked.connect(self._add_batch_jobs)
        row1.addWidget(add_btn)
        row1.addWidget(batch_btn)
        left_layout.addLayout(row1)

        row2 = QHBoxLayout()
        rm_btn = QPushButton(tr(self.lang, "remove"))
        rm_btn.setObjectName("WarningBtn")
        rm_btn.clicked.connect(self._remove_selected)
        clear_btn = QPushButton(tr(self.lang, "clear"))
        clear_btn.setObjectName("DangerBtn")
        clear_btn.clicked.connect(self._clear_jobs)
        row2.addWidget(rm_btn)
        row2.addWidget(clear_btn)
        left_layout.addLayout(row2)

        row3 = QHBoxLayout()
        self.run_btn.setObjectName("SuccessBtn")
        self.stop_btn.setObjectName("DangerBtn")
        self.run_btn.clicked.connect(self._start_run)
        self.stop_btn.clicked.connect(self._stop_run)
        row3.addWidget(self.run_btn)
        row3.addWidget(self.stop_btn)
        left_layout.addLayout(row3)

        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        left_layout.addWidget(self.status_label)
        left_layout.addWidget(self.progress)
        left_layout.addStretch(1)

        right = QWidget()
        right.setObjectName("Panel")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)

        self.table.setHorizontalHeaderLabels([tr(self.lang, "col_id"), tr(self.lang, "col_url"), tr(self.lang, "col_mode"), tr(self.lang, "col_duration"), tr(self.lang, "col_progress"), tr(self.lang, "col_speed"), tr(self.lang, "col_status")])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)

        self.table.setColumnWidth(0, 56)
        self.table.setColumnWidth(2, 84)
        self.table.setColumnWidth(3, 92)
        self.table.setColumnWidth(4, 96)
        self.table.setColumnWidth(5, 112)
        self.table.setColumnWidth(6, 122)

        right_layout.addWidget(QLabel(tr(self.lang, "queue")))
        right_layout.addWidget(self.table, 1)

        self.log_box.setReadOnly(True)
        right_layout.addWidget(QLabel(tr(self.lang, "log")))
        right_layout.addWidget(self.log_box, 1)

        body.addWidget(left)
        body.addWidget(right, 1)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background-color: #090f1f;
                color: #dbeafe;
                font-family: 'Segoe UI';
                font-size: 13px;
            }
            QWidget#Panel {
                background-color: #10192d;
                border: 1px solid #243b63;
                border-radius: 16px;
            }
            QLabel#Title {
                color: #f8fafc;
                font-size: 30px;
                font-weight: 800;
                letter-spacing: 0.3px;
            }
            QLabel#Subtitle {
                color: #7dd3fc;
                font-size: 14px;
            }
            QLineEdit, QComboBox, QTextEdit, QTableWidget {
                background-color: #0d1730;
                border: 1px solid #2a3e66;
                border-radius: 10px;
                padding: 6px;
                color: #e2e8f0;
                selection-background-color: #1d4ed8;
            }
            QTableWidget {
                gridline-color: #23395b;
                alternate-background-color: #12203b;
            }
            QTableWidget::item:selected {
                background: #1d4ed8;
            }
            QHeaderView::section {
                background-color: #0f2e59;
                color: #f1f5f9;
                font-weight: 700;
                padding: 6px;
                border: 1px solid #2e4f78;
            }
            QTableCornerButton::section {
                background-color: #0f2e59;
                border: 1px solid #2e4f78;
            }
            QTextEdit {
                font-family: 'Consolas';
                font-size: 12px;
            }
            QPushButton {
                background-color: #1e293b;
                border: 1px solid #36465f;
                border-radius: 9px;
                padding: 8px 12px;
                color: #e2e8f0;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #334155; }
            QPushButton:pressed { background-color: #1d4ed8; }
            QPushButton:disabled {
                background-color: #182235;
                color: #6b7280;
                border: 1px solid #22324f;
            }
            QPushButton#PrimaryBtn { background-color: #2563eb; border-color: #3b82f6; }
            QPushButton#PrimaryBtn:hover { background-color: #1d4ed8; }
            QPushButton#InfoBtn { background-color: #0ea5e9; border-color: #38bdf8; color: #082f49; }
            QPushButton#InfoBtn:hover { background-color: #0284c7; color: #e0f2fe; }
            QPushButton#SuccessBtn { background-color: #16a34a; border-color: #22c55e; }
            QPushButton#SuccessBtn:hover { background-color: #15803d; }
            QPushButton#WarningBtn { background-color: #d97706; border-color: #f59e0b; color: #fff7ed; }
            QPushButton#WarningBtn:hover { background-color: #b45309; }
            QPushButton#DangerBtn { background-color: #dc2626; border-color: #ef4444; color: #fee2e2; }
            QPushButton#DangerBtn:hover { background-color: #b91c1c; }
            QPushButton#SecondaryBtn { background-color: #334155; border-color: #475569; }
            QPushButton#SecondaryBtn:hover { background-color: #475569; }
            QProgressBar {
                background-color: #0d1730;
                border: 1px solid #2a3e66;
                border-radius: 8px;
                text-align: center;
                color: #e2e8f0;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 7px;
            }
            """
        )

    def _choose_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, tr(self.lang, "pick_output"), self.output_edit.text().strip() or str(Path.cwd()))
        if folder:
            self.output_edit.setText(folder)

    def _add_single_job(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, tr(self.lang, "info"), tr(self.lang, "no_url"))
            return

        duration = self._parse_duration(self.duration_edit.text().strip())
        if self.duration_edit.text().strip() and duration is None:
            QMessageBox.critical(self, tr(self.lang, "error"), tr(self.lang, "invalid_duration"))
            return

        self._append_job(DownloadJob(url=url, mode=self.mode_combo.currentText(), duration=duration))
        self.url_edit.clear()

    def _add_batch_jobs(self) -> None:
        dialog = BatchAddDialog(self.lang, self.mode_combo.currentText(), self.duration_edit.text().strip(), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        urls, mode, duration_text = dialog.get_values()
        if not urls:
            QMessageBox.warning(self, tr(self.lang, "info"), tr(self.lang, "batch_empty"))
            return

        duration = self._parse_duration(duration_text)
        if duration_text and duration is None:
            QMessageBox.critical(self, tr(self.lang, "error"), tr(self.lang, "invalid_duration"))
            return

        for url in urls:
            self._append_job(DownloadJob(url=url, mode=mode, duration=duration))
        self._log(f"Batch tasks added: {len(urls)}" if self.lang == "en" else f"批量添加任务: {len(urls)} 条")

    def _append_job(self, job: DownloadJob) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        duration_text = str(job.duration) if job.duration else "-"
        self.table.setItem(row, 0, QTableWidgetItem(str(self.next_id)))
        self.table.setItem(row, 1, QTableWidgetItem(job.url))
        self.table.setItem(row, 2, QTableWidgetItem(job.mode))
        self.table.setItem(row, 3, QTableWidgetItem(duration_text))
        self.table.setItem(row, 4, QTableWidgetItem("0%"))
        self.table.setItem(row, 5, QTableWidgetItem("-"))
        self.table.setItem(row, 6, QTableWidgetItem(self._status_display("queued")))

        for col in (0, 2, 3, 4, 5, 6):
            item = self.table.item(row, col)
            if item is not None:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        self._apply_status_cell_style(row, "queued")
        self._log(f"Task added #{self.next_id}: {job.url}" if self.lang == "en" else f"已添加任务 #{self.next_id}: {job.url}")
        self.next_id += 1

    def _remove_selected(self) -> None:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        for row in rows:
            self.table.removeRow(row)
        self._log(f"Tasks removed: {len(rows)}" if self.lang == "en" else f"已删除任务: {len(rows)} 条")

    def _clear_jobs(self) -> None:
        if self.table.rowCount() == 0:
            return
        if QMessageBox.question(self, tr(self.lang, "confirm"), tr(self.lang, "clear_confirm")) != QMessageBox.StandardButton.Yes:
            return
        self.table.setRowCount(0)
        self._log("Task queue cleared" if self.lang == "en" else "任务队列已清空")

    def _collect_jobs(self) -> list[QueueItem]:
        items: list[QueueItem] = []
        for row in range(self.table.rowCount()):
            url_item = self.table.item(row, 1)
            mode_item = self.table.item(row, 2)
            duration_item = self.table.item(row, 3)
            if url_item is None or mode_item is None or duration_item is None:
                continue
            url = url_item.text().strip()
            mode = mode_item.text().strip() or "auto"
            duration_text = duration_item.text().strip()
            duration = int(duration_text) if duration_text.isdigit() else None
            items.append(QueueItem(row=row, job=DownloadJob(url=url, mode=mode, duration=duration)))
        return items

    def _start_run(self) -> None:
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.information(self, tr(self.lang, "info"), tr(self.lang, "already_running"))
            return

        items = self._collect_jobs()
        if not items:
            QMessageBox.warning(self, tr(self.lang, "info"), tr(self.lang, "no_jobs"))
            return

        output_dir = self.output_edit.text().strip() or str(Path.cwd() / "downloads")

        self.worker_thread = QThread(self)
        self.worker = JobWorker(items, output_dir, self.lang)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.log.connect(self._log)
        self.worker.status_changed.connect(self._set_row_status)
        self.worker.row_metrics.connect(self._set_row_metrics)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText(tr(self.lang, "running"))
        self.progress.setRange(0, 0)
        self._log(f"Started tasks, total: {len(items)}" if self.lang == "en" else f"开始执行任务，总数: {len(items)}")
        self.worker_thread.start()

    def _stop_run(self) -> None:
        if self.worker:
            self.worker.request_stop()
            self.stop_btn.setEnabled(False)
            self.status_label.setText(tr(self.lang, "stopping"))
            self._log("Stop requested. The current task will stop shortly." if self.lang == "en" else "收到停止请求，当前任务将尽快终止")

    def _set_row_status(self, row: int, status: str) -> None:
        item = self.table.item(row, 6)
        if item is not None:
            item.setText(self._status_display(status))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_status_cell_style(row, status)

    def _status_display(self, raw: str) -> str:
        if raw == "queued":
            return tr(self.lang, "status_queued")
        if raw == "detecting":
            return tr(self.lang, "status_detecting")
        if raw == "not_found":
            return tr(self.lang, "status_not_found")
        if raw == "done":
            return tr(self.lang, "status_done")
        if raw == "stopped":
            return tr(self.lang, "status_stopped")
        if raw.startswith("running:"):
            mode = raw.split(":", 1)[1].upper()
            return tr(self.lang, "status_running_mode", mode=mode)
        if raw.startswith("failed(") and raw.endswith(")"):
            code = raw[7:-1]
            return tr(self.lang, "status_failed", code=code)
        return raw

    def _set_row_metrics(self, row: int, progress: str, bitrate: str) -> None:
        p_item = self.table.item(row, 4)
        b_item = self.table.item(row, 5)
        if p_item is not None:
            p_item.setText(progress)
            p_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if b_item is not None:
            b_item.setText(bitrate)
            b_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def _on_worker_finished(self, success: int, failed: int, stopped: bool) -> None:
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.status_label.setText(tr(self.lang, "stopped") if stopped else tr(self.lang, "done"))
        self._log(
            f"Finished. Download success: {success}, failed: {failed}"
            if self.lang == "en"
            else f"任务结束，下载成功数: {success}，下载失败数: {failed}"
        )

        self.worker = None
        self.worker_thread = None

    def _apply_status_cell_style(self, row: int, status: str) -> None:
        item = self.table.item(row, 6)
        if item is None:
            return

        normalized = status.lower()
        color = "#e2e8f0"
        if normalized in {"queued", "detecting"}:
            color = "#cbd5e1"
        elif normalized.startswith("running"):
            color = "#7dd3fc"
        elif normalized == "done":
            color = "#86efac"
        elif normalized.startswith("failed"):
            color = "#fca5a5"
        elif normalized == "stopped":
            color = "#fdba74"
        elif normalized == "not_found":
            color = "#fda4af"

        item.setForeground(QColor(color))

    def _log(self, message: str) -> None:
        ts = time.strftime("%H:%M:%S")
        color = self._pick_log_color(message)
        self.log_box.append(
            f"<span style='color:#94a3b8'>[{ts}]</span> "
            f"<span style='color:{color}'>{escape(message)}</span>"
        )
        scrollbar = self.log_box.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @staticmethod
    def _pick_log_color(message: str) -> str:
        lower = message.lower()
        if any(k in message for k in ["失败", "异常", "错误"]) or any(k in lower for k in ["failed", "exception", "error"]):
            return "#fca5a5"
        if any(k in message for k in ["完成", "成功", "任务结束"]) or any(k in lower for k in ["done", "success", "finished"]):
            return "#86efac"
        if any(k in message for k in ["开始执行", "开始录制"]) or any(k in lower for k in ["start", "recording"]):
            return "#7dd3fc"
        if "停止" in message or "stopped" in lower:
            return "#fdba74"
        if "检测" in message or "detect" in lower:
            return "#c4b5fd"
        return "#e2e8f0"

    @staticmethod
    def _parse_duration(raw: str) -> int | None:
        if not raw:
            return None
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        return None

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker_thread and self.worker_thread.isRunning():
            result = QMessageBox.question(self, tr(self.lang, "exit"), tr(self.lang, "exit_confirm"))
            if result != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            if self.worker:
                self.worker.request_stop()
            self.worker_thread.quit()
            self.worker_thread.wait(5000)
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    icon_path = resource_path("assets/video_download_studio.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())





