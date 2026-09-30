#!/usr/bin/env python3

import argparse
import os
import sys
from pathlib import Path

from video_downloader import download_user_videos


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download all videos from a Douyin or Kuaishou user homepage."
    )
    parser.add_argument(
        "--douyin-url",
        help="Douyin user home page or user sharing link.",
        default=None,
    )
    parser.add_argument(
        "--kuaishou-url",
        help="Kuaishou user home page URL.",
        default=None,
    )
    parser.add_argument(
        "--output-dir",
        help="Directory to save downloaded videos.",
        default="./downloads",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.douyin_url and not args.kuaishou_url:
        print("Please provide at least one of --douyin-url or --kuaishou-url.")
        sys.exit(1)

    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    if args.douyin_url:
        douyin_dir = output_root / "douyin"
        douyin_dir.mkdir(parents=True, exist_ok=True)
        print(f"[Douyin] starting download from {args.douyin_url}")
        download_user_videos(
            platform="douyin",
            profile_url=args.douyin_url,
            output_dir=str(douyin_dir),
        )

    if args.kuaishou_url:
        kuaishou_dir = output_root / "kuaishou"
        kuaishou_dir.mkdir(parents=True, exist_ok=True)
        print(f"[Kuaishou] starting download from {args.kuaishou_url}")
        download_user_videos(
            platform="kuaishou",
            profile_url=args.kuaishou_url,
            output_dir=str(kuaishou_dir),
        )

    print("All tasks complete.")


if __name__ == "__main__":
    main()
