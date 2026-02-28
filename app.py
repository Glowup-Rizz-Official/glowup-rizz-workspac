import streamlit as st
import pandas as pd
import sqlite3
import re
import time
import os
import base64
from datetime import datetime, timedelta, timezone

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.header import Header

import googleapiclient.discovery
import google.generativeai as genai
from apify_client import ApifyClient

# ==========================================
# ⚙️ 기본 설정 및 공통 초기화
# ==========================================
st.set_page_config(page_title="Glowup Rizz 통합 솔루션", page_icon="💡", layout="wide")

# API Key 설정
try:
    YOUTUBE_KEY = st.secrets["YOUTUBE_API_KEY"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
    APIFY_TOKEN = st.secrets["APIFY_API_TOKEN"]
except KeyError:
    st.error("🚨 보안 설정(.streamlit/secrets.toml)에 API 키(YouTube, Gemini, Apify)를 모두 입력해주세요.")
    st.stop()

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('models/gemini-2.0-flash')
YOUTUBE = googleapiclient.discovery.build('youtube', 'v3', developerKey=YOUTUBE_KEY)
apify_client = ApifyClient(APIFY_TOKEN)

# ==========================================
# 🗄️ 데이터베이스 설정
# ==========================================
def init_creator_db():
    conn = sqlite3.connect('influencer_db.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS influencers 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT, category TEXT, channel_name TEXT, email TEXT, url TEXT, subscribers INTEGER, description TEXT, collected_at TEXT)''')
    try:
        c.execute("ALTER TABLE influencers ADD COLUMN status TEXT DEFAULT '대기'")
    except sqlite3.OperationalError:
        pass
        
    c.execute('''CREATE TABLE IF NOT EXISTS api_usage 
                 (id INTEGER PRIMARY KEY, youtube_count INTEGER, ai_count INTEGER, last_reset TEXT)''')
    c.execute("SELECT count(*) FROM api_usage")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO api_usage (id, youtube_count, ai_count, last_reset) VALUES (1, 0, 0, ?)", (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
    conn.commit()
    conn.close()

def save_creator_to_db(platform, category, channel_name, email, url, subscribers, description):
    conn = sqlite3.connect('influencer_db.db')
    c = conn.cursor()
    c.execute("SELECT id, channel_name FROM influencers WHERE email=?", (email,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO influencers (platform, category, channel_name, email, url, subscribers, description, collected_at, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '대기')",
                  (platform, category, channel_name, email, url, subscribers, description, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    else:
        # DB에 이미 있지만, 새로운 이름이 한글을 포함하고 기존 이름은 한글이 없을 경우 자동으로 업데이트 해줍니다!
        old_name = row[1]
        if channel_name != old_name and re.search(r'[가-힣]', channel_name) and not re.search(r'[가-힣]', old_name):
            c.execute("UPDATE influencers SET channel_name=?, description=? WHERE email=?", (channel_name, description, email))
    conn.commit()
    conn.close()

def update_creator_status(email, status):
    conn = sqlite3.connect('influencer_db.db')
    c = conn.cursor()
    c.execute("UPDATE influencers SET status = ? WHERE email = ?", (status, email))
    conn.commit()
    conn.close()

def delete_creators_from_db(emails_to_delete):
    if not emails_to_delete: return
    conn = sqlite3.connect('influencer_db.db')
    c = conn.cursor()
    placeholders = ','.join('?' for _ in emails_to_delete)
    c.execute(f"DELETE FROM influencers WHERE email IN ({placeholders})", tuple(emails_to_delete))
    conn.commit()
    conn.close()

BRAND_DB_FILE = "glowup_crm_db.csv"
if not os.path.exists(BRAND_DB_FILE):
    pd.DataFrame(columns=["Email", "Keyword", "Discovered_Date", "Last_Sent_Date", "Send_Count", "Template_Used"]).to_csv(BRAND_DB_FILE, index=False, encoding="utf-8-sig")

def load_brand_db():
    try: return pd.read_csv(BRAND_DB_FILE, encoding='utf-8-sig')
    except: return pd.read_csv(BRAND_DB_FILE, encoding='cp949')

def save_brand_db(df):
    df.to_csv(BRAND_DB_FILE, index=False, encoding="utf-8-sig")

init_creator_db()

# ==========================================
# 🛠️ 유틸리티 함수
# ==========================================
def get_kst_now(): return datetime.now(timezone.utc) + timedelta(hours=9)

def manage_api_quota(yt_add=0, ai_add=0):
    conn = sqlite3.connect('influencer_db.db')
    c = conn.cursor()
    c.execute("SELECT youtube_count, ai_count, last_reset FROM api_usage WHERE id=1")
    yt_current, ai_current, last_reset_str = c.fetchone()
    now_kst = get_kst_now()
    last_reset_kst = datetime.strptime(last_reset_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=9))) if last_reset_str else now_kst
    today_5pm = now_kst.replace(hour=17, minute=0, second=0, microsecond=0)
    reset_threshold = today_5pm - timedelta(days=1) if now_kst < today_5pm else today_5pm
    if last_reset_kst < reset_threshold:
        yt_current = 0
        c.execute("UPDATE api_usage SET youtube_count = 0, last_reset = ? WHERE id=1", (now_kst.strftime('%Y-%m-%d %H:%M:%S'),))
        conn.commit()
    if yt_add > 0 or ai_add > 0:
        c.execute("UPDATE api_usage SET youtube_count = youtube_count + ?, ai_count = ai_count + ? WHERE id=1", (yt_add, ai_add))
        conn.commit()
        yt_current += yt_add; ai_current += ai_add
    conn.close()
    return yt_current, ai_current

def get_image_base64(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file: return base64.b64encode(img_file.read()).decode('utf-8')
    return None

# ==========================================
# 🚀 메인 네비게이션
# ==========================================
with st.sidebar:
    st.image("https://via.placeholder.com/300x100.png?text=Glowup+Rizz", use_container_width=True)
    st.markdown("### 🎛️ 솔루션 모드 선택")
    app_mode = st.radio("작업 영역을 선택하세요", ["1️⃣ 크리에이터 발굴 엔진 (시딩용)", "2️⃣ 브랜드 영업 자동화 (B2B 제안용)"])
    st.markdown("---")
    yt_used, ai_used = manage_api_quota()
    st.markdown("### 📊 리소스 현황")
    st.progress(min(yt_used / 500000, 1.0))
    st.caption(f"📺 YouTube API: {yt_used:,} / 500,000")
    st.write(f"🤖 **AI API 호출 횟수:** {ai_used:,}회")

# ==========================================
# 🟢 MODE 1: 크리에이터 발굴 엔진 & 시딩 자동화
# ==========================================
if "1️⃣" in app_mode:
    st.title("🌐 Glowup Rizz 크리에이터 검색 엔진 & 시딩 자동화")
    
    FIXED_SENDER_NAME = "박혜란"
    FIXED_CARD_PATH = "cards/HR.png"
    
    COUNTRIES = {"대한민국": "KR", "미국": "US", "일본": "JP"}
    SUB_RANGES = {"전체": (0, 100000000), "1만 미만": (0, 10000), "1만 ~ 5만": (10000, 50000), "5만 ~ 10만": (50000, 100000), "10만 ~ 50만": (100000, 500000), "50만 ~ 100만": (500000, 1000000)}
    CATEGORIES = ["뷰티", "패션", "리빙", "육아", "반려동물", "IT/테크", "먹방/푸드", "기타"]

    if "youtube_results" not in st.session_state: st.session_state.youtube_results = None

    def extract_email_ai(desc):
        if not desc or len(desc) < 5: return ""
        try:
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', desc)
            if emails: return emails[0]
            manage_api_quota(ai_add=1)
            response = model.generate_content(f"다음 텍스트에서 이메일 주소만 추출해. 없으면 None: {desc}")
            res = response.text.strip()
            return res if "@" in res else ""
        except: return ""

    def check_performance(up_id, subs):
        try:
            manage_api_quota(yt_add=1)
            req = YOUTUBE.playlistItems().list(part="contentDetails", playlistId=up_id, maxResults=10).execute()
            v_ids = [i['contentDetails']['videoId'] for i in req.get('items', [])]
            if not v_ids: return False, 0, 0
            manage_api_quota(yt_add=1)
            v_res = YOUTUBE.videos().list(part="statistics,contentDetails", id=",".join(v_ids)).execute()
            longforms = [v for v in v_res['items'] if 'M' in v['contentDetails']['duration'] or 'H' in v['contentDetails']['duration']]
            if not longforms: return False, 0, 0
            avg_v = sum(int(v['statistics'].get('viewCount', 0)) for v in longforms) / len(longforms)
            eff = avg_v / subs if subs > 0 else 0
            return True, avg_v, eff
        except: return False, 0, 0

    def scrape_sns_apify(platform, keyword, category, max_pages=10):
        influencers = []
        site_domain = "instagram.com" if platform == "Instagram" else "tiktok.com"
        
        conn = sqlite3.connect('influencer_db.db')
        c = conn.cursor()
        c.execute("SELECT email FROM influencers")
        existing_emails = {row[0] for row in c.fetchall()}
        conn.close()
        
        contact_keywords = '("@gmail.com" OR "@naver.com" OR "이메일" OR "email" OR "협찬" OR "dm")'
        exclude_shops = '-"예약" -"오픈카톡" -"카카오채널" -"스튜디오" -"원장" -"살롱" -"클래스" -"진단" -"공식" -"official" -"정부" -"공공기관" -"센터" -"협회" -"국립" -"박물관" -"미술관" -"고객센터"'
        
        search_query = f'site:{site_domain} {keyword} {contact_keywords} {exclude_shops}'
        if platform == "Instagram": search_query += " -inurl:tags -inurl:explore"
        else: search_query += " -inurl:tag"
            
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

        run_input = {
            "queries": search_query,
            "maxPagesPerQuery": max_pages,
            "resultsPerPage": 20,
            "countryCode": "kr",
            "languageCode": "ko"
        }
        
        try:
            run = apify_client.actor("apify/google-search-scraper").call(run_input=run_input)
            blacklist_words = ['official', 'shop', 'store', 'brand', 'company', 'clinic', 'studio', 'museum', 'academy', 
                               '공식', '쇼핑몰', '도매', '정부', '공공기관', '재단', '협회', '센터', '예약', '국립', '박물관', '미술관', '주식회사', '고객센터', '문의처', '대표번호']
            
            for item in apify_client.dataset(run["defaultDatasetId"]).iterate_items():
                for res in item.get("organicResults", []):
                    snippet = res.get("description", "")
                    link = res.get("url", "")
                    title = res.get("title", "")
                    
                    if not re.search(r'[가-힣]', snippet) and not re.search(r'[가-힣]', title): continue
                    if "/tags/" in link.lower() or "/explore" in link.lower(): continue 
                        
                    emails = re.findall(email_pattern, snippet)
                    if emails and site_domain in link:
                        target_email = emails[0]
                        
                        # 🌟 이름 정밀 추출 🌟
                        extracted_id = ""
                        display_name = ""
                        
                        parts = link.split(f"{site_domain}/")[-1].split("/")
                        if parts and parts[0] not in ['p', 'reel', 'reels', 'tv', 'video', 'tag']:
                            extracted_id = parts[0].replace("@", "").split('?')[0]
                        
                        # 1. 스니펫에서 추출 (강력한 패턴: - 이름 (@아이디) 님의)
                        sn_match = re.search(r'-\s*(.*?)\s*\(@([a-zA-Z0-9._]+)\)', snippet)
                        if sn_match:
                            display_name = sn_match.group(1).strip()
                            if not extracted_id: extracted_id = sn_match.group(2).strip()
                            
                        # 2. 타이틀에서 추출
                        if not display_name:
                            ti_match = re.search(r'^(.*?)\s*\(@([a-zA-Z0-9._]+)\)', title)
                            if ti_match:
                                display_name = ti_match.group(1).strip()
                                if not extracted_id: extracted_id = ti_match.group(2).strip()
                            else:
                                ti_nim = re.search(r'(Instagram|인스타그램)의\s*(.*?)\s*님', title, re.IGNORECASE)
                                if ti_nim:
                                    display_name = ti_nim.group(2).strip()
                                    
                        # 찌꺼기 글자 청소
                        display_name = re.sub(r'^(Instagram의|인스타그램의)\s*', '', display_name, flags=re.IGNORECASE).strip()
                        display_name = re.sub(r'(-|\||•|Instagram|인스타그램|사진|동영상|프로필|게시물).*$', '', display_name, flags=re.IGNORECASE).strip()
                        display_name = display_name.replace("님의", "").replace("님", "").strip()
                        
                        # 최종 이름 결정
                        channel_name = display_name if display_name else extracted_id
                        if not channel_name or "링크참고" in channel_name:
                            channel_name = target_email.split('@')[0]
                        
                        is_blacklisted = any(word in channel_name.lower() for word in blacklist_words) or \
                                         any(word in snippet.lower() for word in blacklist_words) or \
                                         any(word in title.lower() for word in blacklist_words)
                        if is_blacklisted: continue

                        # 🌟 마법의 로직: 이미 DB에 있는 사람이지만, 새로 찾은 이름이 한글이고 예전엔 아니었다면 몰래 DB 업데이트!
                        if target_email in existing_emails:
                            if re.search(r'[가-힣]', channel_name):
                                conn = sqlite3.connect('influencer_db.db')
                                c = conn.cursor()
                                c.execute("SELECT channel_name FROM influencers WHERE email=?", (target_email,))
                                existing_row = c.fetchone()
                                if existing_row:
                                    old_name = existing_row[0]
                                    # 예전 이름에 한글이 없었는데, 지금 찾은 건 한글 이름이라면? 덮어씌운다!
                                    if channel_name != old_name and not re.search(r'[가-힣]', old_name):
                                        c.execute("UPDATE influencers SET channel_name=? WHERE email=?", (channel_name, target_email))
                                        conn.commit()
                                conn.close()
                            continue # 중복이므로 표에는 띄우지 않음
                            
                        existing_emails.add(target_email)
                        influencers.append({"플랫폼": platform, "카테고리": category, "채널명": channel_name, "이메일": target_email, "URL": link, "소개글": snippet})
        except Exception as e:
            st.error(f"Apify 검색 중 오류 발생: {e}")
            
        return pd.DataFrame(influencers)

    def get_seeding_template(template_choice, c_name, sender_name):
        display_name = c_name if c_name else "크리에이터"
        
        if "MELV" in template_choice:
            subject = f"[MELV] {display_name}님, 멜브 첫 공식 런칭 제품 시딩 제안드립니다 💖"
            body = f"""<div style="font-family: 'Apple SD Gothic Neo', sans-serif; line-height: 1.6; color: #222;">
            안녕하세요, {display_name}님!<br>
            뷰티 브랜드 MELV(멜브) MD {sender_name}입니다. :)<br><br>
            이번 MELV의 첫 공식 런칭으로, 브랜드 무드와 가장 잘 어울리는 크리에이터분들께만 제일 빠르게! 런칭 제품을 선물 드리고 싶어 연락드렸습니다! 💖<br><br>
            <b>1. MELV 립시럽 (2종)</b><br>
            기존 글로우 립의 요플레 현상과 끈적임을 확실하게 잡았습니다.<br>
            특히 말랑한 물방울 실리콘 팁이 맑은 광택감을 온전히 살려주며, 호호바씨오일과 시어버터를 듬뿍 담아 단순히 겉광만 내는 것이 아니라 건조한 입술에 깊은 보습감까지 꽉 채워줍니다.<br><br>
            <b>2. MELV 립타투 (3종)</b><br>
            촌스러운 핑크 착색이 아닌, 감성적인 뮤티드 컬러로 뽑아낸 신개념 타투 립입니다.<br>
            밥을 먹거나 물놀이를 해도 쉽게 지워지지 않는 강력한 지속력을 자랑하며, 보습 성분(콜라겐, 펩타이드)을 함유하여 떼어낼 때 자극이 적고 건조함 없이 편안하게 마무리됩니다.<br><br>
            {display_name}님을 위해 아낌없이 전 컬러를 꽉 채워 보내드릴 예정입니다!<br>
            본 키트는 제품 협찬으로, 수령 후 인스타그램 피드 또는 스토리에 공식 계정(@melv.kr) 태그와 함께 업로드가 가능하신 분들께만 한정적으로 발송해 드리고 있습니다. 🙏<br>
            (선정된 소수의 분들께만 드리는 키트인 만큼, {display_name}님의 감각적인 후기를 꼭 보고 싶습니다...💖)<br><br>
            진행이 가능하시다면 받아보실 <b>[성함 / 연락처 / 주소]</b>를 남겨주세요. 정성껏 포장해서 보내드리겠습니다.<br><br>
            감사합니다!<br><br>
            <img src="cid:biz_card" alt="{sender_name} 명함" style="max-width: 400px; border: 1px solid #eaeaea; border-radius: 4px;">
            </div>"""
            attach_images = ["melv1.jpg", "melv2.jpg"]
        elif "SOLV" in template_choice:
            subject = f"[SOLV] {display_name}님, 솔브 첫 공식 런칭 에스테틱 모델링팩 시딩 제안드립니다 💖"
            body = f"""<div style="font-family: 'Apple SD Gothic Neo', sans-serif; line-height: 1.6; color: #222;">
            안녕하세요, {display_name}님!<br>
            기초 뷰티 브랜드 SOLV(솔브) MD {sender_name}입니다. :)<br><br>
            이번 SOLV의 첫 공식 런칭으로, 브랜드 무드와 가장 잘 어울리는 크리에이터분들께만 제일 빠르게! 런칭 제품을 선물 드리고 싶어 연락드렸습니다! 💖<br><br>
            <b>&lt;SOLV 모델링팩(5개입)&gt;</b><br>
            💧 <b>물 조절 실패 ZERO!</b><br>
            기존 모델링팩의 단점인 가루 날림과 번거로운 물 조절은 이제 그만! 베이스와 세럼을 섞기만 하면 되는 간편한 방식으로, 떼어낸 후에도 건조함 없이 피부 위 윤광 코팅 효과를 선사합니다.<br><br>
            ❄️ <b>에스테틱 급 쿨링 효과!</b><br>
            시중 모델링팩 중 쿨링 성분을 최대치로 담아, 열감으로 넓어진 모공과 예민해진 피부를 즉각적으로 진정시켜 에스테틱에서 관리받은 듯한 최상의 컨디션을 만들어줍니다.<br><br>
            💄 <b>화잘먹을 위한 필수템!</b><br>
            피부 온도가 낮아지면 베이스 메이크업의 밀착력이 달라집니다. 홈케어로 피부결을 정돈해 메이크업 시간과 화장품 비용을 획기적으로 줄여보세요.<br><br>
            <b>[사용 방법 & TIP]</b><br>
            팩볼에 1제+2제를 컵에 넣고 빠르게 섞어 스파출라로 펴 바른 뒤 완전히 마르면 제거해 주세요. (TIP: 가장자리는 두껍게 바르면 한 번에 깔끔하게 제거됩니다!)<br>
            남은 영양감은 툭툭 두드려 흡수해 주세요! 별도의 세안이 필요 없는 고영양 세럼 제형입니다.<br><br>
            본 제품은 협찬으로, 수령 후 인스타그램 피드 또는 스토리에 공식 계정(@solv.kr) 태그와 함께 업로드가 가능하신 분들께만 한정적으로 발송해 드리고 있습니다. 🙏<br>
            (선정된 소수의 분들께만 드리는 이벤트인 만큼, {display_name}님의 감각적인 후기를 꼭 보고 싶습니다...💖)<br><br>
            진행이 가능하시다면 받아보실 <b>[성함 / 연락처 / 주소]</b>를 남겨주세요. 정성껏 포장해서 보내드리겠습니다.<br><br>
            감사합니다!<br><br>
            <img src="cid:biz_card" alt="{sender_name} 명함" style="max-width: 400px; border: 1px solid #eaeaea; border-radius: 4px;">
            </div>"""
            attach_images = ["solv1.jpg", "solv2.jpg"]
        else:
            subject = f"[UPPR] {display_name}님, 어퍼의 소두핏 코듀로이 볼캡 & 체크셔츠 시딩 제안드립니다 🧢"
            body = f"""<div style="font-family: 'Apple SD Gothic Neo', sans-serif; line-height: 1.6; color: #222;">
            안녕하세요, {display_name}님!<br>
            캐주얼 브랜드 UPPR(어퍼) MD {sender_name}입니다. :)<br><br>
            평소 {display_name}님의 감각적인 무드를 눈여겨보다가, 이번에 새롭게 선보이는 UPPR의 시그니처 아이템들이 찰떡같이 어울리실 것 같아 가장 먼저 선물로 보내드리고 싶어 연락드렸습니다! 🧢<br><br>
            <b>1. UPPR 코듀로이 볼캡 (소두핏 끝판왕)</b><br>
            얇은 면이 아닌 탄탄하고 도톰한 피그먼트 워싱 코듀로이 원단으로 정수리 꺼짐 없이 핏을 꽉 잡아줍니다.<br>
            특히 깊이감 있는 설계와 길고 넓은 챙이 광대를 자연스럽게 커버해 어떤 얼굴형이든 완벽한 '소두핏'을 연출해 줍니다.<br><br>
            <b>2. UPPR 시그니처 체크셔츠</b><br>
            트렌디한 미니 격자 패턴과 자연스럽게 떨어지는 오버핏 실루엣! 바쁜 아침 화장 없이 볼캡과 툭 걸치기만 해도 힙한 '꾸안꾸' 데일리 코디가 완성됩니다.<br><br>
            본 제품은 협찬으로, 수령 후 리뷰 업로드가 가능하신 분들께만 한정적으로 발송해 드리고 있습니다. 🙏<br><br>
            진행이 가능하시다면 받아보실 <b>[성함 / 연락처 / 주소 / 셔츠사이즈(M,L)]</b>를 남겨주세요. 정성껏 포장해서 보내드리겠습니다.<br><br>
            감사합니다!<br><br>
            <img src="cid:biz_card" alt="{sender_name} 명함" style="max-width: 400px; border: 1px solid #eaeaea; border-radius: 4px;">
            </div>"""
            attach_images = ["uppr1.jpg", "uppr2.jpg"]
        return subject, body, attach_images

    tab_yt, tab_ig, tab_tk, tab_mail, tab_db = st.tabs(["📺 YouTube 검색", "📸 Instagram 검색", "🎵 TikTok 검색", "💌 시딩 메일 발송", "🗄️ 플랫폼별 DB 관리"])

    with tab_yt:
        st.subheader("유튜브 크리에이터 딥서치")
        with st.form("yt_search"):
            kws = st.text_input("검색 키워드 (쉼표 구분)")
            category_yt = st.selectbox("저장할 카테고리 지정", CATEGORIES)
            c1, c2, c3 = st.columns(3)
            with c1: selected_country = st.selectbox("국가", list(COUNTRIES.keys()))
            with c2: 
                sub_range = st.selectbox("구독자 범위", list(SUB_RANGES.keys()))
                min_subs, max_subs = SUB_RANGES[sub_range]
            with c3: max_res = st.number_input("분석 샘플 수", 5, 50, 20)
            c4, c5 = st.columns(2)
            with c4: search_mode = st.radio("검색 방식", ["영상 기반", "채널명 기반"], horizontal=True)
            with c5: eff_target = st.slider("최소 효율 (%)", 0, 100, 30) / 100
            btn_yt = st.form_submit_button("🚀 유튜브 분석 시작")

        if btn_yt and kws:
            manage_api_quota(yt_add=100)
            keywords = [k.strip() for k in kws.split(",")]
            final_list, processed = [], set()
            prog, curr, total = st.progress(0), 0, len(keywords) * max_res
            for kw in keywords:
                try:
                    search_type = "video" if "영상" in search_mode else "channel"
                    search = YOUTUBE.search().list(q=kw, part="snippet", type=search_type, maxResults=max_res, regionCode=COUNTRIES[selected_country]).execute()
                    for item in search['items']:
                        curr += 1; prog.progress(min(curr/total, 1.0))
                        cid = item['snippet']['channelId']
                        if cid in processed: continue
                        processed.add(cid)
                        ch_res = YOUTUBE.channels().list(part="snippet,statistics,contentDetails", id=cid).execute()
                        if not ch_res['items']: continue
                        ch = ch_res['items'][0]
                        subs = int(ch['statistics'].get('subscriberCount', 0))
                        if not (min_subs <= subs <= max_subs): continue
                        upid = ch['contentDetails']['relatedPlaylists']['uploads']
                        is_ok, avg_v, eff = check_performance(upid, subs)
                        if is_ok and eff >= eff_target:
                            email = extract_email_ai(ch['snippet']['description'])
                            final_list.append({"채널명": ch['snippet']['title'], "구독자": subs, "평균 조회수": int(avg_v), "효율": f"{eff*100:.1f}%", "이메일": email, "프로필": ch['snippet']['thumbnails']['default']['url'], "URL": f"https://youtube.com/channel/{cid}", "소개글": ch['snippet']['description']})
                except: break
            st.session_state.youtube_results = pd.DataFrame(final_list)

        if st.session_state.youtube_results is not None and not st.session_state.youtube_results.empty:
            st.dataframe(st.session_state.youtube_results, column_config={"프로필": st.column_config.ImageColumn(), "URL": st.column_config.LinkColumn("이동")}, use_container_width=True)
            if st.button("💾 검색 결과를 DB에 저장", key="save_yt"):
                saved_count = 0
                for _, row in st.session_state.youtube_results.iterrows():
                    if row['이메일']:
                        save_creator_to_db("YouTube", category_yt, row['채널명'], row['이메일'], row['URL'], row['구독자'], row['소개글'])
                        saved_count += 1
                st.success(f"{saved_count}명의 크리에이터가 DB에 저장되었습니다!")

    with tab_ig:
        st.subheader("인스타그램 인플루언서 발굴 (릴스 포함)")
        with st.form("ig_search"):
            kw_ig = st.text_input("검색 키워드 (예: \"뷰티\" 립)")
            cat_ig = st.selectbox("분류 카테고리", CATEGORIES)
            pages_ig = st.number_input("검색 깊이 (페이지 수)", 1, 30, 10)
            if st.form_submit_button("🚀 인스타 검색 시작") and kw_ig:
                with st.spinner("데이터를 분석하며 진짜 이름을 추출 중입니다... (기존 DB 이름도 몰래 업그레이드 중!)"):
                    df_ig = scrape_sns_apify("Instagram", kw_ig, cat_ig, pages_ig)
                if not df_ig.empty:
                    st.success(f"이메일과 이름이 확인된 새로운 타겟 {len(df_ig)}명을 찾았습니다. (기존 DB는 제외됨)")
                    st.dataframe(df_ig, column_config={"URL": st.column_config.LinkColumn("이동")}, use_container_width=True)
                    for _, row in df_ig.iterrows(): save_creator_to_db(row['플랫폼'], row['카테고리'], row['채널명'], row['이메일'], row['URL'], 0, row['소개글'])
                else: st.warning("수집된 데이터가 없거나 모두 이미 DB에 저장된 사람입니다. (메일 발송 탭에서 예전 데이터의 이름이 업그레이드되었는지 확인해보세요!)")

    with tab_tk:
        st.subheader("틱톡 크리에이터 발굴")
        with st.form("tk_search"):
            kw_tk = st.text_input("검색 키워드")
            cat_tk = st.selectbox("분류 카테고리", CATEGORIES, key="tk_cat")
            pages_tk = st.number_input("검색 깊이 (페이지 수)", 1, 30, 10, key="tk_page")
            if st.form_submit_button("🚀 틱톡 검색 시작") and kw_tk:
                with st.spinner("틱톡커 데이터를 수집 중입니다..."):
                    df_tk = scrape_sns_apify("TikTok", kw_tk, cat_tk, pages_tk)
                if not df_tk.empty:
                    st.success(f"새로운 타겟 {len(df_tk)}명을 찾았습니다. (기존 DB 제외됨)")
                    st.dataframe(df_tk, column_config={"URL": st.column_config.LinkColumn("이동")}, use_container_width=True)
                    for _, row in df_tk.iterrows(): save_creator_to_db(row['플랫폼'], row['카테고리'], row['채널명'], row['이메일'], row['URL'], 0, row['소개글'])
                else: st.warning("수집된 데이터가 없거나 모두 이미 DB에 저장된 사람입니다.")

    with tab_mail:
        st.subheader("💌 크리에이터 시딩 제안 메일 발송")
        
        conn = sqlite3.connect('influencer_db.db')
        df_pending = pd.read_sql_query("SELECT id, platform, channel_name, email FROM influencers WHERE status='대기'", conn)
        conn.close()
        
        st.info(f"현재 발송 대기 중인 크리에이터: **{len(df_pending)}명**")
        
        col_t1, col_t2 = st.columns(2)
        with col_t1: template_choice = st.radio("시딩 템플릿 선택", ["1. MELV (립시럽/립타투)", "2. SOLV (모델링팩)", "3. UPPR (볼캡/체크셔츠)"])
        with col_t2: 
            st.write(f"🪪 **고정 발신자:** {FIXED_SENDER_NAME}")
            st.write(f"🪪 **첨부 명함:** `{FIXED_CARD_PATH}`")
            
        subject_p, body_p, _ = get_seeding_template(template_choice, "OOO(이름)", FIXED_SENDER_NAME)
        with st.expander("👀 발송될 메일 미리보기 (선택한 이름으로 자동 치환됩니다)"):
            st.markdown(f"**제목:** {subject_p}")
            preview_html = body_p
            if os.path.exists(FIXED_CARD_PATH):
                preview_html = preview_html.replace('cid:biz_card', f'data:image/png;base64,{get_image_base64(FIXED_CARD_PATH)}')
            st.components.v1.html(preview_html, height=350, scrolling=True)

        st.markdown("### ✍️ 발송 대상 선택 및 이름 편집")
        st.caption("표에서 '발송선택'을 체크하세요. 이름이 어색하다면 **'📝 이름/채널명' 칸을 더블클릭해서 직접 예쁘게 수정**하신 후 발송하시면 됩니다!")
        
        if not df_pending.empty:
            df_pending.insert(0, '발송선택', False)
            
            edited_send_df = st.data_editor(
                df_pending,
                column_config={
                    "발송선택": st.column_config.CheckboxColumn("✅ 선택", default=False),
                    "channel_name": st.column_config.TextColumn("📝 이름/채널명 (클릭하여 수정!)"),
                    "platform": st.column_config.TextColumn("플랫폼", disabled=True),
                    "email": st.column_config.TextColumn("이메일", disabled=True),
                    "id": None 
                },
                hide_index=True,
                use_container_width=True,
                key="send_editor"
            )
            
            selected_rows = edited_send_df[edited_send_df['발송선택'] == True]
            
            st.markdown("---")
            c1, c2 = st.columns(2)
            sender_email = st.text_input("보내는 이메일", value=st.secrets.get("SENDER_EMAIL", "rizzsender@gmail.com"))
            sender_pw = st.text_input("앱 비밀번호", type="password", value=st.secrets.get("SENDER_PW", ""))

            if st.button(f"🚀 선택한 {len(selected_rows)}명에게 메일 발송", type="primary"):
                if not sender_pw or selected_rows.empty: 
                    st.error("앱 비밀번호를 입력하시고, 위 표에서 발송할 사람을 1명 이상 체크해주세요.")
                else:
                    prog_bar = st.progress(0); status_text = st.empty(); success_count = 0
                    
                    conn = sqlite3.connect('influencer_db.db')
                    c = conn.cursor()
                    
                    for idx, row in selected_rows.reset_index().iterrows():
                        t_email = row['email']
                        c_name = row['channel_name']
                        
                        c.execute("UPDATE influencers SET channel_name=? WHERE email=?", (c_name, t_email))
                        conn.commit()
                        
                        status_text.write(f"[{idx+1}/{len(selected_rows)}] {c_name}님에게 발송 중...")
                        try:
                            subject, body, imgs = get_seeding_template(template_choice, c_name, FIXED_SENDER_NAME)
                            msg = MIMEMultipart('related')
                            msg['From'], msg['To'], msg['Subject'] = sender_email, t_email, Header(subject, 'utf-8')
                            msg['Reply-To'] = "hcommerceinc1@gmail.com"
                            msg.attach(MIMEText(body, 'html', 'utf-8'))
                            
                            if os.path.exists(FIXED_CARD_PATH):
                                with open(FIXED_CARD_PATH, "rb") as f:
                                    img_data = MIMEImage(f.read()); img_data.add_header('Content-ID', '<biz_card>'); msg.attach(img_data)
                            for img_name in imgs:
                                if os.path.exists(img_name):
                                    with open(img_name, "rb") as f:
                                        part = MIMEApplication(f.read(), Name=img_name); part['Content-Disposition'] = f'attachment; filename="{img_name}"'; msg.attach(part)
                            
                            server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls(); server.login(sender_email, sender_pw.replace(' ', '')); server.send_message(msg); server.quit()
                            
                            c.execute("UPDATE influencers SET status = '발송완료' WHERE email = ?", (t_email,))
                            conn.commit()
                            success_count += 1; time.sleep(1.5)
                        except Exception as e: 
                            st.error(f"{t_email} 발송 실패: {e}")
                            
                        prog_bar.progress((idx + 1) / len(selected_rows))
                    
                    conn.close()
                    st.success(f"🎉 총 {success_count}명에게 성공적으로 발송 완료되었습니다! 화면을 새로고침하여 표를 갱신해주세요.")
                    time.sleep(2)
                    st.rerun()

    with tab_db:
        st.subheader("🗄️ 플랫폼별 DB 관리")
        conn = sqlite3.connect('influencer_db.db')
        df_db = pd.read_sql_query("SELECT platform, category, channel_name, email, url, status FROM influencers ORDER BY collected_at DESC", conn)
        conn.close()
        
        db_yt, db_ig, db_tk = st.tabs(["📺 YouTube", "📸 Instagram", "🎵 TikTok"])
        def render_platform_db(plat_name, df_all):
            df_plat = df_all[df_all['platform'] == plat_name].copy()
            df_plat.insert(0, '선택', False)
            edited_df = st.data_editor(df_plat, column_config={"선택": st.column_config.CheckboxColumn("선택", default=False), "url": st.column_config.LinkColumn("링크")}, use_container_width=True, hide_index=True, disabled=[c for c in df_plat.columns if c != '선택'], key=f"ed_{plat_name}")
            selected_emails = edited_df[edited_df['선택'] == True]['email'].tolist()
            c1, c2 = st.columns(2)
            with c1: st.download_button(f"📥 {plat_name} DB 다운로드", edited_df.drop(columns=['선택']).to_csv(index=False).encode('utf-8-sig'), f"influencers_{plat_name}.csv", "text/csv")
            with c2: 
                if selected_emails and st.button(f"🚨 {len(selected_emails)}명 삭제", key=f"del_btn_{plat_name}"):
                    delete_creators_from_db(selected_emails); st.rerun()
        with db_yt: render_platform_db("YouTube", df_db)
        with db_ig: render_platform_db("Instagram", df_db)
        with db_tk: render_platform_db("TikTok", df_db)

# ==========================================
# 🔵 MODE 2: 브랜드 영업 자동화 (B2B 제안용)
# ==========================================
elif "2️⃣" in app_mode:
    st.title("💡 Glowup Rizz 브랜드 영업 자동화 시스템")
    
    B2B_SENDER_INFO = {
        "윤혜선": "cards/HS.png",
        "김민준": "cards/MJ.png",
        "서영석": "cards/YS.png",
        "김효훈": "cards/HH.png"
    }

    def get_email_templates(sender_name):
        FONT_STYLE = "font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', 'Noto Sans KR', sans-serif; font-size: 14px; line-height: 1.6; color: #222222;"
        FORM_LINK = "<div style='background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e9ecef; margin: 25px 0; text-align: center;'><p style='margin: 0 0 10px 0; font-size: 15px; font-weight: bold; color: #333;'>🚀 COSY / YOGO 상시 입점 제휴 제안서 확인 및 신청</p><a href='https://forms.gle/Dte233GXJrR7nhpJ8' target='_blank' style='display: inline-block; padding: 12px 24px; background-color: #1a73e8; color: #ffffff; text-decoration: none; font-weight: bold; border-radius: 6px; font-size: 15px;'>👉 입점 신청 폼 바로가기 (클릭)</a></div>"
        SIGNATURE_HTML = f"<p style='margin-top: 30px; margin-bottom: 20px;'>긴 글 읽어주셔서 감사합니다.<br><b>글로우업리즈 {sender_name} 드림</b></p><img src='cid:biz_card' alt='{sender_name} 명함' style='max-width: 400px; height: auto; border: 1px solid #eaeaea; border-radius: 4px; display: block;'>"
        
        return {
            "1. [필살기] 커머스(117만) + 코시/상시": {
                "subject": "[글로우업리즈] 117만 유튜버 채널 연계 - 브랜드 입점 제안의 건", 
                "body": f"<div style=\"{FONT_STYLE}\"><p>대표님, 안녕하세요.<br>크리에이터 커머스 플랫폼 <b>글로우업리즈 {sender_name}</b>입니다.</p><p>단순히 제품을 진열만 하는 일반적인 제안이 아닙니다. 저희와 함께하시면 압도적인 파이프라인을 구축하실 수 있습니다.</p>{FORM_LINK}{SIGNATURE_HTML}</div>"
            },
            "2. [코시 중심] 마케팅 예산 없는 신생 브랜드용": {
                "subject": "[글로우업리즈] 인플루언서 시딩 비용 0원 - 코시(COSY) 입점 제안의 건", 
                "body": f"<div style=\"{FONT_STYLE}\"><p>대표님, 안녕하세요.<br>크리에이터 커머스 플랫폼 <b>글로우업리즈 {sender_name}</b>입니다.</p><p>저희 플랫폼의 <b>'크리에이터 자율 매칭 시스템(COSY)'</b>을 활용하시면 섭외 고민이 단번에 해결됩니다.</p>{FORM_LINK}{SIGNATURE_HTML}</div>"
            }
        }

    def scrape_smartstore_apify(keyword, max_pages=3):
        new_targets = []
        df = load_brand_db()
        existing_emails = set(df['Email'].tolist())
        
        run_input = {
            "queries": f"site:smartstore.naver.com {keyword}",
            "maxPagesPerQuery": max_pages,
            "resultsPerPage": 20,
            "countryCode": "kr",
            "languageCode": "ko"
        }
        
        try:
            run = apify_client.actor("apify/google-search-scraper").call(run_input=run_input)
            total_organic_results = 0
            
            for item in apify_client.dataset(run["defaultDatasetId"]).iterate_items():
                results = item.get("organicResults", [])
                total_organic_results += len(results)
                
                for res in results:
                    text_content = res.get("url", "") + " " + res.get("description", "")
                    store_ids = re.findall(r"smartstore\.naver\.com/([a-zA-Z0-9_-]+)", text_content)
                    
                    for sid in set(store_ids):
                        if sid.lower() not in ['category', 'notice', 'profile', 'best', 'products', 'search', 'main']:
                            email = f"{sid}@naver.com".lower()
                            if email not in existing_emails:
                                existing_emails.add(email)
                                new_targets.append({
                                    "Email": email, "Keyword": keyword, "Discovered_Date": datetime.now().strftime("%Y-%m-%d"), 
                                    "Last_Sent_Date": "", "Send_Count": 0, "Template_Used": ""
                                })
                                
            if total_organic_results == 0:
                st.warning(f"⚠️ Apify가 구글에서 '{keyword}' 관련 스마트스토어 검색 결과를 한 건도 찾지 못했습니다.")
            else:
                st.info(f"💡 구글 검색 결과 {total_organic_results}건의 사이트를 분석했습니다.")
                
        except Exception as e:
            st.error(f"Apify 검색 중 오류 발생: {e}")
            
        return new_targets

    tab_ai, tab_scrape, tab_mail, tab_crm = st.tabs(["🧠 AI 타겟 분석", "🕵️‍♀️ 스토어 메일 수집", "💌 콜드메일 발송", "📊 B2B CRM"])

    with tab_ai:
        st.subheader("🧠 검색 키워드 기반 발송 전략 추천")
        with st.form("ai_strategy_form"):
            ai_keyword = st.text_input("분석할 업종 키워드 (예: 색조화장품)")
            if st.form_submit_button("전략 분석하기") and ai_keyword:
                try:
                    with st.spinner("AI가 브랜드 페인포인트와 전략을 분석 중입니다..."):
                        prompt = f"너는 플랫폼 '글로우업리즈'의 입점 영업을 담당해. 타겟은 '{ai_keyword}' 파는 브랜드 대표야. 그들의 페인포인트를 분석하고 추천 템플릿과 영업 팁을 줘."
                        st.info(model.generate_content(prompt).text)
                except Exception as e:
                    if "ResourceExhausted" in str(e):
                        st.error("🚨 AI API 무료 사용량 초과. 1분 뒤에 다시 시도해주세요!")
                    else:
                        st.error(f"🚨 오류 발생: {e}")

    with tab_scrape:
        st.subheader("1. 새로운 브랜드 타겟 찾기 (Apify 엔진)")
        col_kw, col_page = st.columns([3, 1])
        with col_kw: keyword = st.text_input("스마트스토어 검색 키워드 (예: 코스메틱 공식)")
        with col_page: max_pages = st.number_input("검색할 페이지 수", 1, 10, 3)
        
        if st.button("수집 시작", type="primary"):
            if keyword:
                log_box = st.empty()
                log_box.empty()
                log_box.info("Apify 엔진을 통해 스마트스토어 메일을 빠르고 안전하게 수집 중입니다...")
                
                new_data = scrape_smartstore_apify(keyword, max_pages)
                
                log_box.empty()
                if new_data:
                    df = load_brand_db()
                    df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)
                    save_brand_db(df)
                    st.success(f"🎉 총 {len(new_data)}개의 새로운 타겟을 찾아 DB에 추가했습니다!")
                    time.sleep(0.5)
                    st.balloons()
                else:
                    st.warning("새로운 타겟을 찾지 못했거나 이미 모두 수집된 메일들입니다.")

    with tab_mail:
        st.subheader("2. 전략적 제휴 제안 메일 발송")
        col_name, col_card = st.columns([1, 2])
        with col_name: selected_sender_name = st.selectbox("발신자 이름 선택", list(B2B_SENDER_INFO.keys()))
        
        card_path = B2B_SENDER_INFO[selected_sender_name]
        has_card = os.path.exists(card_path)
        with col_card:
            st.write("")
            st.write(f"🪪 **첨부될 명함:** `{card_path}` {'✅ 준비완료' if has_card else '❌ 파일없음'}")
        
        EMAIL_TEMPLATES = get_email_templates(selected_sender_name)
        selected_template_name = st.selectbox("보낼 메일 템플릿을 선택하세요", list(EMAIL_TEMPLATES.keys()))
        selected_template = EMAIL_TEMPLATES[selected_template_name]
        
        with st.expander("👀 발송될 메일 미리보기"):
            preview_body = selected_template['body']
            if has_card: preview_body = preview_body.replace('cid:biz_card', f'data:image/png;base64,{get_image_base64(card_path)}')
            st.components.v1.html(preview_body, height=400, scrolling=True)
        
        c1, c2 = st.columns(2)
        default_email = st.secrets.get("SENDER_EMAIL", "rizzsender@gmail.com")
        default_pw = st.secrets.get("SENDER_PW", "")
        
        with c1: sender_email = st.text_input("보내는 사람 구글 이메일", value=default_email)
        with c2: sender_pw = st.text_input("구글 앱 비밀번호 16자리", type="password", value=default_pw)
        
        df = load_brand_db()
        target_df = df[(df['Last_Sent_Date'].isna()) | (df['Last_Sent_Date'] == "") | (df['Send_Count'] == 0)]
        st.write(f"🎯 **최초 발송 대기 중인 타겟: {len(target_df)}곳**")
        
        if st.button("🚀 위 템플릿으로 발송 시작", type="primary"):
            if not sender_pw: st.error("앱 비밀번호를 입력해주세요!")
            elif not has_card: st.error("명함 파일이 없습니다.")
            elif len(target_df) == 0: st.info("새로 보낼 타겟이 없습니다.")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                success_count = 0
                
                for i, idx in enumerate(target_df.index):
                    to_email = df.at[idx, 'Email'].replace(' ', '').strip()
                    
                    status_text.empty()
                    status_text.write(f"[{i+1}/{len(target_df)}] {to_email} 발송 중...")
                    
                    try:
                        msg = MIMEMultipart('related')
                        msg['From'] = sender_email
                        msg['To'] = to_email
                        msg['Subject'] = Header(selected_template['subject'], 'utf-8')
                        msg['Reply-To'] = "partner@glowuprizz.com"
                        
                        msg.attach(MIMEText(selected_template['body'].replace('\xa0', ' '), 'html', 'utf-8'))
                        
                        if has_card:
                            with open(card_path, "rb") as f:
                                img_data = MIMEImage(f.read())
                                img_data.add_header('Content-ID', '<biz_card>')
                                msg.attach(img_data)
                                
                        server = smtplib.SMTP('smtp.gmail.com', 587)
                        server.starttls()
                        server.login(sender_email, sender_pw.replace(' ', ''))
                        server.send_message(msg)
                        server.quit()
                        
                        df.at[idx, 'Last_Sent_Date'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                        df.at[idx, 'Send_Count'] = int(df.at[idx, 'Send_Count']) + 1
                        df.at[idx, 'Template_Used'] = selected_template_name.split(']')[0] + "]"
                        save_brand_db(df)
                        success_count += 1
                        time.sleep(2)
                    except Exception as e: st.error(f"{to_email} 발송 실패: {e}")
                    
                    progress_bar.progress((i + 1) / len(target_df))
                
                status_text.empty()
                time.sleep(0.5)
                st.success(f"🎉 총 {success_count}곳에 제안서 발송 완료!")

    with tab_crm:
        st.subheader("📊 B2B 콜드메일 CRM 데이터베이스 관리")
        df = load_brand_db()
        
        df.insert(0, '선택', False)
        
        edited_df_b2b = st.data_editor(
            df,
            column_config={
                "선택": st.column_config.CheckboxColumn("선택", default=False)
            },
            use_container_width=True,
            hide_index=True,
            disabled=[col for col in df.columns if col != '선택']
        )
        
        selected_emails_b2b = edited_df_b2b[edited_df_b2b['선택'] == True]['Email'].tolist()
        
        col_csv_b2b, col_del_b2b = st.columns([1, 1])
        with col_csv_b2b:
            csv_b2b = df.drop(columns=['선택']).to_csv(index=False).encode('utf-8-sig')
            st.download_button(label="📥 B2B 타겟 CSV 다운로드", data=csv_b2b, file_name="glowup_crm_db.csv", mime="text/csv")
        with col_del_b2b:
            if selected_emails_b2b:
                if st.button(f"🚨 선택한 타겟 {len(selected_emails_b2b)}곳 영구 삭제", type="primary"):
                    df_to_save = load_brand_db()
                    df_to_save = df_to_save[~df_to_save['Email'].isin(selected_emails_b2b)]
                    save_brand_db(df_to_save)
                    st.success(f"{len(selected_emails_b2b)}개의 타겟이 삭제되었습니다! 🔄 곧 화면이 새로고침됩니다.")
                    time.sleep(1.5)
                    st.rerun()
