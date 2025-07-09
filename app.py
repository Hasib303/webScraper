from fastapi import FastAPI, HTTPException
import os
import requests
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
import time
import json

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Retrieve the SERPER_API_KEY from environment variables
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

def get_news_link(q: str):
    """
    Get the URL of the first news article from the Serper API.
    """
    if not SERPER_API_KEY:
        raise ValueError("SERPER_API_KEY environment variable not set.")

    url = "https://google.serper.dev/news"
    payload = {
        "q": q,
        "location": "United States",
        "num": 1,
        "page": 1
    }
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()  # Raise an exception for bad status codes

    data = response.json()

    if 'news' in data and len(data['news']) > 0:
        return data['news'][0]['link']
    else:
        return None

# Setup Selenium WebDriver (make sure ChromeDriver is installed)
def setup_selenium():
    options = Options()
    options.headless = True  # Run headless browser for scraping
    driver = webdriver.Chrome(options=options)
    return driver

# Define the scraping function using Selenium
def scrape_with_selenium(url):
    driver = setup_selenium()
    driver.get(url)
    
    # Wait for the page to load completely (adjust time if needed)
    time.sleep(3)  # or use WebDriverWait for more dynamic behavior
    
    # Extract the page title
    title = driver.title

    # Extract the main heading (usually the first h1)
    try:
        heading = driver.find_element(By.TAG_NAME, 'h1').text
    except NoSuchElementException:
        heading = "No heading found"

    # Extract the first image URL
    try:
        image_url = driver.find_element(By.TAG_NAME, 'img').get_attribute('src')
    except NoSuchElementException:
        image_url = "No image found"

    # Extract the article text from all paragraph tags
    paragraphs = driver.find_elements(By.TAG_NAME, 'p')
    article_text = "\n".join([p.text for p in paragraphs])

    # Extract tables
    tables_data = []
    tables = driver.find_elements(By.TAG_NAME, 'table')
    for table in tables:
        table_rows = table.find_elements(By.TAG_NAME, 'tr')
        current_table = []
        for row in table_rows:
            row_data = [cell.text for cell in row.find_elements(By.TAG_NAME, 'td')]
            if not row_data:
                row_data = [cell.text for cell in row.find_elements(By.TAG_NAME, 'th')]
            current_table.append(row_data)
        tables_data.append(current_table)

    driver.quit()
    
    return {
        "url": url,
        "title": title,
        "heading": heading,
        "image_url": image_url,
        "article_text": article_text,
        "tables": tables_data
    }

@app.get("/news_scrape")

def news_scrape_endpoint(q: str):
    """
    Get news articles from SerpApi and scrape the first article link using Selenium.
    """
    if not SERPER_API_KEY:
        return {"error": "SERPER_API_KEY environment variable not set."}

    try:
        article_link = get_news_link(q)
        if article_link:
            # Use Selenium to scrape the article
            scraped_data = scrape_with_selenium(article_link)
            # Return the scraped data
            return scraped_data
        else:
            raise HTTPException(status_code=404, detail="No news found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
