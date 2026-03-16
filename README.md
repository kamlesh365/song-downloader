# Song Downloader

A simple, mobile-friendly web app to download songs as high-quality MP3 files. Enter song names (one per line), click Download, and get a zip file with your music.

## Requirements

- **Python 3.8+**
- **FFmpeg** – Required for audio conversion. [Download FFmpeg](https://ffmpeg.org/download.html) and add it to your PATH.

## Setup

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Ensure FFmpeg is installed and available in your PATH:
   ```bash
   ffmpeg -version
   ```

## Run

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser. On mobile, use your computer's local IP (e.g. `http://192.168.1.x:5000`) to access from the same network.

## Usage

1. Enter song names in the text area, one per line (e.g. `Artist - Song Name`)
2. Click **Download MP3**
3. A `songs.zip` file will download with all songs in MP3 format

**Tips for better results:**
- Include both artist and song title
- Add "official" to prefer official uploads
- Maximum 10 songs per download

## Legal Notice

Use only for content you have the right to download. Respect copyright and terms of service.
