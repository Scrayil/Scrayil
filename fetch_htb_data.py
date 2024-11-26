import json
import os
import time

from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
import requests


def create_rank_animation(driver):
    # Creating a GIF of the rank's animation
    element = driver.find_element(By.CSS_SELECTOR, "#waves")
    fps = 60
    n_frames = fps * 5
    for i in range(n_frames):  # Retrieving 300 frames
        if i == 0:
            element.screenshot(f"data/htb/rank_animation_frame.png")
        element.screenshot(f"screenshots/frame_{i:03d}.png")
        time.sleep(1/fps)  # (60 fps)

    # Loading all frames as images
    frames = [Image.open(f"screenshots/{frame}") for frame in sorted(os.listdir("screenshots/"))]
    frame_duration = int(1000 / fps)
    # Creating a gif for the HTB rank
    frames[0].save(
        "data/htb/htb_rank.gif",
        save_all=True,
        append_images=frames[1:],  # The following frames
        duration=frame_duration,  # Frame duration
        loop=0  # Infinite loop
    )


def fetch_htb_progress_images():
    # Configuring Firefox to get for the high resolution
    options = Options()
    options.add_argument("--headless")
    options.set_preference("layout.css.devPixelsPerPx", "3.0")  # Scaling the pixel density

    # Initializing the web driver
    service = Service("/snap/bin/firefox.geckodriver")
    driver = webdriver.Firefox(service=service, options=options)

    try:
        # Loading the webpage
        driver.set_window_size(1920, 1080)  # Setting the window size to Full HD
        driver.get("https://app.hackthebox.com/profile/498656")
        # FIRST STATS ROW
        # Creating a video animation of the rank
        create_rank_animation(driver)
        # Taking screenshots of the other elements
        rank_details_css_prefix = "#UserRankDetails > div:nth-child(1) > div:nth-child(1) > "
        rank_progress_elem = driver.find_element(By.CSS_SELECTOR, rank_details_css_prefix + "div:nth-child(2)")
        rank_progress_elem.screenshot("data/htb/rank_progress.png")
        ownership_elem = driver.find_element(By.CSS_SELECTOR, rank_details_css_prefix + "div:nth-child(3)")
        ownership_elem.screenshot("data/htb/ownership.png")
        # SECOND STATS ROW
        badges = ["global_rank.png", "final_score.png", "user_owns.png", "system_owns.png", "respect.png"]
        rank_details_css_prefix = "#UserRankDetails > div:nth-child(2) > div:nth-child(1) > div:nth-child(1) > "
        for i, badge in enumerate(badges):
            badge_elem = driver.find_element(By.CSS_SELECTOR, rank_details_css_prefix + f"div:nth-child({8 + i}) > div:nth-child(1) > div:nth-child(1) > div:nth-child(1)")
            badge_elem.screenshot(f"data/htb/{badge}")
    finally:
        driver.quit()

def fetch_activity():
    try:
        # RETRIEVING ALL ACTIVITY NOW
        s = requests.Session()
        req = s.get("https://www.hackthebox.com/api/v4/profile/activity/498656", headers={"User-Agent": "Mozilla/5.0"})
        if 199 < req.status_code < 300:
            activities = json.loads(req.text)["profile"]["activity"]
            with open("README.md", "r+") as f:
                lines = f.readlines()
                for idx, line in enumerate(lines):
                    if "<!-- HTB Activities-Start -->" in line:
                        details_idx = idx
                readme_data = "".join(lines[:details_idx]) + "<!-- HTB Activities-Start --><br>\n"
                for activity in activities:
                    if activity["object_type"] != "machine" or activity["type"] == "user":
                        continue
                    readme_data+= f'    <img src="https://labs.hackthebox.com/{activity["machine_avatar"]}" alt="{activity["name"]}" />\n'
                readme_data += "</details>\n"
                f.seek(0)
                f.truncate()
                f.write(readme_data)
    except requests.exceptions.RequestException:
        print("Failed to fetch activity")
        exit(1)

def main():
    if not os.path.exists("data/htb"):
        os.makedirs("data/htb")
    if not os.path.exists("screenshots"):
        os.makedirs("screenshots")

    fetch_htb_progress_images()
    fetch_activity()



if __name__ == '__main__':
    main()
