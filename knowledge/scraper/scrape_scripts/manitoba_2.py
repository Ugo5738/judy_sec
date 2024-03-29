import asyncio
import os
import tempfile

from bs4 import BeautifulSoup
from celery import shared_task
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from playwright.async_api import async_playwright

from chatbackend.configs.logging_config import configure_logger
from knowledge.scraper.scraper_utils import download_pdf, sanitize_filename

logger = configure_logger(__name__)

# Base URL
base_url = "https://www.clpnm.ca/"

async def extract_nav_links(page):
    return await page.evaluate('''() => {
        const links = [];
        document.querySelectorAll('#mega-menu-menu-1 .mega-menu-item a').forEach(a => {
            if (a.offsetParent !== null) {
                links.push({text: a.innerText.trim(), href: a.href});
            }
        });
        return links;
    }''')

async def extract_page_links(page):
    return await page.evaluate('''() => {
        const links = [];
        document.querySelectorAll('a').forEach(a => {
            if (a.href && !a.href.startsWith('javascript') && a.offsetParent !== null) {
                links.push(a.href);
            }
        });
        return links.filter(href => href.startsWith(document.location.origin));
    }''')

async def scrape_html_content(page, url):
    try:
        await page.goto(url, timeout=60000)
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        main_content = soup.find_all(class_='elementor-widget-container')
        content_text = ""

        if main_content:
            for element in main_content:
                for subelement in element.find_all(['h1', 'h2', 'h3', 'p', 'ul', 'a']):
                    if subelement.name == 'a' and 'href' in subelement.attrs:
                        if subelement['href'].endswith('.pdf'):
                            pdf_url = subelement['href']
                            pdf_name = sanitize_filename(subelement.get_text(strip=True)) + '.pdf'
                            pdf_path = f"manitoba_2/pdfs/{pdf_name}"
                            await download_pdf(pdf_url, pdf_path)
                        else:
                            content_text += f"{subelement.get_text(strip=True)}\n\n"
                    else:
                        content_text += f"{subelement.get_text(strip=True)}\n\n"
        else:
            content_text += "Main content not found.\n"

        return content_text
    except Exception as e:
        logger.error(f"Error scraping content from {url}: {str(e)}")
        return None

async def process_page(page, url, temp_file, processed_urls):
    if url in processed_urls or not url.startswith(base_url):
        return
    processed_urls.add(url)

    logger.info(f"Processing page: {url}")
    content = await scrape_html_content(page, url)
    if content:
        temp_file.write(f"URL: {url}\n{content}")
        temp_file.write("------------------------------------------------------------\n\n")
        
    page_links = await extract_page_links(page)
    for link in page_links:
        await process_page(page, link, temp_file, processed_urls)

async def scrape_clpnm_site():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        await page.goto(base_url, timeout=60000)

        processed_urls = set()
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8') as temp_file:
            nav_links = await extract_nav_links(page)
            for nav_link in nav_links:
                await process_page(page, nav_link['href'], temp_file, processed_urls)

            temp_file_path = temp_file.name

        await browser.close()
        logger.info("Scraping completed.")

        # Upload the temporary file to S3
        with open(temp_file_path, 'rb') as temp_file_to_upload:
            s3_file_name = "scraped_data/manitoba_2/scraped_content/scraped_clpnm_content.txt"
            default_storage.save(s3_file_name, ContentFile(temp_file_to_upload.read()))
            logger.info(f"Scraped content saved to S3 as {s3_file_name}")

        # Clean up the temporary file
        try:
            os.remove(temp_file_path)
            logger.info(f"Temporary file {temp_file_path} deleted successfully.")
        except Exception as e:
            logger.error(f"Error deleting temporary file {temp_file_path}: {e}")

# Run the scraping process
@shared_task
def scrape_clpnm_site_task():
    asyncio.run(scrape_clpnm_site())


# @shared_task
# def scrape_clpnm_site():
#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(scrape_clpnm_site())