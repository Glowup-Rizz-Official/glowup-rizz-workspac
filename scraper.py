import pandas as pd
import time
import random
import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build

def run_youtube_search_real(keyword, api_key, min_views=10000):
    """실제 YouTube Data API v3를 활용한 검색"""
    try:
        youtube = build('youtube', 'v3', developerKey=api_key)
        
        search_response = youtube.search().list(
            q=keyword, part='id,snippet', maxResults=10, type='video'
        ).execute()
        
        results = []
        for search_result in search_response.get('items', []):
            video_id = search_result['id']['videoId']
            title = search_result['snippet']['title']
            channel_id = search_result['snippet']['channelId']
            channel_title = search_result['snippet']['channelTitle']
            
            video_response = youtube.videos().list(
                id=video_id, part='statistics'
            ).execute()
            
            views = int(video_response['items'][0]['statistics'].get('viewCount', 0))
            
            if views >= min_views:
                results.append({
                    "플랫폼": "유튜브",
                    "닉네임": channel_title,
                    "영상제목": title,
                    "프로필링크": f"https://www.youtube.com/channel/{channel_id}",
                    "조회수": views,
                    "이메일": "" 
                })
                
        return pd.DataFrame(results) if results else pd.DataFrame({"안내": ["조건에 맞는 결과가 없습니다."]})
    except Exception as e:
        return pd.DataFrame({"에러": [f"유튜브 API 호출 실패: {e}"]})

def run_blog_search_real(keyword):
    """실제 네이버 블로그 검색 크롤링"""
    url = f"https://search.naver.com/search.naver?where=view&sm=tab_jum&query={keyword}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        posts = soup.select('.api_txt_lines.total_tit')[:10]
        for post in posts:
            title = post.text
            link = post['href']
            results.append({
                "플랫폼": "블로그",
                "제목": title,
                "프로필링크": link,
                "닉네임": "블로거", 
                "이메일": ""
            })
        return pd.DataFrame(results)
    except Exception as e:
        return pd.DataFrame({"에러": [f"블로그 크롤링 실패: {e}"]})

def run_insta_scraper_dummy(keyword, progress_bar):
    """인스타그램 크롤링 (Dummy)"""
    for i in range(100):
        time.sleep(0.01)
        progress_bar.progress(i + 1, text=f"인스타 데이터 수집 중... {i+1}%")
    time.sleep(0.5)
    progress_bar.empty()
    
    return pd.DataFrame({
        "닉네임": ["테스트계정_배포시_셀레니움필요"], 
        "프로필링크": ["https://instagram.com/test"], 
        "팔로워수": [50000], 
        "이메일": ["test@instagram.com"]
    }), []

def run_metrics_scraper_dummy(url):
    """콘텐츠 성과 수치(조회수, 좋아요 등)를 가져오는 가상 함수"""
    time.sleep(0.5) 
    return {
        "게재일": "26/03/09",  
        "조회수": random.randint(5000, 500000),
        "좋아요": random.randint(100, 10000),
        "댓글": random.randint(10, 500),
        "저장": random.randint(5, 300),
        "공유": random.randint(1, 100),
        "리포스트": 0
    }
