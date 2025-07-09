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

load_dotenv()

def get_news_link(q: str):
    """
    Get the URL of the first news article from the Serper API.
    """
    SERPER_API_KEY = os.getenv("SERPER_API_KEY")
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

from selenium.common.exceptions import NoSuchElementException
from transformers import pipeline

# Initialize the summarization pipeline
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

def _format_table_as_markdown(table_data):
    if not table_data:
        return ""

    markdown_table = []
    # Add header row
    header = table_data[0]
    markdown_table.append(" | ".join(header))
    # Add separator row
    markdown_table.append(" | ".join([str("-" * len(col)) for col in header]))
    # Add data rows
    for row in table_data[1:]:
        markdown_table.append(" | ".join(row))
    return "\n".join(markdown_table)

# Define the scraping function using Selenium
def scrape_with_selenium(url):
    driver = setup_selenium()
    driver.get(url)
    
    # Wait for the page to load completely (adjust time if needed)
    time.sleep(3)  # or use WebDriverWait for more dynamic behavior
    
    # A rough estimate: 1 token ~ 4 characters
    max_chars = 4000 # 1024 tokens * 4 chars/token

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

    # Extract the article text from all paragraph tags, excluding footer content
    all_paragraphs = driver.find_elements(By.TAG_NAME, 'p')
    article_paragraphs = []
    for p in all_paragraphs:
        # Execute JavaScript to check if the paragraph is inside a footer
        is_in_footer = driver.execute_script("""
            let element = arguments[0];
            while (element) {
                if (element.tagName.toLowerCase() === 'footer') {
                    return true;
                }
                element = element.parentElement;
            }
            return false;
        """, p)
        if not is_in_footer:
            article_paragraphs.append(p.text)
    article_text = "\n".join(article_paragraphs)

    # Extract tables and format as Markdown
    tables_data = []
    tables = driver.find_elements(By.TAG_NAME, 'table')
    for i, table in enumerate(tables):
        table_rows = table.find_elements(By.TAG_NAME, 'tr')
        current_table_data = []
        for row in table_rows:
            row_data = [cell.text for cell in row.find_elements(By.TAG_NAME, 'td')]
            if not row_data:
                row_data = [cell.text for cell in row.find_elements(By.TAG_NAME, 'th')]
            current_table_data.append(row_data)
        
        markdown_table = _format_table_as_markdown(current_table_data)
        tables_data.append({"data": current_table_data, "markdown_table": markdown_table})

    # Generate abstract summarization for the article
    text_to_summarize = f"{title}. {heading}. {article_text}"
    # Truncate text if it's too long for the model (max 1024 tokens * 4 chars/token)
    if len(text_to_summarize) > max_chars:
        text_to_summarize = text_to_summarize[:max_chars]

    article_summary = summarizer(text_to_summarize, max_length=1500, min_length=500, do_sample=False)[0]['summary_text']

    # Collect all summaries and markdown tables
    combined_summary_parts = [article_summary]
    for i, table_info in enumerate(tables_data):
        combined_summary_parts.append(f"\n\nTable {i+1}:\n{table_info['markdown_table']}")

    summary = " ".join(combined_summary_parts)

    driver.quit()
    
    return {
        "url": url,
        "title": title,
        "heading": heading,
        "image_url": image_url,
        "article_text": article_text,
        "tables": tables_data,
        "summary": summary
    }

import json

if __name__ == '__main__':
    # Example usage:
    news_url = get_news_link("latest technology trends")
    if news_url:
        print(f"Found news article: {news_url}")
        scraped_data = scrape_with_selenium(news_url)
        output_filename = "scraped_output.json"
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(scraped_data, f, ensure_ascii=False, indent=4)
        print(f"Scraped data has been saved to {output_filename}")
    else:
        print("No news articles found.")