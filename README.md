# Video Downloader

A Python tool that downloads all videos from a Douyin or Kuaishou user homepage URL.

## Features

- Supports Douyin user homepages
- Supports Kuaishou user homepages
- Downloads all discovered videos to a local directory
- Handles direct mp4 links and adopts yt-dlp for compatibility
- Can accept both Douyin and Kuaishou URLs together in one run

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

## Usage

Download Douyin videos:

```bash
python main.py --douyin-url "https://www.douyin.com/user/xxxxxxxxx" --output-dir ./downloads/douyin
```

Download Kuaishou videos:

```bash
python main.py --kuaishou-url "https://www.kuaishou.com/profile/xxxxxxxxx" --output-dir ./downloads/kuaishou
```

Download both in one run:

```bash
python main.py \
  --douyin-url "https://www.douyin.com/user/xxxxxxxxx" \
  --kuaishou-url "https://www.kuaishou.com/profile/xxxxxxxxx" \
  --output-dir ./downloads
```

## Important notes

- Some platforms restrict automated access and may require browser-like headers or anti-bot handling.
- This project is intended for personal, authorized use only.
- Respect platform copyright and user privacy rules.

## Disclaimer

This script is for educational and personal use. Confirm that you have permission to download the target content before using it.
