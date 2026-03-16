"""
Song Downloader - Flask backend
Downloads songs in high-quality MP3 format using yt-dlp
"""
import os
import zipfile
import tempfile
import shutil
from pathlib import Path
from flask import Flask, request, jsonify, send_file, send_from_directory
import yt_dlp

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request

DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "song_downloader"
DOWNLOAD_DIR.mkdir(exist_ok=True)


def download_song(song_name: str, output_dir: Path) -> str | None:
    """Download a single song by name, returns path to MP3 or None on failure."""
    if not song_name or not song_name.strip():
        return None

    song_name = song_name.strip()
    # Use ytsearch to find the song on YouTube
    search_query = f"ytsearch1:{song_name}"

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(output_dir / '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '0',  # Best quality
        }],
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
    """Accept list of song names, download as MP3, return zip file."""
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

    temp_dir = tempfile.mkdtemp(dir=DOWNLOAD_DIR)
    output_path = Path(temp_dir)
    downloaded = []

    try:
        for song_name in songs:
            mp3_path = download_song(song_name, output_path)
            if mp3_path:
                downloaded.append(Path(mp3_path).name)

        if not downloaded:
            return jsonify({'error': 'Failed to download any songs. Check song names and ensure FFmpeg is installed.'}), 500

        # Create zip file
        zip_path = output_path / "songs.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for mp3_file in output_path.glob("*.mp3"):
                zf.write(mp3_file, mp3_file.name)

        return send_file(
            zip_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name='songs.zip'
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
