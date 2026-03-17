import streamlit as st
import pandas as pd
import time
import io
from mailer_logic import OutreachMaster  # 앞서 만든 로직 파일

st.set_page_config(page_title="Glowup Rizz 자동화 툴", layout="wide")

# 사이드바 설정
with st.sidebar:
    st.title("⚙️ API 설정")
    yt_key = st.text_input("YouTube API Key", type="password")
    gm_key = st.text_input("Gemini API Key", type="password")
    email_user = "rizzsender@gmail.com"
    email_pw = st.text_input("Gmail 앱 비밀번호", type="password")

st.title("✉️ 초개인화 대량 메일 발송 (TSV 전용)")

# 1. 담당자 및 브랜드 선택
col1, col2 = st.columns(2)
with col1:
    # 요청하신 '동그란 칸' 선택 아이콘 (Radio Button)
    sender_option = st.radio("보내는 사람 선택", ["● 박혜란", "○ 직접 입력"], horizontal=True)
    sender_name = "박혜란" if "박혜란" in sender_option else st.text_input("담당자 성함 입력", "")

with col2:
    brand = st.selectbox("브랜드 선택", ["MELV", "SOLV", "UPPR"])
    t_type = st.selectbox("제안 유형", ["시딩 제안용", "커머스 제안용"])

# 2. TSV 파일 업로드 (구글 시트 탭 내보내기용)
uploaded_file = st.file_uploader("구글 시트에서 받은 TSV 파일을 업로드하세요", type=["tsv", "txt"])

if uploaded_file:
    # 9행부터 데이터 시작 (skiprows=8), 탭 구분자(sep='\t') 적용
    # 헤더가 9행에 없을 경우를 대비해 header=None으로 읽고 인덱스로 접근합니다.
    try:
        df = pd.read_csv(uploaded_file, sep='\t', skiprows=8, header=None)
        
        # 유효한 데이터만 필터링 (닉네임이나 링크가 있는 행만)
        df = df[df[1].notna() & df[2].notna()]
        
        st.success(f"✅ 총 {len(df)}명의 크리에이터 리스트를 불러왔습니다.")
        
        # 데이터 구조 확인용 (전체 출력)
        with st.expander("불러온 리스트 전체 보기"):
            display_df = df.iloc[:, [1, 2, 4, 5]] # 닉네임, 링크, 틱톡, 블로그 열만 표시
            display_df.columns = ["닉네임", "인스타/유튜브", "틱톡", "블로그"]
            st.dataframe(display_df)

        # 3. 발송 버튼
        if st.button(f"🚀 {len(df)}명에게 초개인화 메일 즉시 발송", type="primary"):
            if not yt_key or not gm_key or not email_pw:
                st.error("설정창에서 API 키와 비밀번호를 모두 입력해주세요.")
            else:
                master = OutreachMaster(yt_key, gm_key, email_user, email_pw)
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                success_count = 0
                for i, (idx, row) in enumerate(df.iterrows()):
                    try:
                        # 열 번호 기준: 2열(index 1) 닉네임, 3열(index 2) 링크
                        c_nickname = str(row[1]).strip()
                        c_link = str(row[2]).strip()
                        c_email = str(row[5]).strip() if pd.notna(row[5]) else "" # 6열(index 5) 이메일 가정
                        
                        if "@" not in c_email:
                            st.warning(f"⚠️ {c_nickname}: 이메일 주소가 없어서 건너뜁니다.")
                            continue

                        status_text.text(f"⏳ ({i+1}/{len(df)}) {c_nickname}님 분석 및 발송 중...")
                        
                        # 유튜브 링크인 경우에만 영상 분석 수행
                        video_context = "최근 활동 중"
                        if "youtube.com" in c_link or "youtu.be" in c_link:
                            video_context = master.get_recent_videos(c_link)
                        
                        # AI 개인화 본문 생성
                        ai_body = master.generate_ai_body(brand, t_type, c_nickname, video_context, sender_name)
                        
                        # 메일 제목 (브랜드별 템플릿 적용)
                        subject = f"[{brand} X {c_nickname}] 브랜드 협업 제안드립니다."
                        
                        # 발송 (명함.png 자동 포함)
                        master.send_email(c_email, subject, ai_body, sender_name)
                        
                        success_count += 1
                        time.sleep(1.5) # 안정적인 발송을 위한 대기
                        
                    except Exception as e:
                        st.error(f"❌ {c_nickname} 발송 실패: {e}")
                    
                    progress_bar.progress((i + 1) / len(df))
                
                status_text.empty()
                st.balloons()
                st.success(f"🎉 발송 완료! (성공: {success_count} / 전체: {len(df)})")
    
    except Exception as e:
        st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")
