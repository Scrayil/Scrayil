"""
Automated Hack The Box profile synchronization and activity processing.
"""

import json
import os
import re
import tempfile
import time
from pathlib import Path
import traceback

import requests
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

RANK_PROFILE_URL="https://profile.hackthebox.com/profile/019e4906-1313-717c-aeb0-cf4bc73841b3?utm_medium=copy_url"
API_ACTIVITY_URL="https://labs.hackthebox.com/api/v5/user/profile/activity/498656"
README_PATH = Path("README.md")
MARKER_START = "<!-- HTB Activities-Start -->"
MARKER_END = "<!-- HTB Activities-Stop -->"
ERROR=0

def create_rank_images(driver: webdriver.Firefox) -> None:
    """
    Generates a png image from the user rank elements.

    Args:
        driver (webdriver.Firefox): The configured Selenium WebDriver instance.
    """
    elements = driver.find_elements(By.CSS_SELECTOR, ".rank-image-grid-decor")
    data_dir = Path("data/htb")
    data_dir.mkdir(parents=True, exist_ok=True)
    elements[0].screenshot(str(data_dir / "rank.png"))


def fetch_htb_progress_images() -> None:
    """
    Captures high-resolution profile statistics using a headless browser.
    """
    global ERROR
    options = Options()
    options.add_argument("--headless")
    options.set_preference("layout.css.devPixelsPerPx", "3.0")
    if firefox_bin := os.environ.get("FIREFOX_BIN"):
        options.binary_location = firefox_bin

    service = Service(executable_path=os.environ.get("GECKODRIVER_PATH"))
    driver = webdriver.Firefox(service=service, options=options)

    try:
        driver.set_window_size(1920, 1080)
        driver.get(RANK_PROFILE_URL)

        create_rank_images(driver)
    except:
        traceback.print_exc()
        ERROR = 1
    finally:
        driver.quit()


def get_existing_images_from_readme() -> dict[str, str]:
    """
    Extracts existing image sources from the README activity block for fallback usage.

    Returns:
        dict[str, str]: Dictionary mapping image alt text to their source URLs.
    """
    existing_images = {}
    if not README_PATH.exists():
        return existing_images

    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    start_idx = content.find(MARKER_START)
    end_idx = content.find(MARKER_END)

    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
        block = content[start_idx + len(MARKER_START) : end_idx]
        img_pattern = re.compile(r'<img\s+src="([^"]+)"\s+alt="([^"]+)"')
        for match in img_pattern.finditer(block):
            src = match.group(1)
            alt = match.group(2)
            existing_images[alt] = src

    return existing_images


def cache_image_locally(url: str, alt_name: str, existing_src: str, session: requests.Session) -> str:
    """
    Attempts to cache an image locally. Falls back to the existing source if the request fails.

    Args:
        url (str): The remote URL of the image.
        alt_name (str): The alternative text used to generate the local filename.
        existing_src (str): The fallback source path if the remote request fails.
        session (requests.Session): The active requests session.

    Returns:
        str: The path or URL to be used in the generated HTML.
    """
    avatars_dir = Path("data/htb/avatars")
    avatars_dir.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(c for c in alt_name if c.isalnum() or c in (' ', '_', '-')).rstrip()
    local_path = avatars_dir / f"{safe_name}.png"

    try:
        response = session.get(url, stream=True, timeout=10)
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return str(local_path).replace("\\", "/")
    except requests.RequestException:
        pass

    return existing_src if existing_src else url


def fetch_activity() -> None:
    """
    Retrieves recent activity and updates the README file with localized images.
    """
    global ERROR
    existing_images = get_existing_images_from_readme()
    meta = None
    page = 1
    activities = []

    try:
        with requests.Session() as session:
            session.headers.update({"User-Agent": "Mozilla/5.0"})
            last_page = 1
            while page <= last_page:
                response = session.get(API_ACTIVITY_URL, params={"page": page}, timeout=15)
                response.raise_for_status()
                body = response.json()
                activities.extend(body.get("data", []))
                last_page = body.get("meta", {}).get("lastPage", page)
                page += 1
    except requests.RequestException:
        traceback.print_exc()
        ERROR = 1
        if not activities:
            return None
        print(f"WARNING: partial fetch, stopped at page {page}/{last_page}", file=sys.stderr)


    new_html_lines = ["<br>\n"]

    for activity in activities:
        avatar_url = activity.get("avatar", "")

        if "machine" not in avatar_url or activity.get("type", "") not in ["user", "root"]:
            continue

        machine_name = activity.get("name", "Unknown")
        existing_src = existing_images.get(machine_name, "")

        final_src = cache_image_locally(avatar_url, machine_name, existing_src, session)
        new_html_lines.append(f'    <img src="{final_src}" alt="{machine_name}" width="64px" height="64px"/>\n')

    new_block = "".join(new_html_lines)

    if README_PATH.exists():
        with open(README_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        start_idx = content.find(MARKER_START)
        end_idx = content.find(MARKER_END)

        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            pre_content = content[:start_idx + len(MARKER_START)]
            post_content = content[end_idx:]
            
            updated_content = f"{pre_content}\n{new_block}{post_content}"

            with open(README_PATH, "w", encoding="utf-8") as f:
                f.write(updated_content)


def main() -> None:
    """
    Entry point for the HTB synchronization process.
    """
    fetch_htb_progress_images()
    fetch_activity()
    exit(ERROR)


if __name__ == '__main__':
    main()
