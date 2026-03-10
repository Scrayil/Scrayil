"""
Automated Hack The Box profile synchronization and activity processing.
"""

import json
import os
import re
import tempfile
import time
from pathlib import Path

import requests
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service


README_PATH = Path("README.md")
MARKER_START = "<!-- HTB Activities-Start -->"
MARKER_END = "<!-- HTB Activities-Stop -->"


def create_rank_images(driver: webdriver.Firefox) -> None:
    """
    Generates two png images from the user rank elements.

    Args:
        driver (webdriver.Firefox): The configured Selenium WebDriver instance.
    """
    elements = driver.find_elements(By.CSS_SELECTOR, ".common-stats-card__root__top-section")
    data_dir = Path("data/htb")
    data_dir.mkdir(parents=True, exist_ok=True)
    elements[0].screenshot(str(data_dir / "rank.png"))
    elements[1].screenshot(str(data_dir / "points.png"))


def fetch_htb_progress_images() -> None:
    """
    Captures high-resolution profile statistics using a headless browser.
    """
    options = Options()
    options.add_argument("--headless")
    options.set_preference("layout.css.devPixelsPerPx", "3.0")

    service = Service()
    driver = webdriver.Firefox(service=service, options=options)

    try:
        driver.set_window_size(1920, 1080)
        driver.get("https://app.hackthebox.com/profile/498656")

        create_rank_images(driver)

        # rank_details_css_prefix = "#UserRankDetails > div:nth-child(1) > div:nth-child(1) > "
        # rank_progress_elem = driver.find_element(By.CSS_SELECTOR, rank_details_css_prefix + "div:nth-child(2)")
        # rank_progress_elem.screenshot("data/htb/rank_progress.png")

        # ownership_elem = driver.find_element(By.CSS_SELECTOR, rank_details_css_prefix + "div:nth-child(3)")
        # ownership_elem.screenshot("data/htb/ownership.png")

        # badges = ["global_rank.png", "final_score.png", "user_owns.png", "system_owns.png", "respect.png"]
        # rank_details_css_prefix = "#UserRankDetails > div:nth-child(2) > div:nth-child(1) > div:nth-child(1) > "
        # for i, badge in enumerate(badges):
        #     badge_elem = driver.find_element(
        #         By.CSS_SELECTOR,
        #         rank_details_css_prefix + f"div:nth-child({8 + i}) > div:nth-child(1) > div:nth-child(1) > div:nth-child(1)"
        #     )
        #     badge_elem.screenshot(f"data/htb/{badge}")
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
    existing_images = get_existing_images_from_readme()

    try:
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        response = session.get("https://labs.hackthebox.com/api/v4/profile/activity/498656", timeout=15)
        response.raise_for_status()
        activities = response.json().get("profile", {}).get("activity", [])
    except requests.RequestException:
        raise SystemExit("Failed to fetch activity")

    new_html_lines = ["<br>\n"]

    for activity in activities:
        if activity.get("object_type") != "machine" or activity.get("type") == "user":
            continue

        machine_name = activity.get("name", "Unknown")
        avatar_path = activity.get("machine_avatar", "")
        if avatar_path.startswith("/"):
            avatar_path = avatar_path[1:]

        full_url = f"https://htb-mp-prod-public-storage.s3.eu-central-1.amazonaws.com/{avatar_path}"
        existing_src = existing_images.get(machine_name, "")

        final_src = cache_image_locally(full_url, machine_name, existing_src, session)
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


if __name__ == '__main__':
    main()
