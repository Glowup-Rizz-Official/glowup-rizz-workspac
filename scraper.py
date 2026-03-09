import pandas as pd
import time

def run_insta_scraper_dummy(keyword, progress_bar):
    """
    기획서 기반: 인스타 크롤링 로직 (Selenium 도입 전 임시 모델)
    """
    for i in range(100):
        time.sleep(0.01)  # 실제 크롤링 시 대기 시간
        progress_bar.progress(i + 1, text=f"봇이 데이터를 긁어오는 중... {i+1}%")
    
    time.sleep(0.5)
    progress_bar.empty()
    
    # 정상 데이터 및 에러 데이터 분류
    data = {
        "프로필링크": ["https://instagram.com/user1", "https://instagram.com/user2", "https://instagram.com/user3"],
        "닉네임": ["인플루언서A", "인플루언서B", "인플루언서C"],
        "팔로워수": [45000, 120000, 0],
        "최근조회수": [15000, 250000, 0],  # 25만은 UI에서 하이라이트 됨
        "이메일": ["user1@mail.com", "user2@mail.com", ""],
        "상태": ["정상", "정상", "비공개/삭제됨"] # 예외 처리 반영
    }
    
    df = pd.DataFrame(data)
    failed_links = ["https://instagram.com/user3"] # 실패 리스트 따로 반환
    
    return df, failed_links
# scraper.py 맨 아래에 추가
import random

def run_metrics_scraper_dummy(url):
    """
    링크에 접속해서 조회수, 좋아요 등을 긁어오는 가상 함수
    """
    time.sleep(0.5) # 크롤링 하는 척 대기
    
   
    return {
        "게재일": "24/02/15",  # 원래는 페이지에서 날짜를 파싱해야 함
        "조회수": random.randint(5000, 500000),
        "좋아요": random.randint(100, 10000),
        "댓글": random.randint(10, 500),
        "저장": random.randint(5, 300),
        "공유": random.randint(1, 100),
        "리포스트": 0
    }
