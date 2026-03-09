import pandas as pd
import time
import random
import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build

def run_insta_scraper_real(keyword, progress_bar):
    """검색 엔진 우회를 시도하고, 차단될 경우 실전 테스트용 예비 데이터를 반환합니다."""
    url = f"https://html.duckduckgo.com/html/?q=site:instagram.com {keyword}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        progress_bar.progress(30, text="인스타그램 보안망 우회 탐색 중... (약 3초 소요)")
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        
        for a in soup.find_all('a'):
            href = a.get('href', '')
            if href and 'instagram.com/' in href and '/p/' not in href and '/reel/' not in href:
                parts = href.split('instagram.com/')
                if len(parts) > 1:
                    username = parts[1].replace('/', '').split('?')[0]
                    if username and username not in ['explore', 'developer', 'about', 'legal', 'p', 'reel']:
                        results.append({
                            "닉네임": username,
                            "프로필링크": f"https://www.instagram.com/{username}",
                            "팔로워수": "수기 확인 필요",
                            "이메일": ""
                        })
                        
        progress_bar.progress(100, text="탐색 완료!")
        time.sleep(1)
        progress_bar.empty()
        
        df = pd.DataFrame(results).drop_duplicates(subset=['닉네임'])
        
        # 💡 [핵심 로직] 서버 차단으로 0건이 나왔을 때, MVP 테스트를 위한 실제 계정 제공
        if df.empty:
            if "뷰티" in keyword or "화장품" in keyword:
                fallback_data = [
                    {"닉네임": "ponysmakeup", "프로필링크": "https://www.instagram.com/ponysmakeup", "팔로워수": "수기 확인 필요", "이메일": ""},
                    {"닉네임": "risabae_art", "프로필링크": "https://www.instagram.com/risabae_art", "팔로워수": "수기 확인 필요", "이메일": ""},
                    {"닉네임": "lamuqe_magicup", "프로필링크": "https://www.instagram.com/lamuqe_magicup", "팔로워수": "수기 확인 필요", "이메일": ""}
                ]
            elif "패션" in keyword or "옷" in keyword:
                fallback_data = [
                    {"닉네임": "kimehwa", "프로필링크": "https://www.instagram.com/kimehwa", "팔로워수": "수기 확인 필요", "이메일": ""},
                    {"닉네임": "bboggooo", "프로필링크": "https://www.instagram.com/bboggooo", "팔로워수": "수기 확인 필요", "이메일": ""}
                ]
            else:
                fallback_data = [
                    {"닉네임": "test_influencer1", "프로필링크": "https://www.instagram.com/test1", "팔로워수": "수기 확인 필요", "이메일": ""},
                    {"닉네임": "test_influencer2", "프로필링크": "https://www.instagram.com/test2", "팔로워수": "수기 확인 필요", "이메일": ""}
                ]
            return pd.DataFrame(fallback_data), ["서버 우회 차단으로 인해 '실전 예비 데이터'가 로드되었습니다."]
            
        return df, []
        
    except Exception as e:
        return pd.DataFrame({"에러": [f"우회 크롤링 에러: {e}"]}), []

# --- (아래 유튜브, 블로그, 수치 업데이트 함수는 직전과 동일하게 유지해 주세요!) ---
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

def run_blog_search_real(keyword):
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
            results.append({"플랫폼": "블로그", "제목": title, "프로필링크": link, "닉네임": "블로거", "이메일": ""})
        return pd.DataFrame(results)
    except Exception as e:
        return pd.DataFrame({"에러": [f"블로그 크롤링 실패: {e}"]})

def run_metrics_scraper_dummy(url):
    time.sleep(0.5) 
    return {"게재일": "26/03/09", "조회수": random.randint(5000, 500000), "좋아요": random.randint(100, 10000), "댓글": random.randint(10, 500), "저장": random.randint(5, 300), "공유": random.randint(1, 100), "리포스트": 0}
