"""
DOJ Scraper Script for VIDHIVEDA.
Uses Playwright to extract dated legal/judicial content from doj.gov.in,
downloads PDFs, extracts text, and saves to backend/data/doj_dataset.json.
"""
import asyncio
import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
import httpx
import fitz  # PyMuPDF
import pdfplumber
from playwright.async_api import async_playwright

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("errors.log", mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = DATA_DIR / "doj_dataset.json"


def parse_date(text: str) -> str:
    """Extract YYYY-MM-DD from various date patterns in Indian Govt websites."""
    if not text:
        return ""
    text = text.strip()
    
    # 1. DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    m = re.search(r'\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b', text)
    if m:
        try:
            d, month, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return f"{y:04d}-{month:02d}-{d:02d}"
        except ValueError:
            pass
            
    # 2. DD Month YYYY (e.g. 15 June 2023)
    months_pattern = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*'
    m = re.search(rf'\b(\d{{1,2}})\s+({months_pattern})\s+(\d{{4}})\b', text, re.IGNORECASE)
    if m:
        try:
            d_str = m.group(1)
            mon_str = m.group(2)[:3].title()
            y_str = m.group(3)
            dt = datetime.strptime(f"{d_str} {mon_str} {y_str}", "%d %b %Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
            
    # 3. Month DD, YYYY (e.g. June 15, 2023)
    m = re.search(rf'\b({months_pattern})\s+(\d{{1,2}}),\s+(\d{{4}})\b', text, re.IGNORECASE)
    if m:
        try:
            mon_str = m.group(1)[:3].title()
            d_str = m.group(2)
            y_str = m.group(3)
            dt = datetime.strptime(f"{d_str} {mon_str} {y_str}", "%d %b %Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
            
    # 4. Year only fallback
    m = re.search(r'\b(20\d{2}|19\d{2})\b', text)
    if m:
        return f"{m.group(1)}-01-01"
        
    return ""


async def extract_pdf_text(pdf_url: str) -> str:
    """Download PDF and extract text using fitz/pdfplumber."""
    if not pdf_url:
        return ""
    
    logging.info(f"Downloading PDF: {pdf_url}")
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            r = await client.get(pdf_url, headers=headers)
            r.raise_for_status()
            pdf_bytes = r.content
            
        extracted_text = ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
            
        try:
            # PyMuPDF fast extraction
            doc = fitz.open(tmp_path)
            for page in doc:
                extracted_text += page.get_text()
            doc.close()
        except Exception as e:
            logging.warning(f"PyMuPDF failed on {pdf_url}, trying pdfplumber: {e}")
            # Fallback to pdfplumber
            extracted_text = ""
            with pdfplumber.open(tmp_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        extracted_text += text + "\n"
                        
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
            
        return extracted_text.strip()
    except Exception as e:
        logging.error(f"Failed to extract PDF text from {pdf_url}: {e}")
        return ""


async def scrape_circulars(page) -> list:
    """Scrape circulars page from doj.gov.in."""
    url = "https://doj.gov.in/document-category/circulars-notifications/"
    logging.info(f"Scraping circulars: {url}")
    records = []
    
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        # Paginate through 2 pages maximum
        for p in range(1, 3):
            logging.info(f"Circulars Page {p}")
            
            # Find tables
            rows = await page.query_selector_all("table tr")
            if not rows:
                # Try finding in general lists
                rows = await page.query_selector_all(".view-content .views-row")
                
            for row in rows:
                text = await row.inner_text()
                # Find PDF link
                pdf_elem = await row.query_selector("a[href*='.pdf']")
                if not pdf_elem:
                    continue
                
                href = await pdf_elem.get_attribute("href")
                pdf_link = urljoin(url, href)
                
                title = await pdf_elem.inner_text()
                title = title.strip() or "Circular Document"
                
                date_str = parse_date(text)
                if not date_str:
                    date_str = datetime.today().strftime("%Y-%m-%d")
                    
                records.append({
                    "source_type": "circular",
                    "title": title,
                    "date": date_str,
                    "description": text.replace("\n", " ").strip()[:300] + "...",
                    "source_url": url,
                    "pdf_link": pdf_link,
                    "pdf_extracted_text": "" # will populate later
                })
                
            # Click next page
            next_btn = await page.query_selector("li.next a, li.pager-next a, a[title='Go to next page']")
            if next_btn and p < 2:
                await next_btn.click()
                await page.wait_for_timeout(3000)
            else:
                break
    except Exception as e:
        logging.error(f"Error scraping circulars: {e}")
        
    return records


async def scrape_news(page) -> list:
    """Scrape news page from doj.gov.in."""
    url = "https://doj.gov.in/news/"
    logging.info(f"Scraping news: {url}")
    records = []
    
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        rows = await page.query_selector_all(".view-content .views-row, table tr")
        for row in rows:
            text = await row.inner_text()
            title_elem = await row.query_selector("a, h3, h4")
            if not title_elem:
                continue
                
            title = await title_elem.inner_text()
            title = title.strip()
            if len(title) < 5:
                continue
                
            href = await title_elem.get_attribute("href")
            source_link = urljoin(url, href) if href else url
            
            date_str = parse_date(text)
            if not date_str:
                date_str = datetime.today().strftime("%Y-%m-%d")
                
            records.append({
                "source_type": "news",
                "title": title,
                "date": date_str,
                "description": text.replace("\n", " ").strip()[:500] + "...",
                "source_url": source_link,
                "pdf_link": "",
                "pdf_extracted_text": ""
            })
    except Exception as e:
        logging.error(f"Error scraping news: {e}")
        
    return records


async def scrape_notifications(page) -> list:
    """Scrape notification page from doj.gov.in."""
    url = "https://doj.gov.in/news/notification"
    logging.info(f"Scraping notifications: {url}")
    records = []
    
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        rows = await page.query_selector_all("table tr, .views-row")
        for row in rows:
            text = await row.inner_text()
            pdf_elem = await row.query_selector("a[href*='.pdf']")
            if not pdf_elem:
                continue
                
            href = await pdf_elem.get_attribute("href")
            pdf_link = urljoin(url, href)
            
            title = await pdf_elem.inner_text()
            title = title.strip() or "Notification Document"
            
            date_str = parse_date(text)
            if not date_str:
                date_str = datetime.today().strftime("%Y-%m-%d")
                
            records.append({
                "source_type": "notification",
                "title": title,
                "date": date_str,
                "description": text.replace("\n", " ").strip()[:300] + "...",
                "source_url": url,
                "pdf_link": pdf_link,
                "pdf_extracted_text": ""
            })
    except Exception as e:
        logging.error(f"Error scraping notifications: {e}")
        
    return records


async def scrape_schemes(page) -> list:
    """Scrape schemes and policies from doj.gov.in/about-department."""
    url = "https://www.doj.gov.in/about-department"
    logging.info(f"Scraping schemes/about department: {url}")
    records = []
    
    # Official launch dates of schemes for fallback/enrichment
    OFFICIAL_SCHEMES = [
        {
            "title": "e-Courts Mission Mode Project",
            "date": "2007-01-01",
            "keywords": ["e-courts", "ecourts", "mission mode project"],
            "description": "A national mission mode project monitored by the e-Committee of Supreme Court of India and DOJ to digitize Indian courts."
        },
        {
            "title": "Fast Track Special Courts (FTSCs)",
            "date": "2019-10-02",
            "keywords": ["fast track special court", "ftsc", "fast track court"],
            "description": "Centrally Sponsored Scheme launched for swift trial of cases related to sexual offences and POCSO Act."
        },
        {
            "title": "National Judicial Data Grid (NJDG)",
            "date": "2015-09-19",
            "keywords": ["national judicial data grid", "njdg"],
            "description": "A database of pending and disposed cases across commercial, civil, and criminal courts in India."
        },
        {
            "title": "Tele-Law Scheme",
            "date": "2017-06-01",
            "keywords": ["tele-law", "tele law", "legal advice"],
            "description": "DOJ initiative to connect common citizens with lawyers through video conferencing/telephony at Common Service Centres (CSCs)."
        }
    ]
    
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        body_text = await page.locator("body").inner_text()
        
        for scheme in OFFICIAL_SCHEMES:
            found = False
            for kw in scheme["keywords"]:
                if kw in body_text.lower():
                    found = True
                    break
                    
            if found:
                logging.info(f"Found policy/scheme on page: {scheme['title']}")
                records.append({
                    "source_type": "scheme",
                    "title": scheme["title"],
                    "date": scheme["date"],
                    "description": scheme["description"],
                    "source_url": url,
                    "pdf_link": "",
                    "pdf_extracted_text": ""
                })
    except Exception as e:
        logging.error(f"Error scraping schemes: {e}")
        
    return records


async def scrape_reports(page) -> list:
    """Find and scrape Reports/Publications section from doj.gov.in."""
    records = []
    
    # Try different potential report urls
    urls = [
        "https://doj.gov.in/reports-publications/",
        "https://doj.gov.in/annual-reports/",
        "https://doj.gov.in/annual-reports"
    ]
    
    for url in urls:
        logging.info(f"Checking reports URL: {url}")
        try:
            response = await page.goto(url, wait_until="domcontentloaded")
            if not response or response.status != 200:
                continue
                
            await page.wait_for_timeout(3000)
            
            rows = await page.query_selector_all("table tr, .views-row")
            for row in rows:
                text = await row.inner_text()
                pdf_elem = await row.query_selector("a[href*='.pdf']")
                if not pdf_elem:
                    continue
                    
                href = await pdf_elem.get_attribute("href")
                pdf_link = urljoin(url, href)
                
                title = await pdf_elem.inner_text()
                title = title.strip() or "Annual Report"
                
                date_str = parse_date(text)
                if not date_str:
                    date_str = parse_date(title)
                if not date_str:
                    date_str = datetime.today().strftime("%Y-%m-%d")
                    
                records.append({
                    "source_type": "notification",  # reports map as notifications/circulars in RAG
                    "title": title,
                    "date": date_str,
                    "description": f"Annual Report/Publication: {title}",
                    "source_url": url,
                    "pdf_link": pdf_link,
                    "pdf_extracted_text": ""
                })
            
            if records:
                # Successfully scraped, no need to try other urls
                break
        except Exception as e:
            logging.error(f"Error checking report URL {url}: {e}")
            
    return records


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        all_records = []
        
        # 1. Circulars
        circulars = await scrape_circulars(page)
        all_records.extend(circulars)
        await asyncio.sleep(2)
        
        # 2. News
        news = await scrape_news(page)
        all_records.extend(news)
        await asyncio.sleep(2)
        
        # 3. Notifications
        notifications = await scrape_notifications(page)
        all_records.extend(notifications)
        await asyncio.sleep(2)
        
        # 4. Schemes/About
        schemes = await scrape_schemes(page)
        all_records.extend(schemes)
        await asyncio.sleep(2)
        
        # 5. Reports
        reports = await scrape_reports(page)
        all_records.extend(reports)
        
        await browser.close()
        
        logging.info(f"Total crawled items before PDF extraction: {len(all_records)}")
        
        # Extract PDF text for circulars/reports/notifications
        pdf_extracted_count = 0
        for record in all_records:
            if record["pdf_link"]:
                extracted = await extract_pdf_text(record["pdf_link"])
                if extracted:
                    record["pdf_extracted_text"] = extracted
                    pdf_extracted_count += 1
                await asyncio.sleep(1) # respect server load
                
        logging.info(f"PDF text successfully extracted for {pdf_extracted_count} documents.")
        
        # Save output
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(all_records, f, indent=2, ensure_ascii=False)
            
        logging.info(f"Scraped dataset saved successfully to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
