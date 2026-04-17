# VDROP — Self-Hosted YouTube Downloader

A clean, fast, self-hosted video downloader built with **FastAPI + yt-dlp**.  
Supports MP4 (multi-quality), MP3, and playlist downloads.

---

## Project Structure

```
ytdl/
├── main.py              # FastAPI backend
├── static/
│   └── index.html       # Frontend UI
├── downloads/           # Temp download storage (auto-cleaned)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── nginx.conf           # Nginx reverse proxy config
└── cleanup.sh           # Cron-based cleanup script
```

---

## 🚀 Deploy on VPS (Recommended: Docker)

### 1. Install Docker on your VPS

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in
```

### 2. Clone / upload your project files

```bash
scp -r ./ytdl user@your-vps-ip:/home/user/vdrop
ssh user@your-vps-ip
cd /home/user/vdrop
```

### 3. Start the app

```bash
docker compose up -d --build
```

App is now running on `http://your-vps-ip:8000`

---

## 🌐 Set Up Domain + HTTPS (Nginx + Let's Encrypt)

### Install Nginx and Certbot

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

### Get SSL certificate

```bash
sudo certbot --nginx -d yourdomain.com
```

### Configure Nginx

```bash
sudo cp nginx.conf /etc/nginx/sites-available/vdrop
# Edit the file to replace "yourdomain.com" with your actual domain
sudo nano /etc/nginx/sites-available/vdrop

sudo ln -s /etc/nginx/sites-available/vdrop /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Now your app is live at `https://yourdomain.com` ✅

---

## 🔄 Auto-Cleanup Old Downloads (Cron)

Add a cron job inside the container to delete files older than 30 min:

```bash
# On host machine, edit crontab
crontab -e

# Add this line:
*/10 * * * * docker exec vdrop bash /app/cleanup.sh >> /tmp/vdrop-cleanup.log 2>&1
```

---

## 🛠 Running Without Docker (bare metal)

### Requirements
- Python 3.11+
- ffmpeg installed (`sudo apt install ffmpeg`)

```bash
cd ytdl
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Use `screen` or `systemd` to keep it running:

```bash
# With screen:
screen -S vdrop
uvicorn main:app --host 0.0.0.0 --port 8000
# Ctrl+A, D to detach
```

---

## 🔧 Updating yt-dlp

YouTube changes frequently. Update yt-dlp when downloads break:

```bash
# If using Docker:
docker exec vdrop pip install -U yt-dlp

# Or rebuild the container:
docker compose down && docker compose up -d --build
```

---

## ⚙️ Configuration

Edit `main.py` to customize:
- `DOWNLOADS_DIR` — where files are stored
- MP3 quality (default: 192kbps) — find `preferredquality`
- Retry count — find `"retries": 3`

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/info` | Fetch video metadata |
| POST | `/api/download` | Start a download job |
| GET | `/api/status/{job_id}` | Poll job progress |
| GET | `/api/file/{job_id}/{filename}` | Download the file |
| DELETE | `/api/cleanup/{job_id}` | Delete job files |

---

## Notes

- Downloads are stored temporarily in `./downloads/` and cleaned up automatically
- Concurrent downloads are supported (each gets a unique job ID)
- Playlist downloads can take a long time — the UI will show progress
- For personal/private use only — respect YouTube's ToS
