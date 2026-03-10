# Video Download Studio

`Video Download Studio` 是一个 Windows 桌面客户端，支持：

1. 输入 URL 自动检测可下载视频并下载（VOD）
2. 输入直播 URL 实时录制并保存（LIVE）
3. 多 URL 任务队列、进度/速度显示、状态日志

## 项目结构（标准 `src` 布局）

```text
.
├─ src/
│  └─ video_download_studio/
│     ├─ __init__.py
│     ├─ __main__.py
│     ├─ client.py        # 下载与直播录制核心
│     └─ gui.py           # PySide6 图形界面
├─ assets/
│  └─ video_download_studio.ico
├─ scripts/
│  └─ build_release.ps1   # Full/Lite 发布打包脚本
├─ app.py                 # 本地运行/打包入口
├─ requirements.txt
├─ pyproject.toml
└─ build_exe.ps1          # 兼容入口（调用 scripts/build_release.ps1）
```

## 安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 本地运行

```powershell
.\.venv\Scripts\python.exe app.py
```

## 打包发布（两种风格）

```powershell
.\build_exe.ps1
```

会产出：

- `dist/VideoDownloadStudio_v3_Full.exe`：完整版（内置 ffmpeg 回退，体积较大）
- `dist/VideoDownloadStudio_v3.exe`：完整版别名（便于主发布）
- `dist/VideoDownloadStudio_v3_Lite.exe`：轻量版（体积更小，目标机器需可用 `ffmpeg`）

## 说明

- Full 版本推荐直接分发给普通用户。
- Lite 版本适合你自己可控环境（已装 ffmpeg）或追求较小体积的场景。
