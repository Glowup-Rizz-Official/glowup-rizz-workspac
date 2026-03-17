import streamlit as st
import pandas as pd
import time
from mailer_logic import OutreachMaster

st.set_page_config(page_title="Glowup Rizz 자동화 툴", layout="wide")

# 사이드바 설정 (API 키 및 기본 정보)
with st.sidebar:
    st.title("⚙️ 설정")
    yt_key = st.text_input("YouTube API Key", type="password")
    gm_key = st.text_input("Gemini API Key", type="password")
    # 박혜란님 고정 정보 [cite: 1, 2]
    email_user = "rizzsender@gmail.com"
    email_pw = st.text_input("Gmail 앱 비밀번호", type="password")

st.title("✉️ 크리에이터 초개인화 섭외 자동화")

# 1. 담당자 선택부
col1, col2 = st.columns(2)
with col1:
    sender_option = st.radio("보내는 사람 선택", ["○ 박혜란", "○ 직접 입력"], horizontal=True)
    if "박혜란" in sender_option:
        sender_name = "박혜란"
    else:
        sender_name = st.text_input("이름 입력", "")

# 2. 브랜드 및 템플릿 선택
with col2:
    brand = st.selectbox("브랜드 선택", ["MELV", "SOLV", "UPPR"])
    t_type = st.selectbox("제안 유형", ["시딩(협찬) 제안", "커머스(공구) 협업"])

# 3. 파일 업로드
uploaded_file = st.file_uploader("크리에이터 리스트 업로드 (Excel)", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.write("📋 업로드된 데이터 미리보기 (상위 5건)")
    st.dataframe(df.head())
    
    if st.button("🚀 분석 시작 및 대량 발송"):
        if not yt_key or not gm_key or not email_pw:
            st.error("API 키와 비밀번호를 모두 입력해주세요.")
        else:
            master = OutreachMaster(yt_key, gm_key, email_user, email_pw)
            progress_bar = st.progress(0)
            
            success_count = 0
            for i, row in df.iterrows():
                try:
                    c_name = row['채널명']
                    c_link = row['채널링크']
                    c_email = row['이메일']
                    
                    # 1. 유튜브 분석
                    video_context = master.get_recent_videos(c_link)
                    
                    # 2. AI 본문 생성
                    ai_body = master.generate_ai_body(brand, t_type, c_name, video_context, sender_name)
                    
                    # 3. 제목 설정
                    subject = f"[{brand}] {c_name}님, 브랜드 협업 제안드립니다."
                    
                    # 4. 발송
                    master.send_email(c_email, subject, ai_body, sender_name)
                    
                    success_count += 1
                    st.success(f"✅ {c_name}님께 발송 성공!")
                    time.sleep(1) # 스팸 방지
                except Exception as e:
                    st.error(f"❌ {row.get('채널명', i)} 발송 실패: {e}")
                
                progress_bar.progress((i + 1) / len(df))
            
            st.balloons()
            st.success(f"🎉 총 {success_count}건의 메일 발송이 완료되었습니다!")
