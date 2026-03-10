import pandas as pd
import time
import re
import os
import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build

# 셀레니움 관련 라이브러리
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

def get_selenium_driver():
    """투명 망토를 벗고, 사람처럼 보이는 가상 브라우저를 띄웁니다."""
    chrome_options = Options()
    # 💡 아래 줄을 주석 처리(#)해서 모니터에 브라우저가 직접 뜨게 만듭니다!
    # chrome_options.add_argument("--headless") 
    
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # 💡 봇 탐지(로봇이 아닙니다) 회피용 핵심 코드
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")
    
    # 내 컴퓨터(로컬) 환경일 경우 알아서 다운로드하여 사용
    from webdriver_manager.chrome import ChromeDriverManager
    service = Service(ChromeDriverManager().install())
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # 브라우저에게 "나 봇 아니야"라고 한 번 더 최면 걸기
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def is_korean(text):
    if not text: return False
    return bool(re.search(r'[가-힣]', text))

def run_insta_scraper_real(keyword, max_scrolls, progress_bar):
    driver = None
    try:
        progress_bar.progress(10, text="가상 브라우저(Selenium) 구동 중...")
        driver = get_selenium_driver()
        
        url = f"https://www.picuki.com/search/{keyword}"
        driver.get(url)
        time.sleep(3)
        
        results = []
        progress_bar.progress(30, text=f"'{keyword}' 계정 탐색 및 스크롤 중...")
        
        for _ in range(max_scrolls):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
        profiles = driver.find_elements(By.CSS_SELECTOR, ".profile-result")
        total_found = len(profiles)
        
        for i, profile in enumerate(profiles):
            try:
                progress_bar.progress(30 + int(60 * (i / total_found)), text=f"데이터 추출 중... ({i+1}/{total_found})")
                username = profile.find_element(By.CSS_SELECTOR, ".profile-name").text.strip()
                fullname = profile.find_element(By.CSS_SELECTOR, ".profile-fullname").text.strip()
                
                profile_link = f"https://www.instagram.com/{username.replace('@', '')}"
                
                results.append({
                    "플랫폼": "인스타",
                    "닉네임": username.replace('@', ''),
                    "본명/설명": fullname,
                    "프로필링크": profile_link,
                    "팔로워수": "수기확인", 
                    "이메일": ""
                })
            except: continue
            
        progress_bar.progress(100, text="크롤링 완료!")
        time.sleep(1)
        progress_bar.empty()
        
        df = pd.DataFrame(results).drop_duplicates(subset=['닉네임'])
        return df, []
    except Exception as e:
        return pd.DataFrame({"에러": [str(e)]}), []
    finally:
        if driver: driver.quit()

def run_tiktok_scraper_real(keyword, progress_bar):
    driver = None
    try:
        progress_bar.progress(20, text="틱톡 가상 브라우저 접속 중...")
        driver = get_selenium_driver()
        driver.get(f"https://www.tiktok.com/search/user?q={keyword}")
        time.sleep(5) 
        
        progress_bar.progress(60, text="데이터 추출 중...")
        results = []
        users = driver.find_elements(By.CSS_SELECTOR, "[data-e2e='search-user-info-container']")
        for user in users[:20]: 
            try:
                nickname = user.find_element(By.CSS_SELECTOR, "[data-e2e='search-user-unique-id']").text
                link = f"https://www.tiktok.com/@{nickname}"
                results.append({
                    "플랫폼": "틱톡", "닉네임": nickname, "프로필링크": link, "팔로워수": "수기확인", "이메일": ""
                })
            except: continue
            
        progress_bar.empty()
        return pd.DataFrame(results) if results else pd.DataFrame({"안내": ["틱톡 봇 차단으로 결과를 가져오지 못했습니다."]})
    except Exception as e:
        return pd.DataFrame({"에러": [str(e)]})
    finally:
        if driver: driver.quit()

def run_blog_search_real(keyword):
    url = f"https://search.naver.com/search.naver?where=view&sm=tab_jum&query={keyword}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        posts = soup.select('.title_link, .api_txt_lines.total_tit')[:15]
        for post in posts:
            title = post.text
            link = post.get('href', '')
            if "blog.naver.com" in link:
                blog_id = link.split("/")[-2] if "/" in link else "블로거"
                results.append({
                    "플랫폼": "블로그", "닉네임": blog_id, "게시물제목": title, "프로필링크": link, "이메일": ""
                })
        return pd.DataFrame(results) if results else pd.DataFrame({"안내": ["검색 결과가 없습니다."]})
    except Exception as e:
        return pd.DataFrame({"에러": [str(e)]})

def run_metrics_scraper_real(url):
    driver = None
    try:
        driver = get_selenium_driver()
        driver.get(url)
        time.sleep(4) 
        
        metrics = {"게재일": "수기", "조회수": 0, "좋아요": 0, "댓글": 0, "저장": 0, "공유": 0, "리포스트": 0}
        
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        if "instagram.com" in url:
            meta = soup.find("meta", property="og:description")
            if meta:
                desc = meta["content"]
                likes = re.search(r'([\d,]+)\s*Likes', desc)
                comments = re.search(r'([\d,]+)\s*Comments', desc)
                if likes: metrics["좋아요"] = int(likes.group(1).replace(",", ""))
                if comments: metrics["댓글"] = int(comments.group(1).replace(",", ""))
                
        elif "youtube.com" in url or "youtu.be" in url:
            views = soup.find("meta", itemprop="interactionCount")
            if views: metrics["조회수"] = int(views["content"])
            
        return metrics
    except:
        return None
    finally:
        if driver: driver.quit()

def run_youtube_search_real(keyword, api_key, min_views=10000):
    try:
        youtube = build('youtube', 'v3', developerKey=api_key)
        search_response = youtube.search().list(q=keyword, part='id,snippet', maxResults=10, type='video').execute()
        results = []
        for search_result in search_response.get('items', []):
            video_id = search_result['id']['videoId']
            title = search_result['snippet']['title']
            channel_id = search_result['snippet']['channelId']
            channel_title = search_result['snippet']['channelTitle']
            video_response = youtube.videos().list(id=video_id, part='statistics').execute()
            views = int(video_response['items'][0]['statistics'].get('viewCount', 0))
            if views >= min_views:
                results.append({"플랫폼": "유튜브", "닉네임": channel_title, "영상제목": title, "프로필링크": f"https://www.youtube.com/channel/{channel_id}", "조회수": views, "이메일": ""})
        return pd.DataFrame(results) if results else pd.DataFrame({"안내": ["조건에 맞는 결과가 없습니다."]})
    except Exception as e:
        return pd.DataFrame({"에러": [f"유튜브 API 호출 실패: {e}"]})
