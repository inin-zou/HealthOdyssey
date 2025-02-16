import requests
from bs4 import BeautifulSoup
import csv
import time
from datetime import datetime

BASE_URL = "https://rappel.conso.gouv.fr"
CATEGORY_ID = 94       # "Viandes"
START_PAGE = 1
END_PAGE = 209         # 该类别目前显示最多到第 209 页
OUTPUT_CSV = "rappel_conso_viandes.csv"

def get_zone_geographique(url):
    """
    请求详情页并提取“Zone géographique de vente”的内容，
    根据页面中 <li class="product-desc-item"> 标签中，
    当 <span class="carac"> 的文本包含 "Zone géographique de vente" 时，
    提取对应 <span class="val"> 中的文本。
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
    # 定义日期过滤区间
    start_date_filter = datetime(2021, 1, 1)
    end_date_filter = datetime(2023, 12, 31, 23, 59, 59)
    
    for page in range(start_page, end_page + 1):
        url = f"{BASE_URL}/categorie/{category_id}/{page}"
        print(f"正在抓取第 {page} 页 (URL: {url}) ...")
        
        resp = requests.get(url)
        if resp.status_code != 200:
            print(f"[Error] 第 {page} 页返回状态码 {resp.status_code}，停止抓取。")
            break
        
        soup = BeautifulSoup(resp.text, "html.parser")
        products = soup.find_all("li", class_="product-item")
        if not products:
            print(f"第 {page} 页未找到任何召回信息，停止抓取。")
            break
        
        page_count = 0
        for li in products:
            # 提取标题
            title_tag = li.find("a", class_="product-link")
            title = title_tag.get_text(strip=True) if title_tag else ""

            # 详情链接
            link = title_tag["href"] if (title_tag and title_tag.has_attr("href")) else ""
            full_link = BASE_URL + link if link.startswith("/") else link

            # 制造商 / 品牌
            maker_tag = li.find("p", class_="my-0 product-maker")
            maker = maker_tag.get_text(strip=True) if maker_tag else ""

            # 解析 “Risques” 与 “Motif”
            desc_divs = li.find("div", class_="product-desc")
            risks, reason = "", ""
            if desc_divs:
                desc_items = desc_divs.find_all("div", class_="product-desc-item")
                if len(desc_items) >= 1:
                    risks = desc_items[0].get_text(strip=True).replace("Risques : ", "")
                if len(desc_items) >= 2:
                    reason = desc_items[1].get_text(strip=True).replace("Motif : ", "")

            # 解析发布日期
            date_tag = li.find("p", class_="text-muted product-date")
            date_text = ""
            if date_tag:
                time_tag = date_tag.find("time")
                if time_tag and time_tag.has_attr("datetime"):
                    date_text = time_tag["datetime"]  # 格式示例："14/02/2025 15:43:31"

            # 解析日期字符串
            record_date = None
            if date_text:
                try:
                    record_date = datetime.strptime(date_text, "%d/%m/%Y %H:%M:%S")
                except Exception as e:
                    print(f"无法解析日期: {date_text}，错误: {e}")
            
            # 如果日期不存在或不在要求区间，则跳过该记录
            if record_date is None or not (start_date_filter <= record_date <= end_date_filter):
                continue

            # 抓取详情页中的销售区域信息
            zone = get_zone_geographique(full_link)
            # 为防止请求过快，每个详情页请求后稍作休眠
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
        
        print(f"  第 {page} 页共抓取到 {page_count} 条符合日期范围的记录。")
        time.sleep(1)
    
    print(f"共抓取到 {len(all_items)} 条召回信息（符合日期范围）。")
    return all_items

def save_to_csv(items, csv_file):
    """
    将抓取到的数据写入 CSV 文件。
    """
    with open(csv_file, mode="w", encoding="utf-8", newline="") as f:
        fieldnames = ["title", "maker", "risks", "reason", "date", "zone", "link"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in items:
            writer.writerow(row)
    print(f"已将数据保存到 {csv_file}")

def main():
    results = scrape_viandes(CATEGORY_ID, START_PAGE, END_PAGE)
    if results:
        save_to_csv(results, OUTPUT_CSV)

if __name__ == "__main__":
    main()
