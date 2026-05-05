from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from app.services.media import media_dirs

router = APIRouter(tags=["health"])


@router.get("/api/health")
def api_health() -> dict:
    return {"ok": True}


@router.get("/api/debug/media")
def debug_media() -> dict:
    """
    调试接口：列出所有可用的媒体文件
    用于诊断媒体文件更新问题
    """
    voice_dir, video_dir = media_dirs()
    voice_path = Path(voice_dir)
    video_path = Path(video_dir)
    
    audio_files = []
    video_files = []
    
    if voice_path.exists():
        audio_files = sorted([f.name for f in voice_path.iterdir() if f.is_file()])
    
    if video_path.exists():
        video_files = sorted([f.name for f in video_path.iterdir() if f.is_file()])
    
    return {
        "voice_directory": str(voice_path),
        "video_directory": str(video_path),
        "audio_files": audio_files,
        "video_files": video_files,
        "audio_file_count": len(audio_files),
        "video_file_count": len(video_files),
    }

