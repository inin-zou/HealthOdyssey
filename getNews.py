import requests
from bs4 import BeautifulSoup
import csv
import time
from datetime import datetime

BASE_URL = "https://rappel.conso.gouv.fr"
CATEGORY_ID = 94       # "Meats"
START_PAGE = 1
END_PAGE = 209         # Currently, this category shows up to page 209
OUTPUT_CSV = "rappel_conso_viandes.csv"

def get_zone_geographique(url):
    """
    Request the detail page and extract the content for "Zone géographique de vente" (sales region).
    It looks through each <li class="product-desc-item"> tag on the page and, if the text of the
    <span class="carac"> tag contains "Zone géographique de vente", it extracts the corresponding text
    from the <span class="val"> tag.
    """
    try:
        resp = requests.get(url)
        if resp.status_code != 200:
            print(f"Error fetching details for URL: {url} (status code: {resp.status_code})")
            return ""
        detail_soup = BeautifulSoup(resp.text, "html.parser")
        for li in detail_soup.find_all("li", class_="product-desc-item"):
            carac = li.find("span", class_="carac")
            if carac and "Zone géographique de vente" in carac.get_text(strip=True):
                val = li.find("span", class_="val")
                if val:
                    return val.get_text(strip=True)
        return ""
    except Exception as e:
        print(f"Error scraping zone for {url}: {e}")
        return ""

def scrape_viandes(category_id, start_page=1, end_page=209):
    all_items = []
    # Define the date filter range
    start_date_filter = datetime(2021, 1, 1)
    end_date_filter = datetime(2023, 12, 31, 23, 59, 59)
    
    for page in range(start_page, end_page + 1):
        url = f"{BASE_URL}/categorie/{category_id}/{page}"
        print(f"Scraping page {page} (URL: {url}) ...")
        
        resp = requests.get(url)
        if resp.status_code != 200:
            print(f"[Error] Page {page} returned status code {resp.status_code}. Stopping scrape.")
            break
        
        soup = BeautifulSoup(resp.text, "html.parser")
        products = soup.find_all("li", class_="product-item")
        if not products:
            print(f"No recall information found on page {page}. Stopping scrape.")
            break
        
        page_count = 0
        for li in products:
            # Extract title
            title_tag = li.find("a", class_="product-link")
            title = title_tag.get_text(strip=True) if title_tag else ""

            # Detail link
            link = title_tag["href"] if (title_tag and title_tag.has_attr("href")) else ""
            full_link = BASE_URL + link if link.startswith("/") else link

            # Manufacturer / Brand
            maker_tag = li.find("p", class_="my-0 product-maker")
            maker = maker_tag.get_text(strip=True) if maker_tag else ""

            # Parse “Risks” and “Reason”
            desc_divs = li.find("div", class_="product-desc")
            risks, reason = "", ""
            if desc_divs:
                desc_items = desc_divs.find_all("div", class_="product-desc-item")
                if len(desc_items) >= 1:
                    risks = desc_items[0].get_text(strip=True).replace("Risques : ", "")
                if len(desc_items) >= 2:
                    reason = desc_items[1].get_text(strip=True).replace("Motif : ", "")

            # Parse the publication date
            date_tag = li.find("p", class_="text-muted product-date")
            date_text = ""
            if date_tag:
                time_tag = date_tag.find("time")
                if time_tag and time_tag.has_attr("datetime"):
                    date_text = time_tag["datetime"]  # Format example: "14/02/2025 15:43:31"

            # Convert the date string to a datetime object
            record_date = None
            if date_text:
                try:
                    record_date = datetime.strptime(date_text, "%d/%m/%Y %H:%M:%S")
                except Exception as e:
                    print(f"Failed to parse date: {date_text}, error: {e}")
            
            # If the date is missing or not within the specified range, skip this record
            if record_date is None or not (start_date_filter <= record_date <= end_date_filter):
                continue

            # Scrape the sales region from the detail page
            zone = get_zone_geographique(full_link)
            # To avoid sending requests too quickly, pause briefly after each detail page request
            time.sleep(0.5)

            all_items.append({
                "title": title,
                "maker": maker,
                "risks": risks,
                "reason": reason,
                "date": date_text,
                "zone": zone,
                "link": full_link
            })
            page_count += 1
        
        print(f"  Found {page_count} records on page {page} that meet the date range criteria.")
        time.sleep(1)
    
    print(f"Total records found that meet the date range: {len(all_items)}")
    return all_items

def save_to_csv(items, csv_file):
    """
    Save the scraped data into a CSV file.
    """
    with open(csv_file, mode="w", encoding="utf-8", newline="") as f:
        fieldnames = ["title", "maker", "risks", "reason", "date", "zone", "link"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in items:
            writer.writerow(row)
    print(f"Data saved to {csv_file}")

def main():
    results = scrape_viandes(CATEGORY_ID, START_PAGE, END_PAGE)
    if results:
        save_to_csv(results, OUTPUT_CSV)

if __name__ == "__main__":
    main()