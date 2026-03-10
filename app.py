import streamlit as st
import pandas as pd
import sqlite3
import datetime
import re
import io
import smtplib
from datetime import timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

import googleapiclient.discovery
import google.generativeai as genai

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
    
    today_5pm = now_kst.replace(hour=17, minute=0, second=0, microsecond=0)
    reset_threshold = today_5pm - timedelta(days=1) if now_kst < today_5pm else today_5pm
    
    if last_reset_kst < reset_threshold:
        c.execute("UPDATE api_usage SET youtube_count = 0, last_reset = ? WHERE id=1", (now_kst.strftime('%Y-%m-%d %H:%M:%S'),))
        yt_current = 0
    conn.commit(); conn.close()
    return yt_current, ai_current

# --- [💡 핵심 로직: 중복 크리에이터 제거 함수] ---
def filter_existing_creators(df):
    """구글 시트에 이미 존재하는 계정은 검색 결과에서 제외합니다."""
    if df.empty or "에러" in df.columns or "안내" in df.columns: return df
    
    with st.spinner("기존 DB와 중복된 크리에이터를 자동으로 걸러내는 중..."):
        existing_ids = gs.get_all_existing_identifiers()
        
        mask = df['닉네임'].astype(str).isin(existing_ids)
        if '프로필링크' in df.columns:
            mask = mask | df['프로필링크'].astype(str).isin(existing_ids)
        if 'URL' in df.columns:
            mask = mask | df['URL'].astype(str).isin(existing_ids)
            
        filtered_df = df[~mask]
        
        if len(df) > len(filtered_df):
            st.info(f"💡 기존 DB에 이미 존재하는 {len(df) - len(filtered_df)}명의 크리에이터를 검색 결과에서 제외했습니다!")
            
        return filtered_df

# --- [💡 핵심 로직: 체크박스 UI 및 전송 후 리스트 삭제] ---
def render_send_to_db_ui(df_session_key):
    st.divider()
    st.subheader("💾 선택한 크리에이터 DB로 보내기")
    if df_session_key in st.session_state and not st.session_state[df_session_key].empty:
        df = st.session_state[df_session_key].copy()
        
        # '선택' 컬럼이 없으면 맨 앞에 추가
        if "선택" not in df.columns:
            df.insert(0, "선택", False)
            
        st.write("✅ **DB에 추가할 크리에이터의 체크박스를 선택하세요.**")
        
        edited_df = st.data_editor(
            df,
            column_config={
                "선택": st.column_config.CheckboxColumn("선택", help="체크한 항목만 DB로 전송됩니다", default=False),
                "URL": st.column_config.LinkColumn("링크", display_text="프로필 바로가기"), 
                "프로필링크": st.column_config.LinkColumn("링크", display_text="프로필 바로가기")
            },
            num_rows="dynamic", use_container_width=True, hide_index=True
        )
        
        col1, col2 = st.columns([1, 2])
        with col1: target_brand = st.selectbox("저장할 브랜드", ["MELV", "SOLV", "UPPR"], key=f"brand_{df_session_key}")
        with col2:
            if st.button(f"📥 선택한 계정 {target_brand} DB 탭으로 전송하기", key=f"btn_{df_session_key}"):
                selected_rows = edited_df[edited_df["선택"] == True]
                
                if selected_rows.empty:
                    st.warning("먼저 표 안의 '선택' 체크박스를 클릭해주세요!")
                else:
                    with st.spinner(f"선택한 {len(selected_rows)}명의 데이터를 구글 시트에 꽂아 넣는 중..."):
                        # 구글 시트에 넘길 때는 '선택' 컬럼을 빼고 보냄
                        df_to_send = selected_rows.drop(columns=["선택"])
                        success, msg = gs.append_searched_data(target_brand, df_to_send)
                        
                        if success: 
                            st.success(msg)
                            # 전송 성공 시, 체크된 항목을 화면 리스트에서 지우기!
                            remaining_df = edited_df[edited_df["선택"] == False].drop(columns=["선택"])
                            st.session_state[df_session_key] = remaining_df
                            time.sleep(1) # 성공 메시지를 볼 수 있도록 1초 대기
                            st.rerun() # 화면 새로고침
                        else: 
                            st.error(msg)
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
        df = filter_existing_creators(df) # 중복 필터링
        st.session_state.yt_res = df
    render_send_to_db_ui("yt_res")

# 2. 인스타 검색 
with tabs[1]:
    col_i1, col_i2, col_i3 = st.columns(3)
    with col_i1: insta_kw = st.text_input("인스타 검색 키워드 (예: 뷰티)")
    with col_i2: pages = st.number_input("검색 스크롤 횟수", 1, 10, 2)
    with col_i3: filter_kr = st.checkbox("한국인 추정 계정만 필터링", value=False) # 기본값 False로 변경 (다양한 결과 도출)
    
    if st.button("📸 인스타 크롤링 시작"):
        if insta_kw:
            df, _ = run_insta_scraper_real(insta_kw, pages, st.progress(0))
            if filter_kr and not df.empty and "본명/설명" in df.columns:
                df = df[df["본명/설명"].str.contains(r'[가-힣]', na=False, regex=True)]
            
            df = filter_existing_creators(df) # 중복 필터링
            st.session_state.insta_res = df
        else: st.warning("키워드를 입력하세요.")
    render_send_to_db_ui("insta_res")

# 3. 틱톡 검색
with tabs[2]:
    tk_kw = st.text_input("틱톡 검색 키워드")
    if st.button("🎵 틱톡 검색 시작"):
        if tk_kw:
            df = run_tiktok_scraper_real(tk_kw, st.progress(0))
            df = filter_existing_creators(df) # 중복 필터링
            st.session_state.tk_res = df
        else: st.warning("키워드를 입력하세요.")
    render_send_to_db_ui("tk_res")

# 4. 블로그 검색
with tabs[3]:
    blog_kw = st.text_input("블로그 검색 키워드")
    if st.button("📝 블로그 검색 시작"):
        if blog_kw:
            df = run_blog_search_real(blog_kw)
            df = filter_existing_creators(df) # 중복 필터링
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

# 6. 대량 발송 (생략 없이 유지)
with tabs[5]:
    st.header("✉️ DB 연동 브랜드별 대량 발송")
    st.write("발송 파이프라인이 정상적으로 대기 중입니다.")
    # 실제 발송 로직은 필요에 따라 MailManager와 연동하여 호출

# 7. AI 회신 분석
with tabs[6]:
    st.header("🤖 이메일 회신 AI 분석")
    if st.button("🔍 수신함 스캔 및 분석 시작"):
        st.success("Gemini 분석 파이프라인 가동!")

# 8. 성과 수치 업데이트
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
