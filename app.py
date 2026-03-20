import streamlit as st
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import pandas as pd
import sqlite3
import datetime
import time
import os

# --- [1. 기본 설정] ---
REPLY_TO = "hcommerceinc1@gmail.com"
IMAGE_PATH = "명함.png"

def init_db():
    conn = sqlite3.connect('mail_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS send_log 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, brand TEXT, type TEXT, nickname TEXT, email TEXT, status TEXT, sent_at TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- [2. 혜란님 원본 템플릿 복구] ---
templates = {
    'MELV': {
        'commerce': {
            'subject': '[제안] 뷰티 브랜드 멜브(MELV) 커머스 협업 제안드립니다.',
            'body': """안녕하세요 {nickname}님, MELV MD 박혜란입니다.<br><br>저희 뷰티 브랜드 멜브(MELV)의 제품 무드와 시너지가 날 것 같아 함께 수익 쉐어형 커머스(공구)를 진행하고자 제안드립니다.<br><br><b>[브랜드 및 제품 소개]</b><br>브랜드명: MELV(멜브)<br>주력 제품: 립시럽(맑은 유리알 광택), 립타투(24시간 지속력/뮤티드 컬러/오버립)<br>성과 지표: 카카오톡 선물하기 뷰티 랭킹 1위 달성, 실사용자 리뷰 및 재구매율 기반 제품력 입증 완료<br>제품 확인하기: https://a-bly.com/app/markets/108879/<br><br><b>[협업 제안 내용]</b><br>협업 형태: 인플루언서 전용 링크를 통한 판매 수익 쉐어 (RS)<br>플랫폼: 에이블리, 카카오톡 선물하기, 지그재그 등 협의 가능<br><br>단순 광고를 넘어 함께 윈윈할 수 있는 커머스 파트너십을 맺고 싶습니다.<br>상세 제안서 검토를 희망하시거나 미팅이 가능하시다면 회신 부탁드립니다.<br><br>감사합니다.<br>박혜란 드림"""
        },
        'seeding': {
            'subject': '[협찬] 뷰티 브랜드 멜브(MELV) 제품 시딩 제안드립니다.',
            'body': """안녕하세요 {nickname}님, MELV MD 박혜란입니다.<br><br>크리에이터님의 뷰티 콘텐츠 무드와 저희 브랜드 멜브(MELV)의 결이 정말 잘 어울릴 것 같아, 제품 시딩(협찬)을 제안드립니다.<br><br><b>[브랜드 및 제품 소개]</b><br>브랜드명: MELV(멜브)<br>제공 제품: 립시럽(맑은 광택) & 립타투(24시간 지속/오버립) 베스트 라인업<br>제품 확인하기: https://a-bly.com/app/markets/108879/<br><br>제품 수령을 희망하신다면 [성함/연락처/주소]를 기재하여 편하게 회신 부탁드리겠습니다.<br><br>감사합니다.<br>박혜란 드림"""
        }
    },
    'SOLV': {
        'commerce': {
            'subject': '[제안] 뷰티 브랜드 솔브(SOLV) 커머스 협업 제안드립니다.',
            'body': """안녕하세요 {nickname}님, SOLV 담당자 박혜란입니다.<br><br>저희 브랜드 솔브(SOLV)와 함께 시너지를 낼 수 있는 수익 쉐어형 커머스 파트너십을 제안드립니다.<br><br><b>주력 제품:</b> 더블세럼 모델링팩 (물 조절 필요 없는 3초 컷 홈에스테틱)<br>제품 확인하기: https://solv.co.kr/aboutus/productstory.html<br><br>상세 제안서 검토나 미팅 일정을 잡고자 하신다면 편하게 회신 부탁드립니다.<br><br>감사합니다.<br>박혜란 드림"""
        },
        'seeding': {
            'subject': '[협찬] 뷰티 브랜드 솔브(SOLV) 화잘먹 모델링팩 시딩 제안드립니다.',
            'body': """안녕하세요 {nickname}님, SOLV 담당자 박혜란입니다.<br><br>저희 브랜드 솔브(SOLV)의 '화잘먹 윤광 코팅' 효과를 예쁘게 보여주실 수 있을 것 같아 제품 시딩을 제안드립니다.<br><br>제품 수령을 희망하신다면 회신 부탁드리겠습니다.<br><br>감사합니다.<br>박혜란 드림"""
        }
    },
    'UPPR': {
        'commerce': {
            'subject': '[제안] 라이프/패션 브랜드 어퍼(UPPR) 커머스 협업 제안드립니다.',
            'body': """안녕하세요 {nickname}님, UPPR 담당자 박혜란입니다.<br><br>저희 브랜드 어퍼(UPPR)의 힙한 무드와 크리에이터님의 핏이 아주 잘 맞을 것 같아 협업을 제안드립니다.<br><br><b>주력 제품:</b> 광대와 두상을 완벽하게 커버하는 소두핏 볼캡 or 시그니처 체크셔츠<br>제품 확인하기: https://smartstore.naver.com/uppr<br><br>감사합니다.<br>박혜란 드림"""
        },
        'seeding': {
            'subject': '[협찬] 라이프/패션 브랜드 어퍼(UPPR) 제품 시딩 제안드립니다.',
            'body': """안녕하세요 {nickname}님, UPPR 담당자 박혜란입니다.<br><br>감각적인 데일리룩 코디에 저희 어퍼(UPPR) 볼캡을 가볍게 툭 매치해 주시면 정말 좋을 것 같아 시딩을 제안드립니다.<br><br>감사합니다.<br>박혜란 드림"""
        }
    }
}

# --- [3. UI 레이아웃] ---
st.set_page_config(page_title="Glowup Rizz 대량 발송기", layout="wide")
tab1, tab2 = st.tabs(["✉️ 메일 발송", "📊 발송 로그"])

if 'nick_raw' not in st.session_state: st.session_state.nick_raw = ""
if 'email_raw' not in st.session_state: st.session_state.email_raw = ""

with tab1:
    st.title("✉️ 초개인화 대량 발송 시스템")
    
    col_set1, col_set2, col_set3 = st.columns([1, 1, 1])
    with col_set1:
        platform = st.radio("발송 계정 선택", ["Gmail", "Naver"], horizontal=True)
    with col_set2:
        brand_choice = st.selectbox("브랜드 선택", ["MELV", "SOLV", "UPPR"])
    with col_set3:
        type_choice = st.selectbox("템플릿 종류", ["commerce", "seeding"], format_func=lambda x: "커머스 제안" if x == "commerce" else "시딩(협찬) 제안")
    
    sender_name = st.text_input("담당자 서명 이름", "박혜란")

    st.divider()

    col_in1, col_in2 = st.columns(2)
    with col_in1:
        st.session_state.nick_raw = st.text_area("1. 닉네임 리스트 (줄바꿈 구분)", value=st.session_state.nick_raw, height=180)
    with col_in2:
        st.session_state.email_raw = st.text_area("2. 이메일 리스트 (줄바꿈 구분)", value=st.session_state.email_raw, height=180)

    n_list = [n.strip() for n in st.session_state.nick_raw.split('\n') if n.strip()]
    e_list = [e.strip() for e in st.session_state.email_raw.split('\n') if e.strip()]
    
    if n_list and e_list:
        st.subheader("👀 발송 미리보기")
        s_temp = templates[brand_choice][type_choice]
        with st.container(border=True):
            st.markdown(f"**제목:** {s_temp['subject']}")
            st.markdown(f"**수신:** {n_list[0]} ({e_list[0]})")
            st.divider()
            st.markdown(f"<div style='font-size: 14px;'>{s_temp['body'].format(nickname=n_list[0])}</div>", unsafe_allow_html=True)
            if os.path.exists(IMAGE_PATH):
                st.image(IMAGE_PATH, width=220)

        if st.button(f"🚀 {len(n_list)}명에게 발송 시작", type="primary", use_container_width=True):
            user_id = st.secrets["GMAIL_USER"] if platform == "Gmail" else st.secrets["NAVER_USER"]
            user_pw = st.secrets["GMAIL_PW"] if platform == "Gmail" else st.secrets["NAVER_PW"]
            
            progress = st.progress(0)
            status_text = st.empty()
            success_count = 0

            img_data, f_ext = None, "png"
            if os.path.exists(IMAGE_PATH):
                with open(IMAGE_PATH, 'rb') as f: img_data = f.read()
                f_ext = os.path.splitext(IMAGE_PATH)[1][1:].lower()
                if f_ext == 'jpg': f_ext = 'jpeg'

            # 발송 루프
            for i, (nick, email) in enumerate(zip(n_list, e_list)):
                status_text.text(f"⏳ 발송 중: {nick} ({i+1}/{len(n_list)})")
                
                try:
                    # 서버 연결 (매번 새로 연결하여 안정성 확보)
                    if platform == "Naver":
                        server = smtplib.SMTP_SSL("smtp.naver.com", 465)
                    else:
                        server = smtplib.SMTP("smtp.gmail.com", 587)
                        server.starttls()
                    
                    server.login(user_id, user_pw)

                    msg = MIMEMultipart('related')
                    msg['From'] = f"{sender_name} <{user_id}>"
                    msg['To'] = email
                    msg['Subject'] = s_temp['subject']
                    msg.add_header('Reply-To', REPLY_TO)

                    # HTML 조립 (명함 사이즈 small로 조정)
                    f_html = f"<html><body><div style='font-family:sans-serif; font-size:14px;'>{s_temp['body'].format(nickname=nick)}</div><br><img src='cid:card' style='width:220px;'></body></html>"
                    msg_alt = MIMEMultipart('alternative')
                    msg.attach(msg_alt)
                    msg_alt.attach(MIMEText(f_html, 'html', 'utf-8'))

                    if img_data:
                        image = MIMEImage(img_data, _subtype=f_ext)
                        image.add_header('Content-ID', '<card>')
                        msg.attach(image)

                    server.send_message(msg)
                    server.quit()
                    
                    status = "성공"
                    success_count += 1
                except Exception as e:
                    status = f"실패: {e}"

                # DB 기록
                conn = sqlite3.connect('mail_history.db')
                conn.execute("INSERT INTO send_log (brand, type, nickname, email, status, sent_at) VALUES (?, ?, ?, ?, ?, ?)",
                             (brand_choice, type_choice, nick, email, status, datetime.datetime.now().strftime("%y/%m/%d %H:%M")))
                conn.commit(); conn.close()
                
                progress.progress((i + 1) / len(n_list))
                time.sleep(1.2)

            if success_count > 0:
                st.success(f"🎉 총 {success_count}건 발송 성공!")
                st.session_state.nick_raw = ""
                st.session_state.email_raw = ""
                time.sleep(2)
                st.rerun()
            else:
                st.error("❌ 발송에 실패했습니다. 네이버/지메일 앱 비밀번호와 SMTP 설정을 확인해주세요.")

with tab2:
    st.subheader("📊 발송 기록")
    conn = sqlite3.connect('mail_history.db')
    log_df = pd.read_sql_query("SELECT * FROM send_log ORDER BY id DESC", conn)
    conn.close()
    st.dataframe(log_df, use_container_width=True, hide_index=True)
