import streamlit as st
import pandas as pd
import time
from scraper import run_insta_scraper_real, run_youtube_search_real, run_blog_search_real, run_metrics_scraper_dummy
from gsheets import GoogleSheetsManager
from mailer_and_ai import MailManager

# --- [페이지 기본 설정] ---
st.set_page_config(page_title="PB 시딩 자동화", layout="wide")

# --- [보안(Secrets) 정보 불러오기] ---
# 수신용 비밀번호를 따로 받지 않고, 발송용(email_sender) 계정 하나로 통합 처리합니다.
gs = GoogleSheetsManager(st.secrets["gcp_service_account"], st.secrets["google_sheet_name"])
mailer = MailManager(
    st.secrets["email_sender"],      # rizzsender@gmail.com
    st.secrets["email_password"],    # rizzsender의 16자리 앱 비밀번호
    st.secrets["gemini_api_key"]     # Gemini API 키
)

# --- [상단 헤더 및 사이드바] ---
st.title("🚀 PB 인플루언서 시딩 자동화 올인원 솔루션")
st.caption("✔️기능: 맞춤형 크롤링 | 통합 DB 관리 | 타겟 메일 대량 발송 | Gemini AI 회신 자동 분석 | 콘텐츠 성과 추적")
st.markdown("**문의:** 010-8900-6756")
st.divider()

with st.sidebar:
    st.header("⚙️ 관리자 모드")
    st.subheader("API 사용량 관리")
    st.progress(15, text="YouTube API (15/10000)")
    st.progress(5, text="Gemini API (5/1500)")
    st.caption("※ API는 각 서비스별 리셋 시간에 초기화됩니다.")

# --- [8개의 탭 구성] ---
tabs = st.tabs([
    "📸 인스타 검색", "🎵 틱톡 검색", "▶️ 유튜브 검색", "📝 블로그 검색", 
    "🗄️ DB 관리", "✉️ 메일 대량 발송", "🤖 AI 회신 분석", "📊 성과 수치 업데이트"
])

# ==========================================
# 탭 1: 인스타 인플루언서 크롤링
# ==========================================
with tabs[0]:
    st.header("📸 인스타 인플루언서 크롤링 (Dummy)")
    col1, col2, col3 = st.columns(3)
    with col1:
        kw = st.text_input("검색 키워드 (해시태그, 카테고리)")
        nationality = st.radio("국적 필터", ["전체", "한국인 찾기", "외국인 찾기"], horizontal=True)
    with col2:
        follower_filter = st.selectbox("팔로워 수 필터", ["전체", "5만 이하 (시딩 제안)", "5만~10만", "10만 이상 (커머스)"])
    with col3:
        view_eff = st.slider("조회수 효율 (%)", 0, 300, 50)

    if st.button("🔍 봇 크롤링 시작", type="primary", key="btn_insta"):
        progress_bar = st.progress(0, "크롤링 중...")
        df_result, failed_links = run_insta_scraper_real(kw, progress_bar)
        st.session_state.temp_crawled_data = df_result 
        
        st.subheader("결과 미리보기 표")
        st.dataframe(df_result)
        if failed_links:
            st.warning(f"⚠️ 크롤링 실패 링크: {', '.join(failed_links)} (비공개 또는 삭제됨)")

    st.divider()
    st.subheader("💾 구글 시트 DB에 저장하기")
    target_brand = st.selectbox("저장할 브랜드 시트 선택", ["MELV", "SOLV", "UPPR"], key="brand_insta")
    
    if st.button(f"{target_brand} 탭에 크롤링 결과 업데이트", key="save_insta"):
        if 'temp_crawled_data' in st.session_state:
            # 예시로 첫 번째 행만 시트에 넣습니다. (전체 적용 시 for문 사용)
            row = st.session_state.temp_crawled_data.iloc[0]
            influencer_data = {
                "닉네임": row.get("닉네임", ""), 
                "인스타": row.get("프로필링크", ""), 
                "이메일": row.get("이메일", "")
            }
            success, msg = gs.insert_influencer_to_brand(target_brand, influencer_data)
            if success:
                st.success(msg)
            else:
                st.error(f"❌ 실패 원인: {msg}")
        else:
            st.warning("먼저 크롤링을 진행해주세요.")

# ==========================================
# 탭 2: 틱톡 검색
# ==========================================
with tabs[1]:
    st.header("🎵 틱톡 크롤링")
    st.info("틱톡은 인스타와 동일한 셀레니움 기반 로직이 필요하여 현재 MVP에서는 뼈대만 제공됩니다.")

# ==========================================
# 탭 3: 유튜브 검색 (Real API)
# ==========================================
with tabs[2]:
    st.header("▶️ 유튜브 인플루언서 크롤링 (Real API)")
    yt_kw = st.text_input("유튜브 검색어 (예: 뷰티 유튜버)")
    min_views = st.number_input("최소 조회수 필터", value=10000)
    
    if st.button("유튜브 API 검색 시작", type="primary"):
        with st.spinner("구글 서버에서 데이터를 가져오고 있습니다..."):
            yt_df = run_youtube_search_real(yt_kw, st.secrets["youtube_api_key"], min_views)
            st.dataframe(yt_df)

