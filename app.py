import streamlit as st
import pandas as pd
import time
from mailer_logic import OutreachMaster # 기존 로직 활용

st.set_page_config(page_title="Glowup Rizz 발송 시스템", layout="wide")

# 1. 템플릿 데이터베이스 (mail_send.py 내용 이식) 
TEMPLATES = {
    'MELV': {
        '시딩 제안용': {
            'subject': '[협찬] 뷰티 브랜드 멜브(MELV) 제품 시딩 제안드립니다.',
            'body': "안녕하세요 크리에이터님, MELV MD 박혜란입니다.<br><br>크리에이터님의 뷰티 콘텐츠 무드와 저희 브랜드 멜브(MELV)의 결이 정말 잘 어울릴 것 같아 제품 시딩을 제안드립니다.<br><br><b>[브랜드 소개]</b><br>제품: 립시럽 & 립타투<br>성과: 카카오톡 선물하기 뷰티 1위 달성<br>링크: https://a-bly.com/app/markets/108879/<br><br>"
        },
        '커머스 제안용': {
            'subject': '[제안] 뷰티 브랜드 멜브(MELV) 커머스 협업 제안드립니다.',
            'body': "안녕하세요 크리에이터님, MELV MD 박혜란입니다.<br><br>저희 제품 무드와 시너지가 날 것 같아 수익 쉐어형 커머스(공구)를 제안드립니다.<br><br><b>[성과 지표]</b><br>실사용자 리뷰 및 재구매율 기반 제품력 입증 완료<br>플랫폼: 에이블리, 카카오톡 선물하기 등 협의 가능<br><br>"
        }
    }
}

# 사이드바 설정
with st.sidebar:
    st.header("🔑 인증 설정")
    yt_key = st.text_input("YouTube API Key", type="password")
    gm_key = st.text_input("Gemini API Key", type="password")
    email_pw = st.text_input("Gmail 앱 비밀번호", type="password")
    email_user = "rizzsender@gmail.com" [cite: 1]

st.title("✉️ 초개인화 대량 메일 발송 (Glowup Rizz 전용)")

# 담당자 및 브랜드 선택
col1, col2 = st.columns(2)
with col1:
    sender_option = st.radio("보내는 사람 선택", ["● 박혜란", "○ 직접 입력"], horizontal=True)
    sender_name = "박혜란" if "●" in sender_option else st.text_input("이름 입력", "")

with col2:
    brand = st.selectbox("브랜드 선택", ["MELV", "SOLV", "UPPR"])
    t_type = st.selectbox("제안 유형", ["시딩 제안용", "커머스 제안용"])

# TSV 파일 업로드
uploaded_file = st.file_uploader("구글 시트에서 받은 TSV/TXT 파일 업로드", type=["tsv", "txt"])

if uploaded_file:
    try:
        # 다양한 인코딩으로 읽기 시도 (오류 방지)
        content = uploaded_file.read()
        try:
            decoded_content = content.decode('utf-8')
        except:
            decoded_content = content.decode('cp949')
        
        # 9행부터 시작 (skiprows=8), 탭으로 구분
        df = pd.read_csv(io.StringIO(decoded_content), sep='\t', skiprows=8, header=None)
        
        # 혜란님이 지정한 열 번호로 데이터 추출
        # index 1: 닉네임, index 2: 링크, index 5: 이메일
        df = df.dropna(subset=[1, 2]) # 닉네임과 링크가 없으면 제외
        
        st.success(f"✅ {len(df)}명의 리스트를 성공적으로 불러왔습니다.")
        st.dataframe(df[[1, 2, 5]].rename(columns={1: "닉네임", 2: "채널링크", 5: "이메일"}))

        if st.button("🚀 분석 및 전체 발송 시작"):
            master = OutreachMaster(yt_key, gm_key, email_user, email_pw)
            progress = st.progress(0)
            
            for i, (idx, row) in enumerate(df.iterrows()):
                nickname = str(row[1])
                link = str(row[2])
                email = str(row[5]) if pd.notna(row[5]) else ""
                
                if "@" in email:
                    # 1. 유튜브 분석 (최근 10개 영상 제목 추출)
                    video_info = master.get_recent_videos(link) if "youtube" in link else "활동 확인 중"
                    
                    # 2. AI 초개인화 문구 생성 (Gemini)
                    base_temp = TEMPLATES.get(brand, TEMPLATES['MELV'])[t_type]
                    custom_intro = master.generate_ai_body(brand, t_type, nickname, video_info, sender_name)
                    
                    # 3. 메일 조립 및 발송 [cite: 1, 4]
                    full_body = custom_intro + "<br><br>" + base_temp['body']
                    master.send_email(email, base_temp['subject'], full_body, sender_name)
                    
                    st.write(f"✔️ {nickname}님께 발송 완료")
                    time.sleep(1)
                
                progress.progress((i + 1) / len(df))
            st.balloons()

    except Exception as e:
        st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")
        st.info("💡 팁: 구글 시트에서 '탭 구분 값(.tsv)'으로 정확히 내보냈는지 확인해 주세요.")
