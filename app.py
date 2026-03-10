import streamlit as st
import pandas as pd
import sqlite3
import datetime
from datetime import timedelta, timezone

# 모듈 임포트
from scraper import run_insta_scraper_real, run_tiktok_scraper_real, run_blog_search_real, run_youtube_search_real, run_metrics_scraper_real
from gsheets import GoogleSheetsManager
from mailer_and_ai import MailManager, reset_ai_quota

st.set_page_config(page_title="PB 크리에이터 섭외 자동화", layout="wide")

try:
    YOUTUBE_KEY = st.secrets["YOUTUBE_API_KEY"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
    EMAIL_USER = st.secrets["EMAIL_USER"]
    EMAIL_PW = st.secrets["EMAIL_PW"]
    gs = GoogleSheetsManager(st.secrets["gcp_service_account"], st.secrets["google_sheet_name"])
    mailer = MailManager(EMAIL_USER, EMAIL_PW, GEMINI_KEY)
except KeyError as e:
    st.error(f"🚨 보안 설정 누락: {e}")
    st.stop()

# --- [매일 오후 5시 리셋 로직] ---
def manage_api_quota_5pm():
    conn = sqlite3.connect('mail_log.db')
    c = conn.cursor()
    c.execute("SELECT youtube_count, ai_count, last_reset FROM api_usage WHERE id=1")
    row = c.fetchone()
    yt_current, ai_current, last_reset_str = row
    
    now_kst = datetime.datetime.now(timezone.utc) + timedelta(hours=9)
    last_reset_kst = datetime.datetime.strptime(last_reset_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=9))) if last_reset_str else now_kst
    
    # 오후 5시 (17:00) 기준점
    today_5pm = now_kst.replace(hour=17, minute=0, second=0, microsecond=0)
    reset_threshold = today_5pm - timedelta(days=1) if now_kst < today_5pm else today_5pm
    
    if last_reset_kst < reset_threshold:
        c.execute("UPDATE api_usage SET youtube_count = 0, last_reset = ? WHERE id=1", (now_kst.strftime('%Y-%m-%d %H:%M:%S'),))
        yt_current = 0
    conn.commit(); conn.close()
    return yt_current, ai_current

# --- [공통 DB 전송 UI 렌더링 함수] ---
def render_send_to_db_ui(df_session_key):
    st.divider()
    st.subheader("💾 선택한 크리에이터 DB로 보내기")
    if df_session_key in st.session_state and not st.session_state[df_session_key].empty:
        # 결과를 체크박스 형태로 표시
        edited_df = st.data_editor(
            st.session_state[df_session_key],
            column_config={"프로필링크": st.column_config.LinkColumn("링크", display_text="프로필 바로가기")},
            num_rows="dynamic", use_container_width=True
        )
        
        col1, col2 = st.columns([1, 2])
        with col1: target_brand = st.selectbox("저장할 브랜드", ["MELV", "SOLV", "UPPR"], key=f"brand_{df_session_key}")
        with col2:
            if st.button(f"📥 {target_brand} DB 탭으로 전송하기", key=f"btn_{df_session_key}"):
                with st.spinner("구글 시트에 꽂아 넣는 중..."):
                    success, msg = gs.append_searched_data(target_brand, edited_df)
                    if success: st.success(msg)
                    else: st.error(msg)
    else:
        st.info("먼저 검색을 진행해주세요.")

# --- [사이드바] ---
with st.sidebar:
    try: st.image("logo.png") 
    except: st.markdown("## 🌐 Glowup Rizz")
    st.markdown("**문의 010-8900-6756**")
    
    yt_used, ai_used = manage_api_quota_5pm()
    st.markdown("### 📊 팀 전체 리소스 현황")
    st.progress(min(yt_used / 10000, 1.0))
    st.caption(f"📺 YouTube API: {yt_used:,} / 10,000 (매일 17:00 리셋)")
    st.write(f"🤖 **AI 호출 횟수:** {ai_used:,}회")

# --- [탭 구성] ---
tabs = st.tabs(["▶️ 유튜브 상세 검색", "📸 인스타 검색", "🎵 틱톡 검색", "📝 블로그 검색", "🗄️ 구글 시트 DB 관리", "✉️ 대량 발송", "🤖 AI 회신 분석", "📊 성과 업데이트"])

# 1. 유튜브 검색
with tabs[0]:
    kw = st.text_input("유튜브 검색 키워드")
    if st.button("유튜브 검색"):
        df = run_youtube_search_real(kw, YOUTUBE_KEY)
        st.session_state.yt_res = df
    render_send_to_db_ui("yt_res")

# 2. 인스타 검색 (페이지수 지정 및 한국인 필터)
with tabs[1]:
    col_i1, col_i2, col_i3 = st.columns(3)
    with col_i1: insta_kw = st.text_input("인스타 검색 키워드 (예: 뷰티)")
    with col_i2: pages = st.number_input("검색 스크롤 횟수", 1, 10, 2)
    with col_i3: filter_kr = st.checkbox("한국인 추정 계정만 필터링", value=True)
    
    if st.button("📸 인스타 크롤링 시작"):
        if insta_kw:
            df, _ = run_insta_scraper_real(insta_kw, pages, st.progress(0))
            if filter_kr and not df.empty and "본명/설명" in df.columns:
                df = df[df["본명/설명"].str.contains(r'[가-힣]', na=False, regex=True)]
            st.session_state.insta_res = df
        else: st.warning("키워드를 입력하세요.")
    render_send_to_db_ui("insta_res")

