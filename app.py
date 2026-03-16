"""
Song Downloader - Flask backend
Downloads songs in high-quality MP3 format using yt-dlp
"""
import os
import zipfile
import tempfile
import shutil
import time
import uuid
from pathlib import Path
from flask import Flask, request, jsonify, send_file, send_from_directory
from werkzeug.utils import secure_filename
import yt_dlp

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request

DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "song_downloader"
DOWNLOAD_DIR.mkdir(exist_ok=True)

DOWNLOAD_TTL_SECONDS = int(os.environ.get("DOWNLOAD_TTL_SECONDS", "3600"))  # 1 hour


def cleanup_old_downloads() -> None:
    """Best-effort cleanup of old download folders."""
    now = time.time()
    try:
        for p in DOWNLOAD_DIR.iterdir():
            if not p.is_dir():
                continue
            try:
                age = now - p.stat().st_mtime
            except OSError:
                continue
            if age > DOWNLOAD_TTL_SECONDS:
                shutil.rmtree(p, ignore_errors=True)
    except OSError:
        return


def make_mp3_filename(song_name: str, used: set[str]) -> str:
    base = secure_filename(song_name).strip("._- ").replace("_", " ")
    if not base:
        base = "song"
    name = f"{base}.mp3"
    if name.lower() not in used:
        used.add(name.lower())
        return name
    i = 2
    while True:
        name = f"{base} ({i}).mp3"
        if name.lower() not in used:
            used.add(name.lower())
            return name
        i += 1


def resolve_ffmpeg_location() -> str | None:
    """
    Return a path yt-dlp can use to locate ffmpeg/ffprobe.
    Prefers explicit env var, then common Windows install locations.
    """
    env_loc = os.environ.get("FFMPEG_LOCATION") or os.environ.get("FFMPEG_PATH")
    candidates: list[Path] = []
    if env_loc:
        candidates.append(Path(env_loc))

    # Common locations for manual installs on Windows
    candidates.extend([
        Path(r"C:\ffmpeg\bin"),
        Path(r"C:\Tools\ffmpeg\bin"),
    ])

    for p in candidates:
        try:
            if p.is_dir():
                if (p / "ffmpeg.exe").exists() and (p / "ffprobe.exe").exists():
                    return str(p)
            elif p.is_file():
                # allow pointing directly at ffmpeg.exe
                if p.name.lower() == "ffmpeg.exe" and p.exists():
                    return str(p)
        except OSError:
            continue

    return None


def download_song(song_name: str, output_dir: Path) -> str | None:
    """Download a single song by name, returns path to MP3 or None on failure."""
    if not song_name or not song_name.strip():
        return None

    song_name = song_name.strip()
    # Use ytsearch to find the song on YouTube
    search_query = f"ytsearch1:{song_name}"

    ffmpeg_location = resolve_ffmpeg_location()
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(output_dir / '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '0',  # Best quality
        }],
        # Avoid relying on PATH (common issue on Windows)
        **({'ffmpeg_location': ffmpeg_location} if ffmpeg_location else {}),
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([search_query])

        # Find the downloaded MP3 (yt-dlp renames to .mp3)
        for f in output_dir.glob("*.mp3"):
            return str(f)
        return None
    except Exception:
        return None


@app.route('/')
def index():
    """Serve the main page."""
    return send_from_directory('static', 'index.html')


@app.route('/api/download', methods=['POST'])
def download():
    """Accept list of song names, download as MP3, return direct downloads."""
    cleanup_old_downloads()
    data = request.get_json()
    if not data or 'songs' not in data:
        return jsonify({'error': 'Please provide a list of songs'}), 400

    songs = data['songs']
    if not isinstance(songs, list):
        songs = [s.strip() for s in str(songs).split('\n') if s.strip()]
    else:
        songs = [s.strip() for s in songs if s and str(s).strip()]

    if not songs:
        return jsonify({'error': 'No valid song names provided'}), 400

    # Limit to 10 songs per request to avoid timeout
    if len(songs) > 10:
        return jsonify({'error': 'Maximum 10 songs per request'}), 400

    token = uuid.uuid4().hex
    output_path = (DOWNLOAD_DIR / token)
    output_path.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()
    downloaded_files: list[dict[str, str]] = []

    try:
        for song_name in songs:
            mp3_path = download_song(song_name, output_path)
            if not mp3_path:
                continue

            src = Path(mp3_path)
            target_name = make_mp3_filename(song_name, used_names)
            dst = output_path / target_name
            try:
                if src.resolve() != dst.resolve():
                    if dst.exists():
                        dst.unlink(missing_ok=True)
                    src.rename(dst)
            except Exception:
                # If rename fails, keep original filename
                dst = src

            downloaded_files.append({
                "name": dst.name,
                "url": f"/api/mp3/{token}/{dst.name}",
            })

        if not downloaded_files:
            return jsonify({'error': 'Failed to download any songs. Check song names and ensure FFmpeg is installed.'}), 500

        # Single file: return the mp3 directly for best UX
        if len(downloaded_files) == 1:
            only = downloaded_files[0]["name"]
            return send_file(
                output_path / only,
                mimetype="audio/mpeg",
                as_attachment=True,
                download_name=only,
            )

        # Multiple files: return a list of per-file download links
        return jsonify({
            "count": len(downloaded_files),
            "downloads": downloaded_files,
        })
    finally:
        # Files are served via /api/mp3/<token>/... for a short TTL
        try:
            output_path.touch(exist_ok=True)
        except OSError:
            pass


@app.route("/api/mp3/<token>/<path:filename>", methods=["GET"])
def download_mp3(token: str, filename: str):
    base = (DOWNLOAD_DIR / token)
    if not base.exists() or not base.is_dir():
        return jsonify({"error": "Download expired. Please try again."}), 404
    return send_from_directory(base, filename, as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
