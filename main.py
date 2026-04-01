### DATA EXTRACTION & REFINEMENT BOT - CNN WORLDWIDE

import csv
import logging
import os
from typing import List, Set

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def setup_logger() -> logging.Logger:
    """Initialize the application logger with a standard format."""
    logger = logging.getLogger("cnn_scraper")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logger()


# get_driver: initializes the Chrome engine in headless mode for server-side performance
def get_driver(headless: bool = True) -> webdriver.Chrome:
    """Start a Chrome WebDriver instance ready for automated data extraction."""
    options = Options()

    if headless:
        options.add_argument("--headless")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    return driver


# clean_text: performs string sanitization to remove line breaks and ensure CSV integrity
def clean_text(text: str) -> str:
    """Normalize raw text to high-quality CSV content."""
    if not text:
        return ""

    cleaned = " ".join(text.split())
    cleaned = cleaned.strip('"').strip("'")
    return cleaned


# is_valid_headline: this is the filtering engine used to discard image credits (Getty/AP), ads, and navigation noise
def is_valid_headline(text: str, link: str, seen_urls: Set[str]) -> bool:
    """Return True when a link is a valid news headline for CSV export."""
    if not text or not link:
        return False

    link = link.strip()
    cleaned_text = clean_text(text)

    if not link.startswith("http"):
        return False

    if "cnn.com" not in link:
        return False

    if link in seen_urls:
        return False

    lower = cleaned_text.lower()
    if len(lower.split()) < 4:
        return False

    if any(keyword in lower for keyword in ["getty", "ap", "reuters", "photo", "jpg", "png", "gif"]):
        return False

    bad_paths = ["/video", "/watch", "/live", "/audio/", "/podcasts/", "#", "/menu", "/rss", "/newsletter"]
    if any(segment in link for segment in bad_paths):
        return False

    excluded_phrases = ["terms", "privacy", "accessibility", "sign up", "newsletter", "courtesy", "see all", "live updates"]
    if any(phrase in lower for phrase in excluded_phrases):
        return False

    unexpected_labels = ["button", "learn more", "subscribe", "read more", "close"]
    if any(label in lower for label in unexpected_labels):
        return False

    return True


def save_to_csv(rows: List[dict], output_file: str) -> int:
    """Data structuring: write final headlines to CSV with 3-digit automated indexing."""
    with open(output_file, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["ID", "MANCHETE", "URL"])

        for idx, row in enumerate(rows, 1):
            writer.writerow([
                f"{idx:03d}",
                row["headline"].strip(),
                row["url"].strip(),
            ])

    return len(rows)


def scrape_cnn(output_file: str = "cnn_data.csv") -> int:
    """Execute extraction workflow and persist refined data."""
    logger.info("Extraction started")

    url = "https://www.cnn.com/"
    seen_urls: Set[str] = set()
    rows: List[dict] = []

    with get_driver(headless=True) as driver:
        try:
            driver.get(url)
        except (TimeoutException, WebDriverException) as exc:
            logger.error("Failed to load CNN homepage: %s", exc)
            return 0

        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a")))
        except TimeoutException:
            logger.error("No links found on CNN page in wait duration")
            return 0

        elements = driver.find_elements(By.CSS_SELECTOR, "a")
        logger.info("Found %d link elements", len(elements))

        for element in elements:
            try:
                raw_text = element.text
                raw_link = element.get_attribute("href")
            except (NoSuchElementException, WebDriverException):
                continue

            normalized_text = clean_text(raw_text)
            normalized_link = raw_link.strip() if raw_link else ""

            if is_valid_headline(normalized_text, normalized_link, seen_urls):
                seen_urls.add(normalized_link)
                rows.append({"headline": normalized_text, "url": normalized_link})

    if not rows:
        logger.warning("Extraction completed with 0 valid headlines")
        print(f"? Process completed: 0 headlines saved in {output_file}")
        return 0

    total_saved = save_to_csv(rows, output_file)
    logger.info("Data saved successfully")

    print(f"? Process completed: {total_saved} headlines saved in {output_file}")
    return total_saved


def main() -> None:
    """Main entrypoint for industrial-grade data extraction command."""
    os.makedirs("data", exist_ok=True)
    try:
        output_file = "data/cnn_data.csv"
        scrape_cnn(output_file=output_file)

    except Exception as exc:
        logger.exception("Unhandled exception during execution: %s", exc)


if __name__ == "__main__":
    main()
