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
import google.generativeai as genai

from scraper import run_insta_scraper_real, run_blog_search_real, run_metrics_scraper_dummy
from gsheets import GoogleSheetsManager
from mailer_and_ai import MailManager

# --- [1. 보안 및 API 설정] ---
st.set_page_config(page_title="PB 크리에이터 섭외 자동화", layout="wide")

try:
    YOUTUBE_KEY = st.secrets["YOUTUBE_API_KEY"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
    EMAIL_USER = st.secrets["EMAIL_USER"]
    EMAIL_PW = st.secrets["EMAIL_PW"]
    gs = GoogleSheetsManager(st.secrets["gcp_service_account"], st.secrets["google_sheet_name"])
    mailer = MailManager(EMAIL_USER, EMAIL_PW, GEMINI_KEY)
except KeyError as e:
    st.error(f"🚨 보안 설정(.streamlit/secrets.toml)을 확인해주세요. 누락된 키: {e}")
    st.stop()

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('models/gemini-2.0-flash')
YOUTUBE = googleapiclient.discovery.build('youtube', 'v3', developerKey=YOUTUBE_KEY)

# --- [2. 데이터 및 상수 설정] ---
COUNTRIES = {"대한민국": "KR", "미국": "US", "일본": "JP", "영국": "GB"}
SUB_RANGES = {"전체": (0, 100000000), "1만 미만": (0, 10000), "1만 ~ 5만": (10000, 50000), "5만 ~ 10만": (50000, 100000), "10만 이상": (100000, 100000000)}

def get_email_template(brand, template_type, channel_name, sender_name):
    if template_type == "시딩 제안용":
        title = f"[{brand} X {channel_name}] 브랜드 협업 제안의 건"
        body = f"안녕하세요, {channel_name}님!<br>트렌디한 감성의 브랜드 <b>{brand}</b> 담당자 {sender_name}입니다.<br><br>평소 {channel_name}님의 매력적이고 유익한 콘텐츠를 즐겨보고 있습니다.<br>크리에이터님의 채널 분위기가 저희 {brand}의 브랜드 이미지와 매우 잘 부합한다고 생각하여, 제품 협찬(시딩)을 제안 드리고자 연락드렸습니다.<br><br>제공해 드리는 저희 {brand}의 제품을 경험해 보시고, {channel_name}님만의 감성을 담아 콘텐츠로 소개해주실 수 있을까요?<br>진행 가능하시다면 긍정적인 회신 부탁드리며, 필요하신 경우 편하게 유선이나 회신으로 문의해 주시면 상세히 안내해 드리겠습니다.<br><br>감사합니다.<br>{brand} 담당자 {sender_name} 드림"
    else: 
        title = f"[{brand} X {channel_name}] 커머스/광고 협업 제안의 건"
        body = f"안녕하세요, {channel_name}님!<br>라이프스타일 브랜드 <b>{brand}</b> 담당자 {sender_name}입니다.<br><br>크리에이터님의 영향력과 뛰어난 콘텐츠 기획력에 깊은 인상을 받아, 저희 {brand}와 함께 시너지를 낼 수 있는 커머스(공동구매/광고) 협업을 제안 드립니다.<br><br>단순한 제품 노출을 넘어, 크리에이터님과 구독자분들 모두에게 좋은 혜택이 될 수 있는 특별한 R/S(수익분배) 형태의 커머스를 기획하고 있습니다.<br>미팅 요청도 무방하며, 편하게 유선 연락이나 회신 주시면 구체적인 단가 및 진행 방향에 대해 논의하고 싶습니다.<br><br>감사합니다.<br>{brand} 담당자 {sender_name} 드림"
    return title, body

# --- [3. DB 및 상태 관리] ---
if "search_results" not in st.session_state: st.session_state.search_results = None

def init_db():
    conn = sqlite3.connect('mail_log.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS send_log (channel_name TEXT, email TEXT, status TEXT, sent_at TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS api_usage (id INTEGER PRIMARY KEY, youtube_count INTEGER, ai_count INTEGER, last_reset TEXT)')
    c.execute("SELECT count(*) FROM api_usage")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO api_usage (id, youtube_count, ai_count, last_reset) VALUES (1, 0, 0, ?)", (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
    conn.commit()
    conn.close()

init_db()

# --- [4. 핵심 로직 (5AM 리셋 적용)] ---
def get_kst_now(): return datetime.now(timezone.utc) + timedelta(hours=9)

def manage_api_quota(yt_add=0, ai_add=0):
    conn = sqlite3.connect('mail_log.db')
    c = conn.cursor()
    c.execute("SELECT youtube_count, ai_count, last_reset FROM api_usage WHERE id=1")
    yt_current, ai_current, last_reset_str = c.fetchone()
    
    now_kst = get_kst_now()
    last_reset_kst = datetime.strptime(last_reset_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=9))) if last_reset_str else now_kst
    
    # 매일 오전 5시 리셋 로직
    today_5am = now_kst.replace(hour=5, minute=0, second=0, microsecond=0)
    reset_threshold = today_5am - timedelta(days=1) if now_kst < today_5am else today_5am
    
    if last_reset_kst < reset_threshold:
        yt_current = 0
        c.execute("UPDATE api_usage SET youtube_count = 0, last_reset = ? WHERE id=1", (now_kst.strftime('%Y-%m-%d %H:%M:%S'),))
        
    if yt_add > 0 or ai_add > 0:
        c.execute("UPDATE api_usage SET youtube_count = youtube_count + ?, ai_count = ai_count + ? WHERE id=1", (yt_add, ai_add))
        yt_current += yt_add; ai_current += ai_add
    conn.commit(); conn.close()
    return yt_current, ai_current

