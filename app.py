import streamlit as st
import pandas as pd
import time
import io
import os
# mailer_logic.py 파일이 같은 폴더에 있어야 합니다.
from mailer_logic import OutreachMaster 

st.set_page_config(page_title="Glowup Rizz 발송 시스템", layout="wide")

# --- [1. 브랜드별 실제 템플릿 데이터베이스] ---
# mail_send.py의 내용을 바탕으로 구성했습니다.
TEMPLATES = {
    'MELV': {
        '시딩 제안용': {
            'subject': '[협찬] 뷰티 브랜드 멜브(MELV) 제품 시딩 제안드립니다.',
            'body': "저희 브랜드 멜브(MELV)의 제품 무드와 크리에이터님의 결이 정말 잘 어울릴 것 같아 제안드립니다.<br><br><b>주력 제품:</b> 립시럽(유리알 광택) & 립타투(24시간 지속)<br><b>성과:</b> 카카오톡 선물하기 뷰티 랭킹 1위 달성<br><b>링크:</b> https://a-bly.com/app/markets/108879/"
        },
        '커머스 제안용': {
            'subject': '[제안] 뷰티 브랜드 멜브(MELV) 커머스 협업 제안드립니다.',
            'body': "수익 쉐어형 커머스(공구) 파트너십을 제안드립니다.<br><br><b>성과:</b> 카카오톡 선물하기 1위 및 높은 재구매율<br><b>플랫폼:</b> 에이블리, 지그재그 등 협의 가능<br><b>링크:</b> https://a-bly.com/app/markets/108879/"
        }
    },
    'SOLV': {
        '시딩 제안용': {
            'subject': '[협찬] 뷰티 브랜드 솔브(SOLV) 화잘먹 모델링팩 시딩 제안드립니다.',
            'body': "물 조절이 필요 없는 '3초 컷' 더블세럼 모델링팩 시딩을 제안드립니다.<br><br><b>특징:</b> 떼어낸 후에도 마르지 않는 윤광 코팅<br><b>링크:</b> https://solv.co.kr/aboutus/productstory.html"
        },
        '커머스 제안용': {
            'subject': '[제안] 뷰티 브랜드 솔브(SOLV) 커머스 협업 제안드립니다.',
            'body': "상호 윈윈할 수 있는 탄탄한 커머스 파트너십을 구축하고 싶습니다.<br><br><b>제품:</b> 더블세럼 모델링팩 (홈에스테틱)<br><b>링크:</b> https://solv.co.kr/aboutus/productstory.html"
        }
    },
    'UPPR': {
        '시딩 제안용': {
            'subject': '[협찬] 라이프/패션 브랜드 어퍼(UPPR) 제품 시딩 제안드립니다.',
            'body': "감각적인 데일리룩 코디와 저희 어퍼(UPPR)의 무드가 잘 맞아 시딩을 제안드립니다.<br><br><b>제공:</b> 코듀로이 볼캡 또는 시그니처 체크셔츠<br><b>링크:</b> https://smartstore.naver.com/uppr"
        },
        '커머스 제안용': {
            'subject': '[제안] 라이프/패션 브랜드 어퍼(UPPR) 커머스 협업 제안드립니다.',
            'body': "힙한 무드와 크리에이터님의 핏이 잘 맞을 것 같아 판매 수익 쉐어형 협업을 제안합니다.<br><br><b>제품:</b> 소두핏 볼캡 및 오버핏 셔츠<br><b>링크:</b> https://smartstore.naver.com/uppr"
        }
    }
}

# --- [2. 사이드바 설정] ---
with st.sidebar:
    st.header("🔑 API 및 계정 설정")
    yt_key = st.text_input("YouTube API Key", type="password", help="Google Cloud Console에서 발급")
    gm_key = st.text_input("Gemini API Key", type="password", help="Google AI Studio에서 발급")
    email_pw = st.text_input("Gmail 앱 비밀번호", type="password", help="rizzsender@gmail.com의 앱 비밀번호")
    email_user = "rizzsender@gmail.com"
    st.info(f"발송 계정: {email_user}\n회신 계정: hcommerceinc1@gmail.com")

st.title("✉️ Glowup Rizz 초개인화 대량 발송")

