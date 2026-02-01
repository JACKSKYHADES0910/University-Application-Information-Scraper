from utils.browser import get_driver
import time

try:
    print("Testing driver launch...")
    driver = get_driver(headless=False, fast_mode=False)
    print("Driver launched successfully.")
    driver.get("https://google.com")
    print("Page loaded.")
    time.sleep(2)
    driver.quit()
    print("Driver closed.")
except Exception as e:
    print(f"Driver failed: {e}")
