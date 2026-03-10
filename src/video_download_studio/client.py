#!/usr/bin/env python3
"""Core download/record logic for Video Download Studio."""

from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import warnings

warnings.filterwarnings(
    "ignore",
    message="Unable to find acceptable character detection dependency",
    module="requests",
)

import requests

try:
    import yt_dlp
    from yt_dlp.utils import DownloadCancelled as YTDLPDownloadCancelled
except ImportError:  # pragma: no cover - runtime dependency hint
    yt_dlp = None

    class YTDLPDownloadCancelled(Exception):
        pass

try:
    import imageio_ffmpeg
except ImportError:  # pragma: no cover - optional runtime dependency
    imageio_ffmpeg = None


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class DetectionResult:
    input_url: str
    supported: bool = False
    is_live: bool = False
    title: str | None = None
    extractor: str | None = None
    stream_url: str | None = None
    direct_video_urls: list[str] = field(default_factory=list)
    raw_info: dict[str, Any] | None = None


@dataclass
class DownloadJob:
    url: str
    mode: str = "auto"
    duration: int | None = None


class StopRequestedError(Exception):
    """Raised when a running task is cancelled by user request."""


class VideoClient:
    def __init__(
        self,
        output_dir: str | Path,
        ffmpeg_bin: str = "ffmpeg",
        timeout: int = 20,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        stop_event: threading.Event | None = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.last_error: str | None = None
        self.progress_callback = progress_callback
        self.stop_event = stop_event

        self._active_process_lock = threading.Lock()
        self._active_process: subprocess.Popen[Any] | None = None
        self.ffmpeg_bin = self._resolve_ffmpeg_bin(ffmpeg_bin)

    def request_stop(self) -> None:
        if self.stop_event is not None:
            self.stop_event.set()

        process = self._get_active_process()
        if process is not None and process.poll() is None:
            self._terminate_process(process, timeout=3)

    def _is_stopping(self) -> bool:
        return bool(self.stop_event and self.stop_event.is_set())

    def _set_active_process(self, process: subprocess.Popen[Any] | None) -> None:
        with self._active_process_lock:
            self._active_process = process

    def _get_active_process(self) -> subprocess.Popen[Any] | None:
        with self._active_process_lock:
            return self._active_process

    def detect(self, url: str) -> DetectionResult:
        result = DetectionResult(input_url=url)

        info = self._extract_with_yt_dlp(url)
        if info:
            result.supported = True
            result.raw_info = info
            result.title = info.get("title")
            result.extractor = info.get("extractor_key") or info.get("extractor")
            live_status = str(info.get("live_status") or "").lower()
            result.is_live = bool(info.get("is_live")) or live_status == "is_live"

            stream_url = self._pick_stream_url(info, prefer_live=result.is_live)
            if stream_url:
                result.stream_url = stream_url
                result.direct_video_urls.append(stream_url)
            return result

        direct_urls = self._find_direct_video_links(url)
        if direct_urls:
            result.supported = True
            result.direct_video_urls = direct_urls
            result.stream_url = direct_urls[0]
            result.is_live = any(self._looks_like_live_stream(x) for x in direct_urls)

        return result

    def download_vod(self, url: str, detection: DetectionResult) -> int:
        self.last_error = None

        if self._is_stopping():
            self.last_error = "Stopped by user."
            return 130

        if detection.raw_info and yt_dlp is not None:
            return self._download_with_yt_dlp(url)

        if not detection.direct_video_urls:
            self.last_error = "No downloadable video URL found."
            return 2

        target = detection.direct_video_urls[0]
        if self._looks_like_live_stream(target):
            self.last_error = "Detected stream manifest link. Use live mode to record it."
            return 2
        return self._download_direct_file(target, title=detection.title)

    def record_live(self, url: str, detection: DetectionResult, duration: int | None = None) -> int:
        self.last_error = None

        if self._is_stopping():
            self.last_error = "Stopped by user."
            return 130

        stream_url = detection.stream_url
        if not stream_url and detection.raw_info:
            stream_url = self._pick_stream_url(detection.raw_info, prefer_live=True)
        if not stream_url:
            stream_url = url

        if not self._ffmpeg_exists():
            self.last_error = "ffmpeg is not available. Install ffmpeg or imageio-ffmpeg."
            return 2

        safe_title = self._sanitize_filename(detection.title or "live")
        ts = time.strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"{safe_title}_{ts}.ts"

        cmd = [
            self.ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "warning",
            "-y",
            "-i",
            stream_url,
            "-c",
            "copy",
        ]
        if duration and duration > 0:
            cmd.extend(["-t", str(duration)])
        cmd.extend(["-f", "mpegts", str(output_file)])

        process = subprocess.Popen(cmd, **self._popen_kwargs_no_window())
        self._set_active_process(process)
        try:
            while True:
                if self._is_stopping():
                    self.last_error = "Stopped by user."
                    self._terminate_process(process, timeout=5)
                    return 130

                rc = process.poll()
                if rc is not None:
                    return rc
                time.sleep(0.3)
        finally:
            self._set_active_process(None)

    def _extract_with_yt_dlp(self, url: str) -> dict[str, Any] | None:
        if yt_dlp is None or self._is_stopping():
            return None

        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": False,
            "ffmpeg_location": self.ffmpeg_bin,
            "socket_timeout": self.timeout,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if not isinstance(info, dict):
                return None

            if info.get("_type") == "playlist":
                entries = [x for x in (info.get("entries") or []) if isinstance(x, dict)]
                if entries:
                    sample = entries[0]
                    merged = dict(info)
                    merged.update({k: v for k, v in sample.items() if k not in merged or merged[k] is None})
                    return merged
            return info
        except Exception:
            return None

    def _pick_stream_url(self, info: dict[str, Any], prefer_live: bool = False) -> str | None:
        formats = info.get("formats") or []
        if isinstance(formats, list) and formats:
            if prefer_live:
                for fmt in reversed(formats):
                    fmt_url = fmt.get("url")
                    proto = str(fmt.get("protocol") or "")
                    ext = str(fmt.get("ext") or "")
                    if fmt_url and (proto.startswith("m3u8") or ext == "m3u8"):
                        return str(fmt_url)

            for fmt in reversed(formats):
                fmt_url = fmt.get("url")
                if fmt_url:
                    return str(fmt_url)

        raw_url = info.get("url")
        return str(raw_url) if raw_url else None

    def _find_direct_video_links(self, page_url: str) -> list[str]:
        headers = {"User-Agent": USER_AGENT}
        try:
            resp = requests.get(page_url, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException:
            return []

        html = resp.text
        links: set[str] = set()

        for match in re.findall(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", html, re.IGNORECASE):
            candidate = urljoin(page_url, match)
            if self._looks_like_video_url(candidate):
                links.add(candidate)

        for match in re.findall(r"""https?:\\?/\\?/[^"'\\\s]+""", html):
            candidate = match.replace("\\/", "/")
            if self._looks_like_video_url(candidate):
                links.add(candidate)

        return sorted(links)

    @staticmethod
    def _looks_like_video_url(url: str) -> bool:
        lower = url.lower()
        return any(
            ext in lower
            for ext in (
                ".mp4",
                ".mov",
                ".mkv",
                ".webm",
                ".flv",
                ".m3u8",
                ".mpd",
                ".ts",
            )
        )

    @staticmethod
    def _looks_like_live_stream(url: str) -> bool:
        lower = url.lower()
        return ".m3u8" in lower or ".mpd" in lower or "live" in lower

    def _emit_progress(self, payload: dict[str, Any]) -> None:
        callback = self.progress_callback
        if callback is None:
            return
        try:
            callback(payload)
        except Exception:
            pass

    def _download_with_yt_dlp(self, url: str) -> int:
        if yt_dlp is None:
            self.last_error = "yt-dlp is not installed."
            return 2

        if self._is_stopping():
            self.last_error = "Stopped by user."
            return 130

        downloaded: list[str] = []

        def _hook(d: dict[str, Any]) -> None:
            if self._is_stopping():
                raise YTDLPDownloadCancelled("Stopped by user")

            status = d.get("status")
            if status == "downloading":
                downloaded_bytes = d.get("downloaded_bytes")
                total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
                speed = d.get("speed")
                percent: float | None = None
                if downloaded_bytes and total_bytes:
                    try:
                        percent = float(downloaded_bytes) * 100.0 / float(total_bytes)
                    except Exception:
                        percent = None

                self._emit_progress(
                    {
                        "stage": "vod",
                        "status": "downloading",
                        "downloaded_bytes": downloaded_bytes,
                        "total_bytes": total_bytes,
                        "speed": speed,
                        "percent": percent,
                    }
                )
            elif status == "finished":
                name = d.get("filename")
                if name:
                    downloaded.append(str(name))
                self._emit_progress({"stage": "vod", "status": "finished", "percent": 100.0})

        opts: dict[str, Any] = {
            "outtmpl": str(self.output_dir / "%(title).180B-%(id)s.%(ext)s"),
            "format": "bv*+ba/b",
            "merge_output_format": "mp4",
            "noplaylist": False,
            "ffmpeg_location": self.ffmpeg_bin,
            "socket_timeout": self.timeout,
            "progress_hooks": [_hook],
        }

        original_popen = subprocess.Popen

        def _patched_popen(*popen_args: Any, **popen_kwargs: Any) -> subprocess.Popen[Any]:
            command = popen_args[0] if popen_args else popen_kwargs.get("args")
            if self._is_ffmpeg_command(command):
                hidden_kwargs = self._popen_kwargs_no_window()
                if "creationflags" in hidden_kwargs:
                    popen_kwargs["creationflags"] = int(popen_kwargs.get("creationflags", 0)) | int(hidden_kwargs["creationflags"])
                popen_kwargs.setdefault("startupinfo", hidden_kwargs.get("startupinfo"))

            process = original_popen(*popen_args, **popen_kwargs)
            if self._is_ffmpeg_command(command):
                self._set_active_process(process)
            return process

        try:
            if os.name == "nt":
                subprocess.Popen = _patched_popen
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except (StopRequestedError, YTDLPDownloadCancelled):
            self.last_error = "Stopped by user."
            self._emit_progress({"stage": "vod", "status": "stopped"})
            return 130
        except Exception as exc:
            if self._is_stopping():
                self.last_error = "Stopped by user."
                self._emit_progress({"stage": "vod", "status": "stopped"})
                return 130
            self.last_error = str(exc)
            return 1
        finally:
            subprocess.Popen = original_popen
            self._set_active_process(None)

        if not downloaded:
            # Some extractors return success without direct filename callback.
            pass
        return 0

    def _download_direct_file(self, file_url: str, title: str | None = None) -> int:
        if self._is_stopping():
            self.last_error = "Stopped by user."
            return 130

        headers = {"User-Agent": USER_AGENT}
        output_path: Path | None = None
        stopped = False

        try:
            with requests.get(file_url, stream=True, headers=headers, timeout=self.timeout) as resp:
                resp.raise_for_status()
                file_name = self._build_file_name(file_url, title)
                output_path = self.output_dir / file_name
                total = int(resp.headers.get("Content-Length", "0"))
                downloaded = 0
                start_time = time.time()

                with output_path.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 256):
                        if self._is_stopping():
                            stopped = True
                            break

                        if not chunk:
                            continue

                        f.write(chunk)
                        downloaded += len(chunk)
                        elapsed = max(0.001, time.time() - start_time)
                        speed = downloaded / elapsed

                        pct: float | None = None
                        if total:
                            pct = downloaded * 100 / total

                        self._emit_progress(
                            {
                                "stage": "vod",
                                "status": "downloading",
                                "downloaded_bytes": downloaded,
                                "total_bytes": total if total else None,
                                "speed": speed,
                                "percent": pct,
                            }
                        )
        except requests.RequestException as exc:
            if self._is_stopping():
                self.last_error = "Stopped by user."
                self._emit_progress({"stage": "vod", "status": "stopped"})
                return 130
            self.last_error = str(exc)
            return 1

        if stopped:
            if output_path is not None:
                try:
                    output_path.unlink(missing_ok=True)
                except Exception:
                    pass
            self.last_error = "Stopped by user."
            self._emit_progress({"stage": "vod", "status": "stopped"})
            return 130

        self._emit_progress({"stage": "vod", "status": "finished", "percent": 100.0})
        return 0

    def _build_file_name(self, file_url: str, title: str | None = None) -> str:
        parsed = urlparse(file_url)
        base = Path(parsed.path).name
        if not base:
            ts = time.strftime("%Y%m%d_%H%M%S")
            base = f"video_{ts}.mp4"
        if title:
            suffix = Path(base).suffix or ".mp4"
            base = f"{self._sanitize_filename(title)}{suffix}"
        return self._sanitize_filename(base)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        cleaned = re.sub(r'[\\/:*?"<>|]+', "_", name).strip()
        return cleaned[:220] or "video"

    @staticmethod
    def _popen_kwargs_no_window() -> dict[str, Any]:
        if os.name != "nt":
            return {}

        kwargs: dict[str, Any] = {}
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW")

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        kwargs["startupinfo"] = startupinfo
        return kwargs

    @staticmethod
    def _is_ffmpeg_command(command: Any) -> bool:
        try:
            if isinstance(command, (list, tuple)) and command:
                program = str(command[0])
            else:
                program = str(command)
            name = os.path.basename(program).lower()
            return name.startswith("ffmpeg") or name.startswith("ffprobe")
        except Exception:
            return False

    @staticmethod
    def _terminate_process(process: subprocess.Popen[Any], timeout: float = 3.0) -> None:
        if process.poll() is not None:
            return

        try:
            process.terminate()
            process.wait(timeout=timeout)
            return
        except Exception:
            pass

        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **VideoClient._popen_kwargs_no_window(),
                )
            except Exception:
                pass

        try:
            process.kill()
        except Exception:
            pass

    @staticmethod
    def _can_run_ffmpeg(binary: str) -> bool:
        try:
            subprocess.run(
                [binary, "-version"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **VideoClient._popen_kwargs_no_window(),
            )
            return True
        except Exception:
            return False

    def _resolve_ffmpeg_bin(self, preferred_bin: str) -> str:
        if self._can_run_ffmpeg(preferred_bin):
            return preferred_bin

        if imageio_ffmpeg is not None:
            try:
                bundled = imageio_ffmpeg.get_ffmpeg_exe()
                if bundled and self._can_run_ffmpeg(bundled):
                    return bundled
            except Exception:
                pass

        return preferred_bin

    def _ffmpeg_exists(self) -> bool:
        return self._can_run_ffmpeg(self.ffmpeg_bin)