def reset_ai_quota():
    conn = sqlite3.connect('mail_log.db')
    c = conn.cursor()
    c.execute("UPDATE api_usage SET ai_count = 0 WHERE id=1")
    conn.commit(); conn.close()

def send_custom_mail(receiver_email, subject, body, channel_name, sender_name, image_file=None):
    if not receiver_email or "@" not in receiver_email: return False, "유효하지 않은 이메일"
    msg = MIMEMultipart('related')
    msg['Subject'] = subject; msg['From'] = f"{sender_name} <{EMAIL_USER}>"
    msg['To'] = receiver_email; msg['Reply-To'] = "hcommerceinc1@gmail.com"
    html_content = f"<html><body><div style='font-family: Arial, sans-serif; font-size: 14px; color: #333; line-height: 1.6;'>{body}</div>"
    if image_file is not None: html_content += "<br><br><img src='cid:business_card' alt='명함' style='max-width: 400px; height: auto; border: 1px solid #ddd;'>"
    html_content += "</body></html>"
    msg_alternative = MIMEMultipart('alternative'); msg.attach(msg_alternative); msg_alternative.attach(MIMEText(html_content, 'html', 'utf-8'))
    if image_file is not None:
        try:
            image_file.seek(0)
            image = MIMEImage(image_file.read())
            image.add_header('Content-ID', '<business_card>')
            image.add_header('Content-Disposition', 'inline', filename='명함.png')
            msg.attach(image)
        except Exception as e: return False, f"이미지 오류: {e}"
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_USER, EMAIL_PW); server.sendmail(EMAIL_USER, receiver_email, msg.as_string())
        save_log(channel_name, receiver_email, "성공")
        return True, "성공"
    except Exception as e:
        save_log(channel_name, receiver_email, f"실패: {e}"); return False, str(e)

