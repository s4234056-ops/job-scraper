import os
import json
import requests
import time
from datetime import datetime
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# 設定
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
JOBS_FILE = "jobs.json"
KEYWORDS = ["28卒", "インターン", "金融", "Fintech", "クオンツ", "資産運用", "Asset Management", "Global", "Remote"]
TARGET_URLS = [
    # Wantedly: 金融/Fintech系インターン
    "https://www.wantedly.com/projects?q=Fintech%20%E3%82%A4%E3%83%B3%E3%82%BF%E3%83%BC%E3%83%B3",
    "https://www.wantedly.com/projects?q=%E9%87%91%E8%9E%8D%20%E3%82%A4%E3%83%B3%E3%82%BF%E3%83%BC%E3%83%B3",
    "https://www.wantedly.com/projects?q=28%E5%8D%92",
    # Green: 金融系求人
    "https://www.green-japan.com/search_key/01?key=%E9%87%91%E8%9E%8D",
]

def load_seen_jobs():
    if os.path.exists(JOBS_FILE):
        with open(JOBS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_seen_jobs(jobs):
    with open(JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)

def send_slack_notification(job):
    if not SLACK_WEBHOOK_URL:
        print("Slack Webhook URL is not set.")
        return

    payload = {
        "text": f"🚀 *新着求人通知 (28卒/金融系)*\n\n*タイトル:* {job['title']}\n*会社名:* {job['company']}\n*URL:* {job['url']}\n\n💡 _ロンドン大学の知見を活かせるチャンスかもしれません！_"
    }
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"Error sending to Slack: {e}")

def scrape_wantedly(page, seen_jobs):
    new_jobs = []
    # Wantedlyは動的なので少し待つ
    time.sleep(2)
    
    # 求人カードの取得
    cards = page.query_selector_all("article.project-card") or page.query_selector_all("div.project-index-single")
    
    for card in cards:
        try:
            title_elem = card.query_selector(".project-title a")
            company_elem = card.query_selector(".company-name a")
            
            if title_elem and company_elem:
                title = title_elem.inner_text().strip()
                company = company_elem.inner_text().strip()
                url = "https://www.wantedly.com" + title_elem.get_attribute("href").split("?")[0]
                job_id = url
                
                if job_id not in seen_jobs:
                    job_data = {"title": title, "company": company, "url": url}
                    new_jobs.append(job_data)
                    seen_jobs[job_id] = datetime.now().isoformat()
        except Exception as e:
            print(f"Error parsing Wantedly card: {e}")
            continue
            
    return new_jobs

def scrape_green(page, seen_jobs):
    new_jobs = []
    time.sleep(2)
    
    # Greenの求人カード (2024-2025年最新セレクタ想定)
    cards = page.query_selector_all('div[class*="JobCard_container"]') or page.query_selector_all("div.job-card")
    
    for card in cards:
        try:
            title_elem = card.query_selector('a[class*="JobCard_title"]') or card.query_selector("h2 a")
            company_elem = card.query_selector('h3') or card.query_selector(".company-name")
            
            if title_elem and company_elem:
                title = title_elem.inner_text().strip()
                company = company_elem.inner_text().strip()
                url = "https://www.green-japan.com" + title_elem.get_attribute("href").split("?")[0]
                job_id = url
                
                if job_id not in seen_jobs:
                    job_data = {"title": title, "company": company, "url": url}
                    new_jobs.append(job_data)
                    seen_jobs[job_id] = datetime.now().isoformat()
        except Exception as e:
            print(f"Error parsing Green card: {e}")
            continue
            
    return new_jobs

def main():
    seen_jobs = load_seen_jobs()
    total_new_jobs = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
        page = context.new_page()
        
        for url in TARGET_URLS:
            print(f"Scraping: {url}")
            try:
                page.goto(url, wait_until="networkidle")
                if "wantedly.com" in url:
                    total_new_jobs.extend(scrape_wantedly(page, seen_jobs))
                elif "green-japan.com" in url:
                    total_new_jobs.extend(scrape_green(page, seen_jobs))
            except Exception as e:
                print(f"Failed to scrape {url}: {e}")
        
        browser.close()
    
    # 新着のみ通知
    for job in total_new_jobs:
        print(f"Found new job: {job['title']} at {job['company']}")
        send_slack_notification(job)
    
    save_seen_jobs(seen_jobs)
    print(f"Finished. Total new jobs found: {len(total_new_jobs)}")

if __name__ == "__main__":
    main()
