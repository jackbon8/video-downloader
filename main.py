import json
import os
import re
import time
from pathlib import Path
from typing import List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from yt_dlp import YoutubeDL

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/127.0.0.1 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.douyin.com/",
}


class DownloadError(RuntimeError):
    pass


def normalize_url(url: str) -> str:
    if not url:
        raise ValueError("URL is empty.")
    return url.strip()


def request_html(url: str, referer: Optional[str] = None, timeout: int = 20) -> str:
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = referer
    response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    response.raise_for_status()
    return response.text


def find_json_block(text: str) -> List[dict]:
    candidates = []
    for pattern in [
        r"<script[^>]*type=['\"]application/ld\+json['\"][^>]*>(.*?)</script>",
        r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});",
        r"__NEXT_DATA__\s*=\s*(\{.*?\});",
        r"\bJSON\.parse\(\s*json\s*\)\s*",
    ]:
        for match in re.finditer(pattern, text, re.S):
            block = match.group(1)
            if not block:
                continue
            try:
                obj = json.loads(block)
                candidates.append(obj)
            except Exception:
                pass
    return candidates


def extract_string(text: str, pattern: str) -> Optional[str]:
    match = re.search(pattern, text, re.S)
    if not match:
        return None
    value = match.group(1)
    return value.strip("\"'")


def resolve_redirect_url(url: str) -> str:
    try:
        response = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        response.raise_for_status()
        return response.url
    except Exception:
        return url


def pick_first_url(candidates: List[str]) -> Optional[str]:
    for item in candidates:
        if not item:
            continue
        if item.startswith("http"):
            return item
    return None


def get_direct_video_urls_from_html(html: str) -> List[str]:
    urls: Set[str] = set()
    patterns = [
        r"https?://[^\s\"'<>]+\.(?:mp4|m3u8)(?:\?[^\s\"'<>]*)?",
        r'"(https?://[^"\s<>]+(?:/video/|/play/|/download/)[^"\s<>]*)"',
        r"'(https?://[^'\s<>]+(?:/video/|/play/|/download/)[^'\s<>]*)'",
        r"(https?://[^\s\"'<>]+/[^\s\"'<>]*\.(?:mp4|mp4\?[^\s\"'<>]*))",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, html, re.S | re.I):
            candidate = match.group(1) if match.lastindex else match.group(0)
            if candidate.startswith("http"):
                urls.add(candidate)

    for key in ["videoUrl", "mp4Url", "playUrl", "play_url", "video_url", "downloadUrl"]:
        for match in re.finditer(rf'"{key}"\s*:\s*"(https?://[^"\\]+)"', html, re.S):
            urls.add(match.group(1))

    return sorted(urls)


def extract_douyin_user_id(profile_url: str, html: str) -> Optional[str]:
    page_url = resolve_redirect_url(profile_url)
    parsed = urlparse(page_url)
    path = parsed.path
    user_match = re.search(r"/(?:user|profile)/([^/?#]+)", path)
    if user_match:
        return user_match.group(1)

    for pattern in [
        r'"sec_user_id"\s*:\s*"([^"]+)"',
        r'"user_id"\s*:\s*"([^"]+)"',
        r'"uid"\s*:\s*"([^"]+)"',
        r'"user\"\s*:\s*\{[^\}]*"uid"\s*:\s*"([^"]+)"',
    ]:
        match = re.search(pattern, html)
        if match:
            return match.group(1)

    return None


def fetch_douyin_video_urls(profile_url: str) -> List[str]:
    html = request_html(profile_url, referer="https://www.douyin.com/")
    sec_user_id = extract_douyin_user_id(profile_url, html)
    if not sec_user_id:
        raise DownloadError("Could not extract Douyin user id from the page.")

    api_url = (
        "https://www.douyin.com/aweme/v1/web/aweme/post/"
        f"?sec_user_id={sec_user_id}&count=35&max_cursor=0&aid=6383&app_name=douyin_web"
    )

    response = requests.get(api_url, headers={**HEADERS, "Referer": profile_url}, timeout=20)
    response.raise_for_status()

    payload = response.json()
    items = payload.get("aweme_list", [])
    video_urls: List[str] = []
    for item in items:
        video = item.get("video") or {}
        play_addr = video.get("play_addr") or {}
        url_list = play_addr.get("url_list") or []
        if url_list:
            video_urls.append(url_list[0])
            continue
        raw = video.get("play_url") or item.get("video_url")
        if raw:
            video_urls.append(raw)

    if not video_urls:
        direct_urls = get_direct_video_urls_from_html(html)
        if direct_urls:
            video_urls.extend(direct_urls)

    return video_urls


def fetch_kuaishou_video_urls(profile_url: str) -> List[str]:
    html = request_html(profile_url, referer="https://www.kuaishou.com/")
    video_urls = get_direct_video_urls_from_html(html)
    if not video_urls:
        # Fallback: improve detection by scanning script blocks and JSON-like objects
        for block in re.findall(r"<script[^>]*>(.*?)</script>", html, re.S):
            if "video" in block.lower() or "mp4" in block.lower():
                video_urls.extend(get_direct_video_urls_from_html(block))
    return sorted(set(video_urls))


def download_video(url: str, output_dir: str, title: str) -> str:
    os.makedirs(output_dir, exist_ok=True)

    sanitized = re.sub(r"[^a-zA-Z0-9\-_]+", "_", title).strip("_") or "video"
    if not sanitized.endswith(".mp4"):
        sanitized = f"{sanitized}.mp4"

    output_path = str(Path(output_dir) / sanitized)

    opts = {
        "outtmpl": output_path,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "format": "best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "http_headers": {
            "Referer": "https://www.douyin.com/",
            "User-Agent": HEADERS["User-Agent"],
        },
    }

    try:
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception as exc:
        # Fallback: if yt-dlp cannot handle it, try a direct requests download.
        response = requests.get(url, headers=HEADERS, timeout=60)
        response.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)
        if os.path.getsize(output_path) == 0:
            raise DownloadError(f"Downloaded file is empty: {url}") from exc

    return output_path


def dedupe_video_list(items: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in items:
        if not item:
            continue
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def download_user_videos(platform: str, profile_url: str, output_dir: str):
    profile_url = normalize_url(profile_url)
    if platform == "douyin":
        raw_urls = fetch_douyin_video_urls(profile_url)
    elif platform == "kuaishou":
        raw_urls = fetch_kuaishou_video_urls(profile_url)
    else:
        raise ValueError(f"Unsupported platform: {platform}")

    urls = dedupe_video_list(raw_urls)
    if not urls:
        raise DownloadError(f"No playable video URLs were found for {profile_url}.")

    print(f"Found {len(urls)} video URL(s) for {platform} user page.")
    for index, video_url in enumerate(tqdm(urls, desc=f"Downloading {platform}", unit="video"), start=1):
        title = f"{platform}_{index}"
        try:
            download_video(video_url, output_dir, title)
            time.sleep(0.3)
        except Exception as exc:
            print(f"Failed to download {video_url}: {exc}")
            continue

    print(f"Saved outputs to {output_dir}")


if __name__ == "__main__":
    print("This module is intended to be imported. Use main.py to run the downloader.")
