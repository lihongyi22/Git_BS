from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routers import experiment, export, health, scales, subjects, surveys
from app.services.media import media_dirs

app = FastAPI(title="T2DM Thesis Experiment Platform (Python)", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health_check() -> dict:
    return {"ok": True}


app.include_router(subjects.router)
app.include_router(experiment.router)
app.include_router(surveys.router)
app.include_router(scales.router)
app.include_router(export.router)
app.include_router(health.router)

voice_dir, video_dir = media_dirs()
app.mount("/media/voice", StaticFiles(directory=voice_dir), name="voice_media")
app.mount("/media/video", StaticFiles(directory=video_dir), name="video_media")

static_dir = Path(__file__).resolve().parents[1] / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")
