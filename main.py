"""
CNN Data Extraction & Refinement Bot - Professional Edition

A production-ready web scraper for automated CNN news headline extraction.
Built with Selenium WebDriver, featuring robust error handling, intelligent filtering,
and clean data export capabilities.

Features:
- Intelligent multi-layer filtering engine
- Headless Chrome automation with visual mode option
- Explicit wait strategies for reliable DOM interaction
- Duplicate prevention and data sanitization
- Professional logging and error handling
- CSV export with automated indexing

Author: [Your Name] - Senior Python Developer
Date: April 2026
"""

import csv
import logging
import os
import time
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


def get_driver(headless: bool = False) -> webdriver.Chrome:
    """
    Initialize a Chrome WebDriver instance with optimized settings.

    Args:
        headless: Whether to run browser in headless mode (background)

    Returns:
        Configured Chrome WebDriver instance
    """
    options = Options()

    if headless:
        options.add_argument("--headless")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    try:
        driver = webdriver.Chrome(options=options)
        logger.info("Chrome WebDriver initialized successfully")
        return driver
    except Exception as e:
        logger.error(f"Failed to initialize WebDriver: {e}")
        raise


def clean_text(text: str) -> str:
    """
    Perform string sanitization to ensure CSV integrity.

    Args:
        text: Raw text to clean

    Returns:
        Cleaned text safe for CSV export
    """
    if not text:
        return ""

    cleaned = " ".join(text.split())
    cleaned = cleaned.strip('"').strip("'")
    return cleaned


def is_valid_headline(text: str, link: str, seen_urls: Set[str]) -> bool:
    """
    Multi-layer validation engine for news headlines.

    Filters out image credits, ads, navigation elements, and low-quality content.

    Args:
        text: Headline text
        link: URL string
        seen_urls: Set of already processed URLs

    Returns:
        True if headline is valid for export
    """
    if not text or not link:
        return False

    link = link.strip()
    cleaned_text = clean_text(text)

    # Basic URL validation
    if not link.startswith("http"):
        return False

    if "cnn.com" not in link:
        return False

    # Duplicate check
    if link in seen_urls:
        return False

    lower = cleaned_text.lower()

    # Minimum word count
    if len(lower.split()) < 4:
        return False

    # Media credit filtering
    media_keywords = ["getty", "ap", "reuters", "photo", "jpg", "png", "gif", "corbis", "shutterstock"]
    if any(keyword in lower for keyword in media_keywords):
        return False

    # Bad URL path filtering
    bad_paths = ["/video", "/watch", "/live", "/audio/", "/podcasts/", "#", "/menu", "/rss", "/newsletter"]
    if any(segment in link for segment in bad_paths):
        return False

    # Navigation and system link filtering
    excluded_phrases = [
        "terms", "privacy", "accessibility", "sign up", "newsletter",
        "courtesy", "see all", "live updates", "advertisement", "sponsored"
    ]
    if any(phrase in lower for phrase in excluded_phrases):
        return False

    # UI element filtering
    ui_labels = ["button", "learn more", "subscribe", "read more", "close", "menu", "search"]
    if any(label in lower for label in ui_labels):
        return False

    return True


def save_to_csv(rows: List[dict], output_file: str) -> int:
    """
    Write validated headlines to CSV with structured formatting.

    Args:
        rows: List of headline dictionaries
        output_file: Path to output CSV file

    Returns:
        Number of rows saved
    """
    try:
        with open(output_file, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(["ID", "MANCHETE", "URL"])

            for idx, row in enumerate(rows, 1):
                writer.writerow([
                    f"{idx:03d}",
                    row["headline"].strip(),
                    row["url"].strip(),
                ])

        logger.info("Successfully saved %d rows to %s", len(rows), output_file)
        return len(rows)

    except Exception as exc:
        logger.error("Failed to save data to CSV: %s", exc)
        return 0


def scrape_cnn(output_file: str = "cnn_data.csv", headless: bool = False) -> int:
    """
    Execute the complete CNN headline extraction workflow.

    Args:
        output_file: Path for CSV output
        headless: Whether to run browser in background

    Returns:
        Number of headlines extracted and saved
    """
    logger.info("Starting CNN headline extraction process")

    url = "https://www.cnn.com/"
    seen_urls: Set[str] = set()
    rows: List[dict] = []

    driver = get_driver(headless=headless)
    try:
        logger.info("Loading CNN homepage...")
        try:
            driver.get(url)
        except (TimeoutException, WebDriverException) as exc:
            logger.error("Failed to load CNN homepage: %s", exc)
            return 0

        logger.info("Waiting for page elements to load...")
        try:
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a")))
        except TimeoutException:
            logger.error("Timeout waiting for page elements")
            return 0

        # Simulate human behavior: scroll to load dynamic content
        logger.info("Simulating user scrolling to load additional content...")
        for i in range(3):
            try:
                # Check if session is still active
                driver.current_url  # This will raise an exception if session is dead
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                logger.debug(f"Scroll iteration {i+1} completed")
            except Exception as e:
                logger.warning(f"Scroll iteration {i+1} failed or session ended: {e}")
                break

        # Extract all link elements
        elements = driver.find_elements(By.CSS_SELECTOR, "a")
        logger.info("Found %d link elements on page", len(elements))

        # Process each element with error handling
        processed_count = 0
        valid_count = 0

        for element in elements:
            try:
                raw_text = element.text
                raw_link = element.get_attribute("href")
                processed_count += 1
            except (NoSuchElementException, WebDriverException):
                continue

            normalized_text = clean_text(raw_text)
            normalized_link = raw_link.strip() if raw_link else ""

            if is_valid_headline(normalized_text, normalized_link, seen_urls):
                seen_urls.add(normalized_link)
                rows.append({"headline": normalized_text, "url": normalized_link})
                valid_count += 1

        logger.info("Processing complete: %d elements processed, %d valid headlines found", processed_count, valid_count)

    finally:
        driver.quit()
        logger.info("WebDriver session closed")

    if not rows:
        logger.warning("No valid headlines found for extraction")
        print("⚠️ Process completed: 0 headlines saved")
        return 0

    # Save results to CSV
    total_saved = save_to_csv(rows, output_file)
    if total_saved > 0:
        logger.info("Data extraction and saving completed successfully")
        print(f"✅ Process completed: {total_saved} headlines saved to {output_file}")
    else:
        logger.error("Failed to save extracted data")

    return total_saved


def main() -> None:
    """Application entry point for command-line execution."""
    # Create timestamped output directory
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_dir = f"data/extraction_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    try:
        output_file = f"{output_dir}/cnn_data.csv"
        # Default to headless=True for stability (change to False for visual demo)
        total = scrape_cnn(output_file=output_file, headless=True)

        if total > 0:
            # Automatically open the generated CSV file
            try:
                abs_output_file = os.path.abspath(output_file)
                os.startfile(abs_output_file)  # Windows-specific
                logger.info(f"Opened CSV file: {abs_output_file}")
            except AttributeError:
                # For non-Windows systems
                import subprocess
                abs_output_file = os.path.abspath(output_file)
                subprocess.run(["xdg-open", abs_output_file])  # Linux
                logger.info(f"Opened CSV file: {abs_output_file}")
            except Exception as e:
                logger.warning(f"Could not auto-open file: {e}")

    except Exception as exc:
        logger.exception("Unhandled exception during execution: %s", exc)
        print(f"❌ Critical error: {exc}")


if __name__ == "__main__":
    main()
