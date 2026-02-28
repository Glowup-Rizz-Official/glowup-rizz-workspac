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
    # 이메일 중복 체크로 변경 (안정성)
    c.execute("SELECT id FROM influencers WHERE email=?", (email,))
    if not c.fetchone():
        c.execute("INSERT INTO influencers (platform, category, channel_name, email, url, subscribers, description, collected_at, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '대기')",
                  (platform, category, channel_name, email, url, subscribers, description, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
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

    def scrape_sns_apify(platform, keyword, category, max_pages=10):
        influencers = []
        site_domain = "instagram.com" if platform == "Instagram" else "tiktok.com"
        
        contact_keywords = '("@gmail.com" OR "@naver.com" OR "이메일" OR "email" OR "협찬" OR "dm")'
        exclude_shops = '-"예약" -"오픈카톡" -"카카오채널" -"스튜디오" -"원장" -"살롱" -"클래스" -"진단" -"공식" -"official" -"정부" -"공공기관" -"센터" -"협회"'
        
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
            blacklist_words = ['official', 'shop', 'store', 'brand', 'company', 'clinic', 'studio', '공식', '쇼핑몰', '도매', '정부', '공공기관', '재단', '협회', '센터', '예약']
            
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
                        
                        # 🌟 [개선] 릴스에서도 닉네임을 찾아내는 스마트 아이디 추출 시스템 🌟
                        extracted_id = ""
                        
                        # 1순위: 구글 제목의 괄호 (@아이디) 추출
                        username_match = re.search(r'\(@([a-zA-Z0-9._]+)\)', title)
                        if username_match:
                            extracted_id = username_match.group(1)
                        
                        # 2순위: 릴스 링크가 아닐 경우 URL에서 추출
                        if not extracted_id:
                            parts = link.split(f"{site_domain}/")[-1].split("/")
                            if parts and parts[0] not in ['p', 'reel', 'reels', 'tv']:
                                extracted_id = parts[0].replace("@", "")
                        
                        # 3순위 (최후의 수단): 이메일의 앞부분을 아이디로 간주
                        if not extracted_id or "링크참고" in extracted_id:
                            extracted_id = target_email.split('@')[0]
                            
                        channel_name = extracted_id
                        
                        # 블랙리스트 필터
                        is_blacklisted = any(word in channel_name.lower() for word in blacklist_words) or \
                                         any(word in snippet.lower() for word in blacklist_words) or \
                                         any(word in title.lower() for word in blacklist_words)
                        if is_blacklisted: continue
                            
                        influencers.append({"플랫폼": platform, "카테고리": category, "채널명": channel_name, "이메일": target_email, "URL": link, "소개글": snippet})
        except Exception as e:
            st.error(f"Apify 검색 중 오류 발생: {e}")
            
        return pd.DataFrame(influencers).drop_duplicates(subset=['이메일'])

    def get_seeding_template(template_choice, c_name, sender_name):
        # OOO님 호칭이 어색하지 않게 처리
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

    with tab_ig:
        st.subheader("인스타그램 인플루언서 발굴 (릴스 포함)")
        with st.form("ig_search"):
            kw_ig = st.text_input("검색 키워드 (예: \"뷰티\" 립)")
            cat_ig = st.selectbox("분류 카테고리", CATEGORIES)
            pages_ig = st.number_input("검색 깊이 (페이지 수)", 1, 30, 10)
            if st.form_submit_button("🚀 인스타 검색 시작") and kw_ig:
                with st.spinner("릴스 및 게시물 데이터를 분석하며 아이디를 추출 중입니다..."):
                    df_ig = scrape_sns_apify("Instagram", kw_ig, cat_ig, pages_ig)
                if not df_ig.empty:
                    st.success(f"이메일과 아이디가 확인된 {len(df_ig)}명을 찾았습니다.")
                    st.dataframe(df_ig, column_config={"URL": st.column_config.LinkColumn("이동")}, use_container_width=True)
                    for _, row in df_ig.iterrows(): save_creator_to_db(row['플랫폼'], row['카테고리'], row['채널명'], row['이메일'], row['URL'], 0, row['소개글'])
                else: st.warning("수집된 데이터가 없습니다.")

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
                    st.success(f"{len(df_tk)}명을 찾았습니다.")
                    st.dataframe(df_tk, column_config={"URL": st.column_config.LinkColumn("이동")}, use_container_width=True)
                    for _, row in df_tk.iterrows(): save_creator_to_db(row['플랫폼'], row['카테고리'], row['채널명'], row['이메일'], row['URL'], 0, row['소개글'])

    with tab_mail:
        st.subheader("💌 크리에이터 시딩 제안 메일 발송")
        conn = sqlite3.connect('influencer_db.db')
        df_pending = pd.read_sql_query("SELECT platform, channel_name, email FROM influencers WHERE status='대기'", conn)
        conn.close()
        
        st.info(f"발송 대기 중: **{len(df_pending)}명**")
        template_choice = st.radio("시딩 템플릿 선택", ["1. MELV (립시럽/립타투)", "2. SOLV (모델링팩)", "3. UPPR (볼캡/체크셔츠)"])
        
        subject_p, body_p, _ = get_seeding_template(template_choice, "아이디", FIXED_SENDER_NAME)
        with st.expander("👀 발송될 메일 미리보기"):
            st.markdown(f"**제목:** {subject_p}")
            preview_html = body_p
            if os.path.exists(FIXED_CARD_PATH):
                preview_html = preview_html.replace('cid:biz_card', f'data:image/png;base64,{get_image_base64(FIXED_CARD_PATH)}')
            st.components.v1.html(preview_html, height=350, scrolling=True)

        c1, c2 = st.columns(2)
        sender_email = st.text_input("보내는 이메일", value=st.secrets.get("SENDER_EMAIL", "rizzsender@gmail.com"))
        sender_pw = st.text_input("앱 비밀번호", type="password", value=st.secrets.get("SENDER_PW", ""))
        selected_creators = st.multiselect("발송 대상 선택", df_pending['email'].tolist(), format_func=lambda x: f"{df_pending[df_pending['email']==x]['channel_name'].values[0]} ({x})")

        if st.button("🚀 선택한 크리에이터에게 메일 발송", type="primary"):
            if not sender_pw or not selected_creators: st.error("정보를 확인해주세요.")
            else:
                prog_bar = st.progress(0); status_text = st.empty(); success_count = 0
                for idx, t_email in enumerate(selected_creators):
                    c_name = df_pending[df_pending['email']==t_email]['channel_name'].values[0]
                    status_text.write(f"[{idx+1}/{len(selected_creators)}] {c_name}님 발송 중...")
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
                        update_creator_status(t_email, '발송완료'); success_count += 1; time.sleep(1.5)
                    except Exception as e: st.error(f"{t_email} 실패: {e}")
                    prog_bar.progress((idx + 1) / len(selected_creators))
                st.success(f"🎉 총 {success_count}명 발송 완료!")

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

    with tab_yt:
        st.subheader("유튜브 크리에이터 검색 (기본 로직)")
        with st.form("yt_search"):
            kws = st.text_input("키워드")
            category_yt = st.selectbox("카테고리", CATEGORIES)
            c1, c2, c3 = st.columns(3)
            with c1: selected_country = st.selectbox("국가", list(COUNTRIES.keys()))
            with c2: sub_range = st.selectbox("구독자", list(SUB_RANGES.keys()))
            with c3: max_res = st.number_input("분석 샘플 수", 5, 50, 20)
            btn_yt = st.form_submit_button("🚀 검색")
        if btn_yt and kws:
            manage_api_quota(yt_add=100); min_subs, max_subs = SUB_RANGES[sub_range]
            final_list, processed = [], set()
            for kw in kws.split(","):
                search = YOUTUBE.search().list(q=kw.strip(), part="snippet", type="video", maxResults=max_res, regionCode=COUNTRIES[selected_country]).execute()
                for item in search['items']:
                    cid = item['snippet']['channelId']
                    if cid in processed: continue
                    processed.add(cid)
                    ch = YOUTUBE.channels().list(part="snippet,statistics,contentDetails", id=cid).execute()['items'][0]
                    subs = int(ch['statistics'].get('subscriberCount', 0))
                    if min_subs <= subs <= max_subs:
                        email = extract_email_ai(ch['snippet']['description'])
                        final_list.append({"채널명": ch['snippet']['title'], "구독자": subs, "이메일": email, "URL": f"https://youtube.com/channel/{cid}", "프로필": ch['snippet']['thumbnails']['default']['url']})
            st.session_state.youtube_results = pd.DataFrame(final_list)
            st.dataframe(st.session_state.youtube_results, column_config={"프로필": st.column_config.ImageColumn(), "URL": st.column_config.LinkColumn("이동")})
            if st.button("💾 DB 저장"):
                for _, r in st.session_state.youtube_results.iterrows():
                    if r['이메일']: save_creator_to_db("YouTube", category_yt, r['채널명'], r['이메일'], r['URL'], r['구독자'], "")
                st.success("저장 완료!")

# ==========================================
# 🔵 MODE 2: 브랜드 영업 자동화 (B2B)
# ==========================================
elif "2️⃣" in app_mode:
    st.title("💡 Glowup Rizz 브랜드 영업 자동화 시스템")
    B2B_SENDER_INFO = {"윤혜선": "cards/HS.png", "김민준": "cards/MJ.png", "서영석": "cards/YS.png", "김효훈": "cards/HH.png"}

    def get_email_templates(sender_name):
        FONT_STYLE = "font-family: 'Apple SD Gothic Neo', sans-serif; font-size: 14px; line-height: 1.6; color: #222;"
        FORM_LINK = "<div style='background-color: #f8f9fa; padding: 20px; text-align: center; border: 1px solid #eee; margin: 20px 0;'><a href='https://forms.gle/Dte233GXJrR7nhpJ8' style='padding: 12px 24px; background: #1a73e8; color: white; text-decoration: none; border-radius: 6px;'>👉 입점 신청 폼 바로가기</a></div>"
        SIGN_HTML = f"<p><b>글로우업리즈 {sender_name} 드림</b></p><img src='cid:biz_card' style='max-width: 400px;'>"
        return {
            "1. [필살기] 커머스(117만)": {"subject": "[글로우업리즈] 117만 유튜버 채널 연계 - 입점 제안", "body": f"<div style='{FONT_STYLE}'>대표님 안녕하세요. {sender_name}입니다.{FORM_LINK}{SIGN_HTML}</div>"},
            "2. [코시] 마케팅 0원": {"subject": "[글로우업리즈] 인플루언서 시딩 0원 - 입점 제안", "body": f"<div style='{FONT_STYLE}'>대표님 안녕하세요. {sender_name}입니다.{FORM_LINK}{SIGN_HTML}</div>"}
        }

    tab_scrape, tab_mail, tab_crm = st.tabs(["🕵️‍♀️ 스토어 메일 수집", "💌 콜드메일 발송", "📊 B2B CRM"])

    with tab_scrape:
        st.subheader("스마트스토어 이메일 수집")
        keyword = st.text_input("검색 키워드 (예: 코스메틱)"); max_p = st.number_input("페이지", 1, 30, 10)
        if st.button("수집 시작", type="primary"):
            df_b = load_brand_db(); existing = set(df_b['Email'].tolist()); new_targets = []
            run = apify_client.actor("apify/google-search-scraper").call(run_input={"queries": f"site:smartstore.naver.com {keyword}", "maxPagesPerQuery": max_p, "resultsPerPage": 20, "countryCode": "kr", "languageCode": "ko"})
            for item in apify_client.dataset(run["defaultDatasetId"]).iterate_items():
                for res in item.get("organicResults", []):
                    sid = re.findall(r"smartstore\.naver\.com/([a-zA-Z0-9_-]+)", res.get("url", ""))
                    if sid:
                        em = f"{sid[0]}@naver.com".lower()
                        if em not in existing: existing.add(em); new_targets.append({"Email": em, "Keyword": keyword, "Discovered_Date": datetime.now().strftime("%Y-%m-%d"), "Last_Sent_Date": "", "Send_Count": 0, "Template_Used": ""})
            if new_targets: df_b = pd.concat([df_b, pd.DataFrame(new_targets)], ignore_index=True); save_brand_db(df_b); st.success(f"{len(new_targets)}개 추가 완료!")
            else: st.warning("새로 발견된 타겟이 없습니다.")

    with tab_mail:
        st.subheader("전략 제휴 메일 발송")
        s_name = st.selectbox("발신자 선택", list(B2B_SENDER_INFO.keys()))
        card_p = B2B_SENDER_INFO[s_name]; t_list = get_email_templates(s_name)
        t_name = st.selectbox("템플릿 선택", list(t_list.keys()))
        
        with st.expander("👀 미리보기"):
            preview_b = t_list[t_name]['body']
            if os.path.exists(card_p): preview_b = preview_b.replace('cid:biz_card', f'data:image/png;base64,{get_image_base64(card_p)}')
            st.components.v1.html(preview_b, height=300, scrolling=True)
            
        s_em = st.text_input("보내는 메일", value=st.secrets.get("SENDER_EMAIL", "rizzsender@gmail.com"), key="b2b_em")
        s_pw = st.text_input("앱 비밀번호", type="password", value=st.secrets.get("SENDER_PW", ""), key="b2b_pw")
        df_b = load_brand_db(); targets = df_b[df_b['Send_Count'] == 0]
        st.write(f"발송 대기: {len(targets)}곳")
        if st.button("🚀 발송 시작", type="primary"):
            if not s_pw or targets.empty: st.error("정보 확인"); st.stop()
            p_bar = st.progress(0); s_cnt = 0
            for i, idx in enumerate(targets.index):
                to_em = df_b.at[idx, 'Email'].strip()
                try:
                    msg = MIMEMultipart('related'); msg['From'], msg['To'], msg['Subject'] = s_em, to_em, Header(t_list[t_name]['subject'], 'utf-8')
                    msg['Reply-To'] = "partner@glowuprizz.com" # 🌟 B2B 답장은 이쪽으로!
                    msg.attach(MIMEText(t_list[t_name]['body'], 'html', 'utf-8'))
                    if os.path.exists(card_p):
                        with open(card_p, "rb") as f:
                            img_data = MIMEImage(f.read()); img_data.add_header('Content-ID', '<biz_card>'); msg.attach(img_data)
                    server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls(); server.login(s_em, s_pw.replace(' ', '')); server.send_message(msg); server.quit()
                    df_b.at[idx, 'Last_Sent_Date'] = datetime.now().strftime("%Y-%m-%d %H:%M"); df_b.at[idx, 'Send_Count'] += 1; save_brand_db(df_b); s_cnt += 1; time.sleep(1.5)
                except Exception as e: st.error(f"{to_em} 실패: {e}")
                p_bar.progress((i + 1) / len(targets))
            st.success("발송 완료!")

    with tab_crm:
        st.subheader("B2B CRM 관리")
        df_crm = load_brand_db(); df_crm.insert(0, '선택', False)
        ed_b2b = st.data_editor(df_crm, column_config={"선택": st.column_config.CheckboxColumn("선택", default=False)}, use_container_width=True, hide_index=True, disabled=[c for c in df_crm.columns if c != '선택'], key="ed_b2b")
        sel_b2b = ed_b2b[ed_b2b['선택'] == True]['Email'].tolist()
        c1, c2 = st.columns(2)
        with c1: st.download_button("📥 CSV 다운로드", ed_b2b.drop(columns=['선택']).to_csv(index=False).encode('utf-8-sig'), "glowup_crm_db.csv", "text/csv")
        with c2: 
            if sel_b2b and st.button(f"🚨 {len(sel_b2b)}곳 삭제", key="del_b2b"):
                df_new = load_brand_db(); df_new = df_new[~df_new['Email'].isin(sel_b2b)]; save_brand_db(df_new); st.rerun()