# ==========================================
# 탭 4: 블로그 검색 (Real Scraping)
# ==========================================
with tabs[3]:
    st.header("📝 블로그 인플루언서 크롤링 (Real Scraping)")
    blog_kw = st.text_input("블로그 검색어 (예: 화장품 리뷰)")
    if st.button("네이버 블로그 검색", type="primary"):
        with st.spinner("블로그 글을 수집 중입니다..."):
            blog_df = run_blog_search_real(blog_kw)
            st.dataframe(blog_df)

# ==========================================
# 탭 5: DB 관리
# ==========================================
with tabs[4]:
    st.header("🗄️ 통합 DB 관리")
    st.write("구글 시트에 저장된 데이터를 한눈에 봅니다.")
    if st.button("🔄 최신 시트 데이터 동기화"):
        st.info("실제 배포 시: 구글 시트의 전체 데이터를 읽어와 아래 표에 띄워줍니다.")
    
    # 임시 표 노출
    dummy_db = pd.DataFrame({
        "브랜드": ["MELV", "SOLV"], "닉네임": ["테스터A", "테스터B"], 
        "이메일": ["test1@gmail.com", "test2@naver.com"], "회신현황": ["", "YES"]
    })
    st.data_editor(dummy_db, use_container_width=True)

# ==========================================
# 탭 6: 자동 대량 메일 전송
# ==========================================
with tabs[5]:
    st.header("✉️ 자동 대량 메일 전송")
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        brand = st.selectbox("진행할 브랜드 선택", ["MELV", "SOLV", "UPPR"])
    with col_m2:
        template = st.selectbox("이메일 템플릿", ["커머스 제안용", "시딩 제안용"])
    
    # 메일 미리보기
    st.subheader("👀 발송될 메일 미리보기")
    subj, body = mailer.generate_email_content(brand, template)
    with st.expander("미리보기 열기/닫기", expanded=True):
        st.markdown(f"**[제목]** {subj}")
        st.text(body)
        st.caption("📎 첨부파일: 명함.png (자동으로 400px 사이즈로 조절되어 첨부됩니다)")
    
    st.divider()
    dummy_db_emails = ["test1@gmail.com", "test2@naver.com"] 
    selected_emails = st.multiselect("발송 대상 선택 (DB 연동)", dummy_db_emails)
    
    if st.button("🚀 선택한 대상에게 메일 발송", type="primary"):
        if selected_emails:
            with st.spinner("메일 발송 중... (명함 이미지 리사이징 포함)"):
                success, msg = mailer.send_bulk_emails(selected_emails, brand, template)
            if success:
                st.success("✅ 메일 발송 완료!")
            else:
                st.error(msg)
        else:
            st.warning("발송할 이메일을 선택해주세요.")

# ==========================================
# 탭 7: AI 회신 자동 분석
# ==========================================
with tabs[6]:
    st.header("🤖 이메일 회신 내역 Gemini 자동 분석")
    st.write("`rizzsender` 수신함으로 전달(Forwarding)된 **안 읽은 회신 메일**을 읽어 유가(비용) 요구 여부를 분석합니다.")
    
    if st.button("🔍 지금 수신함 스캔 및 AI 분석 시작", type="primary"):
        with st.spinner("수신함에 접속하여 Gemini가 문맥을 분석 중입니다..."):
            success, msg, ai_results = mailer.check_replies_and_analyze()
            
            if success:
                st.success(msg)
                if ai_results:
                    st.dataframe(pd.DataFrame(ai_results))
                    st.info("💡 찐 배포 기능: '유가요구여부'가 True인 메일을 구글 시트에서 찾아 해당 행의 배경색을 연노랑색으로 칠하고, '회신현황' 열을 업데이트합니다.")
            else:
                st.error(msg)

# ==========================================
# 탭 8: 콘텐츠 성과 수치 업데이트
# ==========================================
with tabs[7]:
    st.header("📊 콘텐츠 성과 수치 자동 수집")
    st.write("각 브랜드의 '콘텐츠수치' 탭에서 G열(업로드 링크)을 읽어와서 조회수, 좋아요 등을 업데이트합니다.")
    
    metrics_brand = st.selectbox("수치를 업데이트할 브랜드 선택", ["MELV", "SOLV", "UPPR"], key="metrics_brand_select")
    
    if st.button(f"🚀 {metrics_brand}콘텐츠수치 탭 크롤링 및 수치 업데이트", type="primary"):
        with st.spinner('봇이 링크들을 하나씩 타고 들어가서 수치를 긁어오는 중입니다...'):
            result_msg = gs.update_content_metrics(metrics_brand, run_metrics_scraper_dummy)
        st.success(result_msg)
