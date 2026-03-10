import streamlit as st
import pandas as pd
import re
import time
import sqlite3
import smtplib
import io
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime, timedelta, timezone

import googleapiclient.discovery
import googleapiclient.errors
import google.generativeai as genai

# (기존 크롤링 및 구글시트 모듈 임포트)
from scraper import run_insta_scraper_real, run_blog_search_real, run_metrics_scraper_dummy
from gsheets import GoogleSheetsManager

# --- [1. 보안 및 API 설정] ---
st.set_page_config(page_title="PB 크리에이터 섭외 자동화", layout="wide")

try:
    YOUTUBE_KEY = st.secrets["YOUTUBE_API_KEY"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
    EMAIL_USER = st.secrets["EMAIL_USER"]
    EMAIL_PW = st.secrets["EMAIL_PW"]
    gs = GoogleSheetsManager(st.secrets["gcp_service_account"], st.secrets["google_sheet_name"])
except KeyError as e:
    st.error(f"🚨 보안 설정(.streamlit/secrets.toml)을 확인해주세요. 누락된 키: {e}")
    st.stop()

# API 초기화
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('models/gemini-2.0-flash')
YOUTUBE = googleapiclient.discovery.build('youtube', 'v3', developerKey=YOUTUBE_KEY)

# --- [2. 데이터 및 상수 설정] ---
COUNTRIES = {"대한민국": "KR", "미국": "US", "일본": "JP", "영국": "GB", "베트남": "VN", "태국": "TH", "인도네시아": "ID", "대만": "TW"}
SUB_RANGES = {"전체": (0, 100000000), "1만 미만": (0, 10000), "1만 ~ 5만": (10000, 50000), "5만 ~ 10만": (50000, 100000), "10만 ~ 50만": (100000, 500000), "50만 ~ 100만": (500000, 1000000), "100만 이상": (1000000, 100000000)}

# 💡 동적 템플릿 생성 함수 (MELV, SOLV, UPPR 및 시딩/커머스 대응)
def get_email_template(brand, template_type, channel_name, sender_name):
    if template_type == "시딩 제안용":
        title = f"[{brand} X {channel_name}] 브랜드 협업 제안의 건"
        body = f"""안녕하세요, {channel_name}님!<br>
트렌디한 감성의 브랜드 <b>{brand}</b> 담당자 {sender_name}입니다.<br><br>

평소 {channel_name}님의 매력적이고 유익한 콘텐츠를 즐겨보고 있습니다.<br>
크리에이터님의 채널 분위기가 저희 {brand}의 브랜드 이미지와 매우 잘 부합한다고 생각하여, 제품 협찬(시딩)을 제안 드리고자 연락드렸습니다.<br><br>

제공해 드리는 저희 {brand}의 제품을 경험해 보시고, {channel_name}님만의 감성을 담아 콘텐츠로 소개해주실 수 있을까요?<br>
진행 가능하시다면 긍정적인 회신 부탁드리며, 필요하신 경우 편하게 유선이나 회신으로 문의해 주시면 상세히 안내해 드리겠습니다.<br><br>

감사합니다.<br>
{brand} 담당자 {sender_name} 드림"""
    else: # 커머스 제안용
        title = f"[{brand} X {channel_name}] 커머스/광고 협업 제안의 건"
        body = f"""안녕하세요, {channel_name}님!<br>
라이프스타일 브랜드 <b>{brand}</b> 담당자 {sender_name}입니다.<br><br>

크리에이터님의 영향력과 뛰어난 콘텐츠 기획력에 깊은 인상을 받아, 저희 {brand}와 함께 시너지를 낼 수 있는 커머스(공동구매/광고) 협업을 제안 드립니다.<br><br>

단순한 제품 노출을 넘어, 크리에이터님과 구독자분들 모두에게 좋은 혜택이 될 수 있는 특별한 R/S(수익분배) 형태의 커머스를 기획하고 있습니다.<br>
미팅 요청도 무방하며, 편하게 유선 연락이나 회신 주시면 구체적인 단가 및 진행 방향에 대해 논의하고 싶습니다.<br><br>

감사합니다.<br>
{brand} 담당자 {sender_name} 드림"""
    return title, body

# --- [3. DB 및 상태 관리] ---
if "search_results" not in st.session_state: st.session_state.search_results = None

def init_db():
    conn = sqlite3.connect('mail_log.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS send_log (channel_name TEXT, email TEXT, status TEXT, sent_at TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS api_usage 
                 (id INTEGER PRIMARY KEY, youtube_count INTEGER, ai_count INTEGER, last_reset TEXT)''')
    c.execute("SELECT count(*) FROM api_usage")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO api_usage (id, youtube_count, ai_count, last_reset) VALUES (1, 0, 0, ?)", 
                  (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
    conn.commit()
    conn.close()

init_db()

# --- [4. 핵심 로직 함수들] ---
def get_kst_now(): return datetime.now(timezone.utc) + timedelta(hours=9)

def manage_api_quota(yt_add=0, ai_add=0):
    conn = sqlite3.connect('mail_log.db')
    c = conn.cursor()
    c.execute("SELECT youtube_count, ai_count, last_reset FROM api_usage WHERE id=1")
    row = c.fetchone()
    yt_current, ai_current, last_reset_str = row
    
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

def reset_ai_quota():
    conn = sqlite3.connect('mail_log.db')
    c = conn.cursor()
    c.execute("UPDATE api_usage SET ai_count = 0 WHERE id=1")
    conn.commit()
    conn.close()

def send_custom_mail(receiver_email, subject, body, channel_name, sender_name, image_file=None):
    if not receiver_email or "@" not in receiver_email: return False, "유효하지 않은 이메일"
    
    msg = MIMEMultipart('related')
    msg['Subject'] = subject
    msg['From'] = f"{sender_name} <{EMAIL_USER}>"
    msg['To'] = receiver_email
    msg['Reply-To'] = "hcommerceinc1@gmail.com" # 기획서 상의 지정된 회신용 메일

    html_content = f"""
    <html>
    <body>
        <div style="font-family: Arial, sans-serif; font-size: 14px; color: #333; line-height: 1.6;">
            {body}
        </div>
    """
    if image_file is not None:
        html_content += """
        <br><br>
        <img src="cid:business_card" alt="명함" style="max-width: 400px; height: auto; border: 1px solid #ddd;">
        """
    html_content += "</body></html>"

    msg_alternative = MIMEMultipart('alternative')
    msg.attach(msg_alternative)
    msg_alternative.attach(MIMEText(html_content, 'html', 'utf-8'))

    if image_file is not None:
        try:
            image_file.seek(0)
            img_data = image_file.read()
            image = MIMEImage(img_data)
            image.add_header('Content-ID', '<business_card>')
            image.add_header('Content-Disposition', 'inline', filename='명함.png')
            msg.attach(image)
        except Exception as e:
            return False, f"이미지 처리 오류: {str(e)}"

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_USER, EMAIL_PW)
            server.sendmail(EMAIL_USER, receiver_email, msg.as_string())
        save_log(channel_name, receiver_email, "성공")
        return True, "성공"
    except Exception as e:
        save_log(channel_name, receiver_email, f"실패: {str(e)}")
        return False, str(e)

def save_log(name, email, status):
    conn = sqlite3.connect('mail_log.db')
    c = conn.cursor()
    c.execute("INSERT INTO send_log VALUES (?, ?, ?, ?)", (name, email, status, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit(); conn.close()

def extract_exclude_list(file):
    try:
        df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        return set(df.iloc[:,0].astype(str).str.strip().tolist())
    except: return set()

def extract_email_ai(desc):
    if not desc or len(desc) < 5: return "None"
    try:
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', desc)
        if emails: return emails[0]
        manage_api_quota(ai_add=1)
        response = model.generate_content(f"다음 텍스트에서 이메일 주소만 추출해. 없으면 None: {desc}")
        res = response.text.strip()
        return res if "@" in res else "None"
    except: return "None"

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

def get_recent_ad_videos_ai(up_id, count):
    try:
        manage_api_quota(yt_add=2)
        req = YOUTUBE.playlistItems().list(part="snippet,contentDetails", playlistId=up_id, maxResults=count).execute()
        v_ids = [i['contentDetails']['videoId'] for i in req.get('items', [])]
        v_res = YOUTUBE.videos().list(part="snippet,statistics", id=",".join(v_ids)).execute()
        
        all_videos = []
        ad_indices = []
        patterns = ["유료 광고", "협찬", "광고", "AD", "Paid", "제작 지원", "제품 제공"]
        
        for idx, v in enumerate(v_res.get('items', [])):
            title = v['snippet']['title']
            desc = v['snippet'].get('description', '')
            pub = v['snippet']['publishedAt']
            if (datetime.now() - datetime.strptime(pub, '%Y-%m-%dT%H:%M:%SZ')).days > 365: continue
            
            vid_data = {"영상 제목": title, "업로드": pub[:10], "조회수": int(v['statistics'].get('viewCount',0)), "링크": f"https://youtu.be/{v['id']}"}
            if any(p in title for p in patterns) or any(p in desc for p in patterns):
                ad_indices.append(idx)
            all_videos.append(vid_data)
            
        remaining = [i for i in range(len(all_videos)) if i not in ad_indices]
        if remaining:
            prompt = "".join([f"[{i}] 제목:{all_videos[i]['영상 제목']} / 설명:{v_res['items'][i]['snippet']['description'][:300]}\n" for i in remaining])
            try:
                manage_api_quota(ai_add=1)
                resp = model.generate_content(f"광고/협업이 의심되는 번호만 쉼표로 출력:\n{prompt}")
                ad_indices.extend([int(x) for x in re.findall(r'\d+', resp.text)])
            except: pass
        final_ads = [all_videos[i] for i in sorted(list(set(ad_indices))) if i < len(all_videos)]
        return pd.DataFrame(final_ads)
    except: return pd.DataFrame()

# --- [5. UI 상단 및 사이드바] ---
st.title("🌐 Glowup Rizz 올인원 분석 엔진")
st.markdown("문의 010-8900-6756")
st.divider()

with st.sidebar:
    try: st.image("logo.png", use_container_width=True)
    except: pass
    
    yt_used, ai_used = manage_api_quota()
    st.markdown("### 📊 팀 전체 리소스 현황")
    yt_limit = 500000 
    st.progress(min(yt_used / yt_limit, 1.0))
    st.caption(f"📺 YouTube API: {yt_used:,} / {yt_limit:,} (오늘 5PM 리셋)")
    
    st.markdown("---")
    st.write(f"🤖 **AI API 호출 횟수:** {ai_used:,}회")
    
    if st.checkbox("📋 실시간 발송 로그 보기"):
        try:
            conn = sqlite3.connect('mail_log.db')
            log_df = pd.read_sql_query("SELECT * FROM send_log ORDER BY sent_at DESC", conn)
            log_df.columns = ['채널명', '이메일', '상태', '발송시간']
            st.dataframe(log_df, use_container_width=True, hide_index=True)
            conn.close()
        except: st.write("아직 발송 기록이 없습니다.")
            
    st.markdown("---")
    
    admin_pw = st.text_input("🔓 관리자 모드", type="password")
    try: secret_pw = st.secrets["ADMIN_PASSWORD"]
    except: secret_pw = "rizz"

    if admin_pw == secret_pw:
        st.success("✅ 관리자 인증 완료")
        if st.button("🔄 AI 카운트 리셋 (월초 권장)"):
            reset_ai_quota()
            st.rerun()

# --- [6. 탭 구성] ---
tabs = st.tabs([
    "▶️ 유튜브 상세 검색", "📸 인스타 검색", "🎵 틱톡 검색", "📝 블로그 검색", 
    "🗄️ DB 관리", "✉️ 일반 대량 발송", "📊 성과 업데이트"
])

# ==========================================
# 탭 1: 유튜브 상세 검색
# ==========================================
with tabs[0]:
    with st.form("search"):
        exclude_file = st.file_uploader("제외할 채널 리스트", type=['xlsx', 'csv'])
        kws = st.text_input("검색 키워드 (쉼표 구분)")
        
        c1, c2, c3 = st.columns(3)
        with c1: selected_country = st.selectbox("국가", list(COUNTRIES.keys()))
        with c2: 
            sub_range = st.selectbox("구독자 범위", list(SUB_RANGES.keys()))
            min_subs, max_subs = SUB_RANGES[sub_range]
        with c3: max_res = st.number_input("분석 샘플 수", 5, 50, 20)
        
        c4, c5 = st.columns(2)
        with c4: search_mode = st.radio("검색 방식", ["영상 기반 (추천)", "채널명 기반"], horizontal=True)
        with c5: eff_target = st.slider("최소 효율 (%)", 0, 100, 30) / 100
        
        btn = st.form_submit_button("🚀 분석 시작")

    if btn and kws:
        manage_api_quota(yt_add=100)
        exclude_data = extract_exclude_list(exclude_file) if exclude_file else set()
        keywords = [k.strip() for k in kws.split(",")]
        final_list = []
        processed = set()
        prog = st.progress(0)
        curr = 0; total = len(keywords) * max_res
        
        for kw in keywords:
            try:
                if "영상" in search_mode:
                    search = YOUTUBE.search().list(q=kw, part="snippet", type="video", maxResults=max_res, regionCode=COUNTRIES[selected_country]).execute()
                else:
                    search = YOUTUBE.search().list(q=kw, part="snippet", type="channel", maxResults=max_res, regionCode=COUNTRIES[selected_country]).execute()
                    
                for item in search['items']:
                    curr += 1
                    prog.progress(min(curr/total, 1.0))
                    cid = item['snippet']['channelId']
                    if cid in processed: continue
                    processed.add(cid)
                    
                    ch_res = YOUTUBE.channels().list(part="snippet,statistics,contentDetails", id=cid).execute()
                    if not ch_res['items']: continue
                    ch = ch_res['items'][0]
                    
                    title = ch['snippet']['title']
                    url = f"https://youtube.com/channel/{cid}"
                    if title in exclude_data or url in exclude_data: continue
                    
                    subs = int(ch['statistics'].get('subscriberCount', 0))
                    if not (min_subs <= subs <= max_subs): continue
                    
                    upid = ch['contentDetails']['relatedPlaylists']['uploads']
                    is_ok, avg_v, eff = check_performance(upid, subs)
                    
                    if is_ok and eff >= eff_target:
                        email = extract_email_ai(ch['snippet']['description'])
                        final_list.append({
                            "채널명": title, "구독자": subs, "평균 조회수": int(avg_v), "효율": f"{eff*100:.1f}%",
                            "이메일": email, "프로필": ch['snippet']['thumbnails']['default']['url'],
                            "URL": url, "upload_id": upid
                        })
            except: break
        st.session_state.search_results = pd.DataFrame(final_list)

    if "search_results" in st.session_state and st.session_state.search_results is not None:
        st.subheader("📊 분석 결과 리스트")
        event = st.dataframe(
            st.session_state.search_results,
            column_config={
                "프로필": st.column_config.ImageColumn(),
                "URL": st.column_config.LinkColumn("채널 바로가기", display_text="이동"),
                "upload_id": None
            },
            use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row"
        )

        if event.selection.rows:
            row = st.session_state.search_results.iloc[event.selection.rows[0]]
            st.divider()
            
            st.subheader(f"🔍 '{row['채널명']}' 딥리서치")
            if st.button("광고 이력 분석 시작"):
                with st.spinner("분석 중..."):
                    df = get_recent_ad_videos_ai(row['upload_id'], 20)
                    if not df.empty:
                        st.error(f"🚨 광고 의심 영상 {len(df)}개 발견")
                        st.dataframe(df, column_config={"링크": st.column_config.LinkColumn("영상 바로가기", display_text="시청")}, use_container_width=True)
                    else: st.success("✅ 최근 1년 내 광고 이력 없음")
            
            st.divider()
            
            # 💡 [핵심 변경] 브랜드 및 템플릿 선택 최적화
            st.subheader("📧 섭외 제안서 작성")
            st.write("👤 **발송 담당자 정보 및 템플릿 선택**")
            
            col1, col2, col3 = st.columns(3)
            with col1: sender = st.text_input("담당자 (내 이름)", value="마케터")
            with col2: target_email = st.text_input("수신 이메일", value=row['이메일'])
            with col3: st.text_input("회신 주소", value="hcommerceinc1@gmail.com", disabled=True)
            
            col_b1, col_b2 = st.columns(2)
            with col_b1: brand_select = st.selectbox("진행 브랜드", ["MELV", "SOLV", "UPPR"])
            with col_b2: type_select = st.selectbox("제안 목적", ["커머스 제안용", "시딩 제안용"])
            
            # 동적 템플릿 가져오기
            def_sub, def_body = get_email_template(brand_select, type_select, row['채널명'], sender)
            
            sub_final = st.text_input("제목", value=def_sub)
            body_final = st.text_area("본문 (HTML 가능)", value=def_body, height=350)
            
            # 💡 [핵심 변경] 단일 명함 파일(명함.png) 로드
            final_card_data = None 
            st.markdown("---")
            try:
                with open("명함.png", "rb") as f:
                    final_card_data = f.read()
                st.success("✅ **명함(명함.png)** 파일이 메일 하단에 자동으로 첨부됩니다.")
            except FileNotFoundError:
                st.warning("🚨 깃허브 최상단 경로에 `명함.png` 파일이 없어 텍스트만 발송됩니다. (아래에서 직접 업로드 가능)")
                uploaded_card = st.file_uploader("명함 파일 수동 업로드 (JPG, PNG)", type=['png', 'jpg', 'jpeg'])
                if uploaded_card:
                    final_card_data = uploaded_card.getvalue()

            with st.expander("👀 발송될 이메일 미리보기 (수신자 화면)", expanded=True):
                st.markdown(f"**받는 사람:** {target_email}")
                st.markdown(f"**제목:** {sub_final}")
                st.markdown("---")
                st.markdown(body_final, unsafe_allow_html=True)
                if final_card_data:
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.image(final_card_data, caption="[하단에 첨부될 명함]", width=300)
                else:
                    st.caption("※ 명함 이미지가 없습니다.")
                st.markdown("---")
                
            if st.button("🚀 이메일 전송"):
                if "@" not in target_email:
                    st.error("이메일 주소를 확인해주세요.")
                else:
                    with st.spinner("전송 중..."):
                        image_stream = io.BytesIO(final_card_data) if final_card_data else None
                        ok, msg = send_custom_mail(target_email, sub_final, body_final, row['채널명'], sender, image_stream)
                        if ok: st.success("전송 완료!")
                        else: st.error(f"전송 실패: {msg}")

# ==========================================
# 탭 2: 인스타
# ==========================================
with tabs[1]:
    st.header("📸 인스타 크롤링 (우회 검색 모드)")
    kw = st.text_input("인스타 키워드 (예: 뷰티)")
    if st.button("크롤링 시도"):
        pb = st.progress(0)
        df, err = run_insta_scraper_real(kw, pb)
        st.dataframe(df)

# ==========================================
# 탭 3~7 (기타 기능들)
# ==========================================
with tabs[2]: st.info("틱톡은 셀레니움 연동 후 제공됩니다.")

with tabs[3]:
    st.header("📝 네이버 블로그 검색")
    blog_kw = st.text_input("블로그 키워드")
    if st.button("검색"): st.dataframe(run_blog_search_real(blog_kw))

with tabs[4]:
    st.header("🗄️ 구글 시트 DB 연동")
    st.write("MVP 기획에 명시된 DB 시트 동기화 기능이 들어갈 자리입니다.")

with tabs[5]:
    st.header("✉️ 일반 템플릿 대량 발송")
    st.write("유튜브 상세 검색 탭의 기능 외에 리스트를 불러와 대량 발송을 진행합니다.")

with tabs[6]:
    st.header("📊 구글 시트 성과 수치 업데이트")
    st.write("콘텐츠수치 탭의 업로드 링크를 추적하여 조회수를 업데이트합니다.")