# --- [3. 메인 UI 및 발송 옵션] ---
col1, col2 = st.columns(2)
with col1:
    # 동그란 칸 아이콘이 포함된 선택창
    sender_option = st.radio("보내는 사람 선택", ["● 박혜란", "○ 직접 입력"], horizontal=True)
    if "박혜란" in sender_option:
        sender_name = "박혜란"
    else:
        sender_name = st.text_input("담당자 성함 입력", placeholder="성함을 입력하세요")

with col2:
    brand = st.selectbox("브랜드 선택", ["MELV", "SOLV", "UPPR"])
    t_type = st.selectbox("제안 유형", ["시딩 제안용", "커머스 제안용"])

# TSV 파일 업로드 및 데이터 처리
uploaded_file = st.file_uploader("구글 시트에서 받은 TSV/TXT 파일 업로드 (9행부터 리스트 시작)", type=["tsv", "txt"])

if uploaded_file:
    try:
        # 인코딩 문제 해결을 위해 binary로 읽은 후 디코딩 시도
        raw_data = uploaded_file.read()
        try:
            decoded_text = raw_data.decode('utf-8')
        except UnicodeDecodeError:
            decoded_text = raw_data.decode('cp949') # 한국어 윈도우 환경 대응
        
        # 9행부터 데이터 시작 (skiprows=8), 탭으로 구분
        # 혜란님 시트 기준: 2열(idx 1) 닉네임, 3열(idx 2) 링크, 6열(idx 5) 이메일
        df = pd.read_csv(io.StringIO(decoded_text), sep='\t', skiprows=8, header=None)
        
        # 데이터 정제: 닉네임과 링크가 비어있지 않은 행만 필터링
        df = df[df[1].notna() & df[2].notna()]
        
        st.success(f"✅ 총 {len(df)}명의 크리에이터를 찾았습니다.")
        
        # 데이터 확인용 표 (닉네임, 링크, 이메일 열만)
        display_df = df[[1, 2, 5]].copy()
        display_df.columns = ["닉네임", "채널링크", "이메일"]
        st.dataframe(display_df, use_container_width=True)

        if st.button(f"🚀 {len(df)}명에게 초개인화 메일 전체 발송", type="primary"):
            if not yt_key or not gm_key or not email_pw:
                st.error("설정 창에서 API 키와 비밀번호를 모두 입력해주세요.")
            else:
                master = OutreachMaster(yt_key, gm_key, email_user, email_pw)
                progress_bar = st.progress(0)
                status_box = st.empty()
                
                success_count = 0
                for i, (idx, row) in enumerate(df.iterrows()):
                    nickname = str(row[1]).strip()
                    link = str(row[2]).strip()
                    email = str(row[5]).strip() if pd.notna(row[5]) else ""
                    
                    if "@" not in email:
                        st.warning(f"⚠️ {nickname}님은 이메일 정보가 없어 건너뜁니다.")
                        continue

                    status_box.text(f"⏳ ({i+1}/{len(df)}) {nickname}님 영상 분석 및 발송 중...")
                    
                    # 1. 유튜브 분석 (링크에 youtube가 포함된 경우에만)
                    video_info = "활동 확인 중"
                    if "youtube" in link or "youtu.be" in link:
                        video_info = master.get_recent_videos(link)
                    
                    # 2. AI 초개인화 문구 생성 (브랜드 무드 반영)
                    custom_intro = master.generate_ai_body(brand, t_type, nickname, video_info, sender_name)
                    
                    # 3. 메일 제목 및 본문 결합
                    temp_data = TEMPLATES[brand][t_type]
                    full_body = f"{custom_intro}<br><br>{temp_data['body']}<br><br>감사합니다.<br>{brand} 담당자 {sender_name} 드림"
                    
                    # 4. 발송
                    master.send_email(email, temp_data['subject'], full_body, sender_name)
                    
                    success_count += 1
                    time.sleep(1.2) # 구글 스팸 필터링 방지
                    progress_bar.progress((i + 1) / len(df))
                
                status_box.empty()
                st.balloons()
                st.success(f"🎉 발송 완료! (성공: {success_count} / 전체: {len(df)})")
                
    except Exception as e:
        st.error(f"에러 발생: {e}")
        st.info("💡 팁: 구글 시트에서 '파일' -> '내보내기' -> '탭 구분 값(.tsv)'으로 받은 파일이 맞는지 확인해 주세요.")
