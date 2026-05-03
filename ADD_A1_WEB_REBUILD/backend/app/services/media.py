from __future__ import annotations

from pathlib import Path

VOICE_MAP = {
    "III_short_hyper__expert__audio": "voice_iii_expert.wav",
    "III_short_hyper__peer__audio": "voice_iii_peer.wav",
    "IV_persistent_high_normal__expert__audio": "voice_iv_expert.wav",
    "IV_persistent_high_normal__peer__audio": "voice_iv_peer.wav",
}

VIDEO_MAP = {
    "III_short_hyper__expert__avatar": "video_iii_expert.mp4",
    "III_short_hyper__peer__avatar": "video_iii_peer.mp4",
    "IV_persistent_high_normal__expert__avatar": "video_iv_expert.mp4",
    "IV_persistent_high_normal__peer__avatar": "video_iv_peer.mp4",
}


def media_dirs() -> tuple[str, str]:
    root = Path(__file__).resolve().parents[2]
    voice_dir = root / "media" / "voice"
    video_dir = root / "media" / "video"
    return str(voice_dir), str(video_dir)


def find_media_file(folder: Path, condition_id: str, media_type: str) -> str | None:
    """
    动态查找媒体文件，不依赖硬编码的映射表。
    优先级：
    1. 首先尝试硬编码映射表（兼容旧文件）
    2. 其次动态扫描文件夹查找匹配的文件
    """
    if not folder.exists():
        return None
    
    # 尝试硬编码映射表
    if media_type == "audio" and condition_id in VOICE_MAP:
        fallback_file = folder / VOICE_MAP[condition_id]
        if fallback_file.exists():
            return VOICE_MAP[condition_id]
    elif media_type == "video" and condition_id in VIDEO_MAP:
        fallback_file = folder / VIDEO_MAP[condition_id]
        if fallback_file.exists():
            return VIDEO_MAP[condition_id]
    
    # 动态扫描文件夹，查找包含condition_id关键字的文件
    audio_extensions = {".wav", ".mp3", ".aac", ".flac", ".m4a"}
    video_extensions = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    
    target_extensions = audio_extensions if media_type == "audio" else video_extensions
    
    # 标准化condition_id用于文件名搜索
    # 例如：III_short_hyper__expert__audio -> 查找包含 iii 或 expert 的文件
    condition_parts = condition_id.lower().split("__")
    
    for file_path in sorted(folder.iterdir()):
        if not file_path.is_file():
            continue
        
        file_ext = file_path.suffix.lower()
        if file_ext not in target_extensions:
            continue
        
        filename_lower = file_path.name.lower()
        # 检查文件名是否包含条件的关键部分
        if any(part in filename_lower for part in condition_parts if part and part not in ["__", "audio", "avatar"]):
            return file_path.name
    
    # 如果没有找到，返回None
    return None


def resolve_media_urls(condition_id: str, media: str) -> tuple[str | None, str | None]:
    """
    返回媒体文件的URL。支持动态文件发现和缓存破坏。
    """
    voice_dir, video_dir = media_dirs()
    voice_path = Path(voice_dir)
    video_path = Path(video_dir)
    
    if media == "audio":
        filename = find_media_file(voice_path, condition_id, "audio")
        if filename:
            return (f"/media/voice/{filename}?t={int(Path(voice_path / filename).stat().st_mtime)}", None)
        return (None, None)
    
    if media == "avatar":
        filename = find_media_file(video_path, condition_id, "video")
        if filename:
            return (None, f"/media/video/{filename}?t={int(Path(video_path / filename).stat().st_mtime)}")
        return (None, None)
    
    return (None, None)