# 3. 틱톡 검색 (셀레니움 연동됨)
with tabs[2]:
    tk_kw = st.text_input("틱톡 검색 키워드")
    if st.button("🎵 틱톡 검색 시작"):
        if tk_kw:
            df = run_tiktok_scraper_real(tk_kw, st.progress(0))
            st.session_state.tk_res = df
        else: st.warning("키워드를 입력하세요.")
    render_send_to_db_ui("tk_res")

# 4. 블로그 검색
with tabs[3]:
    blog_kw = st.text_input("블로그 검색 키워드")
    if st.button("📝 블로그 검색 시작"):
        if blog_kw:
            df = run_blog_search_real(blog_kw)
            st.session_state.blog_res = df
    render_send_to_db_ui("blog_res")

# 5. DB 관리 (불러오기 -> 수정 -> 최종 연동)
with tabs[4]:
    st.header("🗄️ 구글 시트 DB 관리")
    st.write("구글 시트에 저장된 데이터를 불러와 직접 수정/삭제한 뒤, [최종 연동]을 눌러 안전하게 시트를 업데이트합니다.")
    db_brand = st.selectbox("관리할 브랜드 탭 선택", ["MELV", "SOLV", "UPPR"])
    
    if st.button(f"📥 {db_brand} 시트 데이터 불러오기"):
        records = gs.get_all_records(db_brand)
        if records:
            st.session_state.current_db = pd.DataFrame(records)
            st.success("데이터를 성공적으로 불러왔습니다!")
        else:
            st.warning("데이터가 없거나 시트를 불러오지 못했습니다.")
            st.session_state.current_db = pd.DataFrame()
            
    if 'current_db' in st.session_state and not st.session_state.current_db.empty:
        # 링크 컬럼은 바로가기로 렌더링
        edited_df = st.data_editor(
            st.session_state.current_db, num_rows="dynamic", use_container_width=True,
            column_config={
                "인스타그램 계정": st.column_config.LinkColumn(display_text="바로가기"),
                "틱톡 계정": st.column_config.LinkColumn(display_text="바로가기"),
                "블로그 계정": st.column_config.LinkColumn(display_text="바로가기")
            }
        )
        if st.button("💾 수정된 내용을 구글 시트에 최종 연동 (덮어쓰기)", type="primary"):
            with st.spinner("구글 시트 업데이트 중..."):
                success, msg = gs.overwrite_sheet(db_brand, edited_df)
                if success: st.success(msg)
                else: st.error(msg)

# 6. 대량 발송
with tabs[5]:
    st.header("✉️ DB 연동 브랜드별 대량 발송")
    col_m1, col_m2 = st.columns(2)
    with col_m1: send_brand = st.selectbox("발송 브랜드", ["MELV", "SOLV", "UPPR"])
    with col_m2: send_type = st.selectbox("템플릿", ["커머스 제안용", "시딩 제안용"])
    
    if st.button(f"📥 {send_brand} 시트에서 이메일 리스트 불러오기"):
        records = gs.get_all_records(send_brand)
        st.session_state.email_list = list(set([str(r.get('이메일', '')).strip() for r in records if str(r.get('이메일', '')).strip()]))
        st.success(f"이메일 {len(st.session_state.email_list)}개 로드 완료!")
        
    target_emails = st.multiselect("발송 대상 선택", st.session_state.get('email_list', []))
    if st.button("🚀 선택한 대상에게 전송", type="primary"):
        st.success("발송 파이프라인 가동! (실제 발송 로직 연동)")

# 7. AI 회신 분석
with tabs[6]:
    st.header("🤖 이메일 회신 AI 분석")
    if st.button("🔍 수신함 스캔 및 분석 시작"):
        st.success("Gemini 분석 파이프라인 가동!")

# 8. 성과 수치 업데이트 (셀레니움 실제 방문)
with tabs[7]:
    st.header("📊 구글 시트 성과 수치 업데이트")
    st.write("각 콘텐츠수치 탭의 G열(업로드 시 링크)에 셀레니움 봇이 직접 방문하여 좋아요, 조회수를 긁어옵니다.")
    metrics_brand = st.selectbox("업데이트할 브랜드", ["MELV", "SOLV", "UPPR"])
    
    if st.button(f"🚀 {metrics_brand}콘텐츠수치 업데이트"):
        if not gs.spreadsheet:
            st.error(f"🚨 구글 시트 연결 오류: {gs.error_msg}")
        else:
            with st.spinner("가상 브라우저가 링크들을 하나씩 방문하며 수치를 긁어오는 중입니다... (시간 소요)"):
                result_msg = gs.update_content_metrics(metrics_brand, run_metrics_scraper_real)
                st.success(result_msg)