def save_log(name, email, status):
    conn = sqlite3.connect('mail_log.db'); c = conn.cursor()
    c.execute("INSERT INTO send_log VALUES (?, ?, ?, ?)", (name, email, status, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit(); conn.close()

def extract_exclude_list(file):
    try: return set((pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)).iloc[:,0].astype(str).str.strip().tolist())
    except: return set()

def extract_email_ai(desc):
    if not desc or len(desc) < 5: return "None"
    try:
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', desc)
        if emails: return emails[0]
        manage_api_quota(ai_add=1); res = model.generate_content(f"이메일 추출: {desc}").text.strip()
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
        return True, avg_v, (avg_v / subs if subs > 0 else 0)
    except: return False, 0, 0

def get_recent_ad_videos_ai(up_id, count):
    try:
        manage_api_quota(yt_add=2)
        req = YOUTUBE.playlistItems().list(part="snippet,contentDetails", playlistId=up_id, maxResults=count).execute()
        v_ids = [i['contentDetails']['videoId'] for i in req.get('items', [])]
        v_res = YOUTUBE.videos().list(part="snippet,statistics", id=",".join(v_ids)).execute()
        all_videos, ad_indices, patterns = [], [], ["유료 광고", "협찬", "광고", "AD", "Paid", "제작 지원", "제품 제공"]
        for idx, v in enumerate(v_res.get('items', [])):
            title, desc, pub = v['snippet']['title'], v['snippet'].get('description', ''), v['snippet']['publishedAt']
            if (datetime.now() - datetime.strptime(pub, '%Y-%m-%dT%H:%M:%SZ')).days > 365: continue
            all_videos.append({"영상 제목": title, "업로드": pub[:10], "조회수": int(v['statistics'].get('viewCount',0)), "링크": f"https://youtu.be/{v['id']}"})
            if any(p in title for p in patterns) or any(p in desc for p in patterns): ad_indices.append(idx)
        remaining = [i for i in range(len(all_videos)) if i not in ad_indices]
        if remaining:
            prompt = "".join([f"[{i}] 제목:{all_videos[i]['영상 제목']} / 설명:{v_res['items'][i]['snippet']['description'][:300]}\n" for i in remaining])
            try: manage_api_quota(ai_add=1); ad_indices.extend([int(x) for x in re.findall(r'\d+', model.generate_content(f"광고의심 번호 추출:\n{prompt}").text)])
            except: pass
        return pd.DataFrame([all_videos[i] for i in sorted(list(set(ad_indices))) if i < len(all_videos)])
    except: return pd.DataFrame()

# --- [5. UI 상단 및 사이드바] ---
st.title("🌐 Glowup Rizz 올인원 분석 엔진")
st.markdown("**문의 010-8900-6756**")
st.divider()

with st.sidebar:
    try: st.image("logo.png", use_container_width=True) # 로고를 상단에 배치
    except: pass
    
    yt_used, ai_used = manage_api_quota()
    st.markdown("### 📊 팀 전체 리소스 현황")
    st.progress(min(yt_used / 10000, 1.0))
    st.caption(f"📺 YouTube API: {yt_used:,} / 10,000 (매일 오전 5시 리셋)")
    st.write(f"🤖 **AI API 호출 횟수:** {ai_used:,}회")
    
    if st.checkbox("📋 실시간 발송 로그 보기"):
        try: st.dataframe(pd.read_sql_query("SELECT * FROM send_log ORDER BY sent_at DESC", sqlite3.connect('mail_log.db')).rename(columns={'channel_name':'채널명', 'email':'이메일', 'status':'상태', 'sent_at':'발송시간'}), hide_index=True)
        except: st.write("발송 기록 없음")
    
    if st.text_input("🔓 관리자 모드", type="password") == st.secrets.get("ADMIN_PASSWORD", "rizz"):
        st.success("✅ 관리자 인증 완료")
        if st.button("🔄 AI 카운트 리셋"): reset_ai_quota(); st.rerun()

# --- [6. 탭 구성 (요청하신 순서 및 이름 적용)] ---
tabs = st.tabs([
    "▶️ 유튜브 상세 검색", "📸 인스타 검색", "🎵 틱톡 검색", "📝 블로그 검색", 
    "🗄️ DB 관리", "✉️ 대량 발송", "🤖 AI 회신 분석", "📊 성과 업데이트"
])

# [탭 1: 유튜브 상세 검색]
with tabs[0]:
    with st.form("search"):
        exclude_file = st.file_uploader("제외할 채널 리스트", type=['xlsx', 'csv'])
        kws = st.text_input("검색 키워드 (쉼표 구분)")
        c1, c2, c3 = st.columns(3)
        with c1: selected_country = st.selectbox("국가", list(COUNTRIES.keys()))
        with c2: sub_range = st.selectbox("구독자 범위", list(SUB_RANGES.keys())); min_subs, max_subs = SUB_RANGES[sub_range]
        with c3: max_res = st.number_input("분석 샘플 수", 5, 50, 20)
        c4, c5 = st.columns(2)
        with c4: search_mode = st.radio("검색 방식", ["영상 기반 (추천)", "채널명 기반"], horizontal=True)
        with c5: eff_target = st.slider("최소 효율 (%)", 0, 100, 30) / 100
        btn = st.form_submit_button("🚀 분석 시작")

    if btn and kws:
        manage_api_quota(yt_add=100)
        exclude_data = extract_exclude_list(exclude_file) if exclude_file else set()
        final_list, processed, prog, curr, total = [], set(), st.progress(0), 0, len(kws.split(",")) * max_res
        
        for kw in [k.strip() for k in kws.split(",")]:
            try:
                search = YOUTUBE.search().list(q=kw, part="snippet", type="video" if "영상" in search_mode else "channel", maxResults=max_res, regionCode=COUNTRIES[selected_country]).execute()
                for item in search['items']:
                    curr += 1; prog.progress(min(curr/total, 1.0))
                    cid = item['snippet']['channelId']
                    if cid in processed: continue
                    processed.add(cid)
                    
                    ch_res = YOUTUBE.channels().list(part="snippet,statistics,contentDetails", id=cid).execute()
                    if not ch_res['items']: continue
                    ch = ch_res['items'][0]; title, url = ch['snippet']['title'], f"https://youtube.com/channel/{cid}"
                    if title in exclude_data or url in exclude_data: continue
                    
                    subs = int(ch['statistics'].get('subscriberCount', 0))
                    if not (min_subs <= subs <= max_subs): continue
                    
                    upid = ch['contentDetails']['relatedPlaylists']['uploads']
                    is_ok, avg_v, eff = check_performance(upid, subs)
                    if is_ok and eff >= eff_target:
                        final_list.append({"채널명": title, "구독자": subs, "평균 조회수": int(avg_v), "효율": f"{eff*100:.1f}%", "이메일": extract_email_ai(ch['snippet']['description']), "프로필": ch['snippet']['thumbnails']['default']['url'], "URL": url, "upload_id": upid})
            except: break
        st.session_state.search_results = pd.DataFrame(final_list)

    if st.session_state.search_results is not None:
        st.subheader("📊 분석 결과 리스트")
        event = st.dataframe(st.session_state.search_results, column_config={"프로필": st.column_config.ImageColumn(), "URL": st.column_config.LinkColumn("바로가기", display_text="이동"), "upload_id": None}, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")

# [탭 2: 인스타 검색] - 키워드 먼저, 버튼 나중에 배치
with tabs[1]:
    st.header("📸 인스타 크롤링")
    insta_kw = st.text_input("인스타 검색 키워드 (예: 뷰티)")
    if st.button("크롤링 시작", key="insta_btn"):
        if insta_kw:
            df, err = run_insta_scraper_real(insta_kw, st.progress(0))
            st.dataframe(df)
        else:
            st.warning("키워드를 먼저 입력해주세요.")

# [탭 3: 틱톡 검색] - 심플한 문구 적용
with tabs[2]: 
    st.header("🎵 틱톡 검색")
    st.info("틱톡은 셀레니움 연동 후 제공됩니다.")

# [탭 4: 블로그 검색] - 키워드 먼저 배치
with tabs[3]:
    st.header("📝 네이버 블로그 검색")
    blog_kw = st.text_input("블로그 검색 키워드 (예: 화장품 리뷰)")
    if st.button("블로그 검색 시작", key="blog_btn"):
        if blog_kw:
            st.dataframe(run_blog_search_real(blog_kw))
        else:
            st.warning("키워드를 먼저 입력해주세요.")

# [탭 5: DB 관리] - 조회 -> 수정 -> 구글 시트 덮어쓰기 파이프라인
with tabs[4]:
    st.header("🗄️ 구글 시트 DB 관리")
    st.write("구글 시트에 저장된 데이터를 불러와 직접 수정/삭제한 뒤, [최종 연동]을 눌러 안전하게 시트를 업데이트합니다.")
    
    db_brand = st.selectbox("관리할 브랜드 탭 선택", ["MELV", "SOLV", "UPPR"])
    if st.button(f"📥 {db_brand} 시트 데이터 불러오기"):
        records = gs.get_all_records(db_brand)
        if records:
            st.session_state.current_db = pd.DataFrame(records)
            st.success("데이터를 성공적으로 불러왔습니다! 아래 표에서 바로 수정하세요.")
        else:
            st.warning("데이터가 없거나 시트를 불러오지 못했습니다.")
            st.session_state.current_db = pd.DataFrame() # 빈 데이터프레임 초기화
            
    if 'current_db' in st.session_state and not st.session_state.current_db.empty:
        # num_rows="dynamic" 옵션으로 행 추가/삭제 기능 지원
        edited_df = st.data_editor(st.session_state.current_db, num_rows="dynamic", use_container_width=True)
        
        if st.button("💾 수정된 내용을 구글 시트에 최종 연동 (덮어쓰기)"):
            with st.spinner("구글 시트 업데이트 중..."):
                success, msg = gs.overwrite_sheet(db_brand, edited_df)
                if success: st.success(msg)
                else: st.error(msg)

# [탭 6: 대량 발송] - 시트 연동 + 바로 발송
with tabs[5]:
    st.header("✉️ DB 연동 브랜드별 대량 발송")
    col1, col2 = st.columns(2)
    with col1: send_brand = st.selectbox("발송 브랜드", ["MELV", "SOLV", "UPPR"], key="send_b")
    with col2: send_type = st.selectbox("템플릿", ["커머스 제안용", "시딩 제안용"], key="send_t")
    
    sender_name = st.text_input("마케터 이름 (내 이름)", "마케터", key="send_n")
    
    st.write(f"**{send_brand}** 시트에서 이메일 목록을 불러옵니다.")
    if st.button(f"📥 {send_brand} 이메일 리스트 불러오기"):
        records = gs.get_all_records(send_brand)
        if records:
            emails = [str(r.get('이메일', '')).strip() for r in records if str(r.get('이메일', '')).strip()]
            st.session_state.email_list = list(set(emails)) # 중복 제거
            st.success(f"총 {len(st.session_state.email_list)}개의 이메일을 불러왔습니다.")
        else:
            st.warning("이메일 목록을 찾을 수 없습니다.")
            st.session_state.email_list = []
            
    target_emails = st.multiselect("발송할 대상 선택 (개별/전체 선택 가능)", st.session_state.get('email_list', []))
    
    st.divider()
    def_sub, def_body = get_email_template(send_brand, send_type, "[인플루언서 이름]", sender_name)
    with st.expander("👀 발송될 템플릿 미리보기 (명함 자동 첨부)", expanded=True):
        st.markdown(f"**제목:** {def_sub}\n\n---")
        st.markdown(def_body, unsafe_allow_html=True)
        st.caption("📎 메일 하단에 '명함.png'가 첨부됩니다.")
        
    if st.button("🚀 선택한 대상에게 일괄 전송", type="primary"):
        if not target_emails:
            st.error("발송할 이메일을 선택해주세요.")
        else:
            with st.spinner("메일 발송 중... (최대 수십 초 소요)"):
                try:
                    with open("명함.png", "rb") as f: card_data = f.read()
                except: card_data = None
                
                success_count = 0
                for email_addr in target_emails:
                    ok, msg = send_custom_mail(email_addr, def_sub.replace("[인플루언서 이름]", "크리에이터"), def_body.replace("[인플루언서 이름]", "크리에이터"), "대량발송", sender_name, io.BytesIO(card_data) if card_data else None)
                    if ok: success_count += 1
                st.success(f"✅ 총 {success_count}/{len(target_emails)}건 발송 성공!")

# [탭 7: AI 회신 분석]
with tabs[6]:
    st.header("🤖 이메일 회신 AI 분석")
    st.write("`rizzsender@gmail.com` 수신함의 안 읽은 메일을 분석합니다.")
    if st.button("🔍 수신함 스캔 및 분석 시작", type="primary"):
        with st.spinner("Gemini가 메일을 분석 중입니다..."):
            success, msg, ai_results = mailer.check_replies_and_analyze()
            if success:
                st.success(msg)
                if ai_results: st.dataframe(pd.DataFrame(ai_results))
            else: st.error(msg)

# [탭 8: 성과 업데이트] - 에러 핸들링 강화
with tabs[7]:
    st.header("📊 구글 시트 성과 수치 업데이트")
    metrics_brand = st.selectbox("업데이트할 브랜드", ["MELV", "SOLV", "UPPR"])
    if st.button(f"🚀 {metrics_brand}콘텐츠수치 업데이트"):
        if not gs.spreadsheet:
            # 💡 [핵심] 연결 에러의 원인을 화면에 명확하게 붉은 글로 노출
            st.error(f"🚨 구글 시트 연결 오류: {gs.error_msg}\n\n[해결방법]\n1. Secrets의 'google_sheet_name'이 실제 구글 시트 파일명과 똑같은지 확인하세요.\n2. 서비스 계정 이메일(client_email)을 구글 시트 우측 상단 '공유'에 넣고 '편집자' 권한을 주셨는지 확인하세요.")
        else:
            with st.spinner("수치를 긁어오는 중..."):
                st.success(gs.update_content_metrics(metrics_brand, run_metrics_scraper_dummy))
