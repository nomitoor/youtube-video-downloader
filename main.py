import os
import uuid
import asyncio
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp

app = FastAPI(title="YT Downloader")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)

# In-memory job store
jobs: dict[str, dict] = {}


class InfoRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    format: str  # "mp3", "mp4"
    quality: Optional[str] = "best"  # "360", "480", "720", "1080", "best"
    playlist: bool = False


def get_ydl_opts(job_id: str, fmt: str, quality: str, playlist: bool) -> dict:
    output_template = str(DOWNLOADS_DIR / job_id / "%(title)s.%(ext)s")

    def progress_hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            percent = int(downloaded / total * 100) if total else 0
            speed = d.get("_speed_str", "").strip()
            eta = d.get("_eta_str", "").strip()
            jobs[job_id].update({
                "status": "downloading",
                "percent": percent,
                "speed": speed,
                "eta": eta,
                "filename": d.get("filename", ""),
            })
        elif d["status"] == "finished":
            jobs[job_id]["status"] = "processing"

    base_opts = {
        "outtmpl": output_template,
        "progress_hooks": [progress_hook],
        "noplaylist": not playlist,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
    }

    if fmt == "mp3":
        base_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        # MP4 video
        if quality == "best":
            fmt_str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        else:
            fmt_str = f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}][ext=mp4]/best[height<={quality}]"
        base_opts.update({
            "format": fmt_str,
            "merge_output_format": "mp4",
        })

    return base_opts


async def run_download(job_id: str, url: str, fmt: str, quality: str, playlist: bool):
    job_dir = DOWNLOADS_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    try:
        opts = get_ydl_opts(job_id, fmt, quality, playlist)
        loop = asyncio.get_event_loop()
        def do_download():
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        await loop.run_in_executor(None, do_download)

        # Find downloaded files
        files = list(job_dir.glob("*"))
        if not files:
            raise Exception("No files downloaded")

        jobs[job_id]["status"] = "done"
        jobs[job_id]["files"] = [f.name for f in files]
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


@app.post("/api/info")
async def get_info(req: InfoRequest):
    """Fetch video metadata (title, thumbnail, formats, duration)."""
    try:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": False,
        }
        loop = asyncio.get_event_loop()
        def fetch():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(req.url, download=False)
        info = await loop.run_in_executor(None, fetch)

        is_playlist = info.get("_type") == "playlist"
        entries = info.get("entries", [info]) if is_playlist else [info]
        first = entries[0] if entries else info

        # Available video heights
        formats = first.get("formats", [])
        heights = sorted({
            f["height"] for f in formats
            if f.get("height") and f.get("vcodec") != "none"
        }, reverse=True)

        return {
            "title": info.get("title") or first.get("title", "Unknown"),
            "thumbnail": first.get("thumbnail", ""),
            "duration": first.get("duration", 0),
            "uploader": first.get("uploader", ""),
            "view_count": first.get("view_count", 0),
            "is_playlist": is_playlist,
            "playlist_count": len(entries) if is_playlist else 1,
            "available_heights": heights[:6],  # top 6 qualities
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/download")
async def start_download(req: DownloadRequest, background_tasks: BackgroundTasks):
    """Queue a download job and return job_id."""
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued", "percent": 0, "speed": "", "eta": "", "files": []}
    background_tasks.add_task(run_download, job_id, req.url, req.format, req.quality, req.playlist)
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def job_status(job_id: str):
    """Poll download status."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


@app.get("/api/file/{job_id}/{filename}")
async def serve_file(job_id: str, filename: str):
    """Serve a completed download."""
    file_path = DOWNLOADS_DIR / job_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream",
    )


@app.delete("/api/cleanup/{job_id}")
async def cleanup_job(job_id: str):
    """Delete downloaded files after user grabs them."""
    job_dir = DOWNLOADS_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    jobs.pop(job_id, None)
    return {"ok": True}


# Serve frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")
