import streamlit as st
import pandas as pd
from scraper import run_insta_scraper_dummy, run_metrics_scraper_dummy
from gsheets import GoogleSheetsManager
from mailer_and_ai import MailManager

st.set_page_config(page_title="PB 시딩 자동화", layout="wide")

gs = GoogleSheetsManager(st.secrets["gcp_service_account"], st.secrets["google_sheet_name"])
mailer = MailManager(st.secrets["email_sender"], st.secrets["email_password"], st.secrets["gemini_api_key"])

st.title("🚀 PB 인플루언서 시딩 자동화 올인원 솔루션")
st.divider()

tabs = st.tabs(["📸 인스타 검색", "🎵 틱톡 검색", "▶️ 유튜브 검색", "📝 블로그 검색", "🗄️ DB 관리", "✉️ 메일 발송", "🤖 AI 회신 분석"])

# --- [탭 1: 인스타 검색 및 구글 시트 연동] ---
with tabs[0]:
    st.header("인스타 인플루언서 크롤링")
    kw = st.text_input("검색 키워드")
    
    if st.button("🔍 봇 크롤링 시작", type="primary"):
        progress_bar = st.progress(0, "크롤링 중...")
        df_result, failed_links = run_insta_scraper_dummy(kw, progress_bar)
        st.session_state.temp_crawled_data = df_result 
        st.dataframe(df_result)

    st.divider()
    target_brand = st.selectbox("저장할 브랜드 시트 선택", ["MELV", "SOLV", "UPPR"])
    
    if st.button(f"{target_brand} 탭에 크롤링 결과 업데이트"):
        if 'temp_crawled_data' in st.session_state:
            # 첫 번째 행 데이터만 예시로 넣습니다 (전체 반복 시 for문 사용)
            row = st.session_state.temp_crawled_data.iloc[0]
            influencer_data = {"닉네임": row.get("닉네임", ""), "인스타": row.get("프로필링크", ""), "이메일": row.get("이메일", "")}
            
            # 성공 여부를 받아와서 화면에 출력!
            success, msg = gs.insert_influencer_to_brand(target_brand, influencer_data)
            if success:
                st.success(msg)
            else:
                st.error(f"❌ 실패 원인: {msg}") # 시트 연동 실패 시 명확한 에러 노출
        else:
            st.warning("먼저 크롤링을 진행해주세요.")

# --- [탭 6: 메일 발송 및 미리보기] ---
with tabs[5]:
    st.header("✉️ 자동 대량 메일 전송")
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        brand = st.selectbox("진행할 브랜드 선택", ["MELV (멜브)", "SOLV (솔브)", "UPPR (어퍼)"])
        brand_code = brand.split(" ")[0] # MELV, SOLV 등으로 추출
    with col_m2:
        template = st.selectbox("이메일 템플릿", ["커머스 제안용", "시딩 제안용"])
    
    # 💡 메일 미리보기 기능 추가
    st.subheader("👀 발송될 메일 미리보기")
    subj, body = mailer.generate_email_content(brand_code, template)
    with st.expander("미리보기 열기/닫기", expanded=True):
        st.markdown(f"**[제목]** {subj}")
        st.text(body)
        st.caption("📎 첨부파일: 명함_resized.png (자동으로 사이즈가 조절되어 첨부됩니다)")
    
    st.divider()
    dummy_db_emails = ["test1@gmail.com", "test2@naver.com"] 
    selected_emails = st.multiselect("발송 대상 선택 (DB 연동)", dummy_db_emails)
    
    if st.button("🚀 선택한 대상에게 메일 발송", type="primary"):
        if selected_emails:
            with st.spinner("메일 발송 중... (이미지 리사이징 포함)"):
                success, msg = mailer.send_bulk_emails(selected_emails, brand_code, template)
            if success:
                st.success("✅ 메일 발송 완료!")
            else:
                st.error(msg)
        else:
            st.warning("발송할 이메일을 선택해주세요.")
