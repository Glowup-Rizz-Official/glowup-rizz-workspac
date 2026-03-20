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

# --- [2. 템플릿 데이터베이스] ---
templates = {
    'MELV': {
        'commerce': {
            'subject': '[제안] 뷰티 브랜드 멜브(MELV) 커머스 협업 제안드립니다.',
            'body': """안녕하세요 {nickname}님, MELV MD 박혜란입니다.<br><br>저희 뷰티 브랜드 멜브(MELV)의 제품 무드와 시너지가 날 것 같아 함께 수익 쉐어형 커머스(공구)를 진행하고자 제안드립니다.<br><br><b>[브랜드 및 제품 소개]</b><br>브랜드명: MELV(멜브)<br>주력 제품: 립시럽, 립타투<br>성과: 카카오톡 선물하기 뷰티 랭킹 1위 달성<br>제품 확인하기: <a href='https://a-bly.com/app/markets/108879/'>에이블리 링크</a><br><br>감사합니다."""
        },
        'seeding': {
            'subject': '[협찬] 뷰티 브랜드 멜브(MELV) 제품 시딩 제안드립니다.',
            'body': """안녕하세요 {nickname}님, MELV MD 박혜란입니다.<br><br>크리에이터님의 뷰티 콘텐츠 무드와 저희 브랜드 멜브(MELV)의 결이 정말 잘 어울릴 것 같아, 제품 시딩(협찬)을 제안드립니다.<br><br>성함/연락처/주소를 기재하여 회신 부탁드립니다!"""
        }
    },
    'SOLV': {
        'commerce': {'subject': '[제안] 솔브(SOLV) 커머스 제안', 'body': '안녕하세요 {nickname}님, 솔브입니다...'},
        'seeding': {'subject': '[협찬] 솔브(SOLV) 시딩 제안', 'body': '안녕하세요 {nickname}님, 솔브입니다...'}
    },
    'UPPR': {
        'commerce': {'subject': '[제안] 어퍼(UPPR) 커머스 제안', 'body': '안녕하세요 {nickname}님, 어퍼입니다...'},
        'seeding': {'subject': '[협찬] 어퍼(UPPR) 시딩 제안', 'body': '안녕하세요 {nickname}님, 어퍼입니다...'}
    }
}

# --- [3. UI 레이아웃] ---
st.set_page_config(page_title="Glowup Rizz 발송기", layout="wide")
tab1, tab2 = st.tabs(["✉️ 메일 발송", "📊 발송 로그"])

if 'n_input' not in st.session_state: st.session_state.n_input = ""
if 'e_input' not in st.session_state: st.session_state.e_input = ""

with tab1:
    st.title("✉️ 초개인화 대량 발송 시스템")
    
    c1, c2, c3 = st.columns(3)
    with c1: platform = st.radio("발송 계정", ["Gmail", "Naver"], horizontal=True)
    with c2: brand_choice = st.selectbox("브랜드", ["MELV", "SOLV", "UPPR"])
    with c3: type_choice = st.selectbox("종류", ["commerce", "seeding"])
    
    sender_name = st.text_input("서명 이름", "박혜란")

    ci1, ci2 = st.columns(2)
    with ci1: st.session_state.n_input = st.text_area("1. 닉네임 리스트", value=st.session_state.n_input, height=150)
    with ci2: st.session_state.e_input = st.text_area("2. 이메일 리스트", value=st.session_state.e_input, height=150)

    n_list = [n.strip() for n in st.session_state.n_input.split('\n') if n.strip()]
    e_list = [e.strip() for e in st.session_state.e_input.split('\n') if e.strip()]
    
    if n_list and e_list:
        st.subheader("👀 미리보기")
        s_temp = templates[brand_choice][type_choice]
        with st.container(border=True):
            st.markdown(f"**제목:** {s_temp['subject']}")
            st.markdown(f"{s_temp['body'].format(nickname=n_list[0])}", unsafe_allow_html=True)

        if st.button(f"🚀 {len(n_list)}명 발송 시작", type="primary", use_container_width=True):
            user_id = st.secrets["GMAIL_USER"] if platform == "Gmail" else st.secrets["NAVER_USER"]
            user_pw = st.secrets["GMAIL_PW"] if platform == "Gmail" else st.secrets["NAVER_PW"]
            
            progress = st.progress(0)
            status_text = st.empty()
            success_count = 0

            # 이미지 데이터 미리 읽기
            img_data, f_ext = None, "png"
            if os.path.exists(IMAGE_PATH):
                with open(IMAGE_PATH, 'rb') as f: img_data = f.read()
                f_ext = os.path.splitext(IMAGE_PATH)[1][1:].lower()
                if f_ext == 'jpg': f_ext = 'jpeg'

            for i, (nick, email) in enumerate(zip(n_list, e_list)):
                status_text.text(f"⏳ 발송 중: {nick} ({i+1}/{len(n_list)})")
                
                try:
                    # --- 루프 안에서 매번 새로 연결 (연결 오류 방지 핵심!) ---
                    if platform == "Naver":
                        server = smtplib.SMTP_SSL("smtp.naver.com", 465)
                    else:
                        server = smtplib.SMTP("smtp.gmail.com", 587)
                        server.starttls()
                    
                    server.login(user_id, user_pw)

                    # 메일 작성
                    msg = MIMEMultipart('related')
                    msg['From'] = f"{sender_name} <{user_id}>"
                    msg['To'] = email
                    msg['Subject'] = s_temp['subject']
                    msg.add_header('Reply-To', REPLY_TO)

                    body_html = f"<html><body>{s_temp['body'].format(nickname=nick)}<br><br><img src='cid:card' style='width:220px;'></body></html>"
                    msg.attach(MIMEText(body_html, 'html', 'utf-8'))

                    if img_data:
                        image = MIMEImage(img_data, _subtype=f_ext)
                        image.add_header('Content-ID', '<card>')
                        msg.attach(image)

                    server.send_message(msg)
                    server.quit() # 전송 후 바로 연결 종료
                    
                    status = "성공"
                    success_count += 1
                except Exception as e:
                    status = f"실패: {e}"

                # 로그 기록
                conn = sqlite3.connect('mail_history.db')
                conn.execute("INSERT INTO send_log (brand, type, nickname, email, status, sent_at) VALUES (?, ?, ?, ?, ?, ?)",
                             (brand_choice, type_choice, nick, email, status, datetime.datetime.now().strftime("%y/%m/%d %H:%M")))
                conn.commit(); conn.close()
                
                progress.progress((i + 1) / len(n_list))
                time.sleep(1.5)

            st.success(f"🎉 총 {success_count}건 발송 성공!")
            st.session_state.n_input = ""
            st.session_state.e_input = ""
            time.sleep(2)
            st.rerun()

with tab2:
    st.subheader("📊 발송 기록")
    conn = sqlite3.connect('mail_history.db')
    log_df = pd.read_sql_query("SELECT * FROM send_log ORDER BY id DESC", conn)
    conn.close()
    st.dataframe(log_df, use_container_width=True, hide_index=True)
