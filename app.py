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

# --- [1. 기본 설정 및 보안] ---
SMTP_SETTINGS = {
    "Gmail": {"host": "smtp.gmail.com", "port": 587},
    "Naver": {"host": "smtp.naver.com", "port": 465} # 네이버는 465 SSL 고정
}

REPLY_TO = "hcommerceinc1@gmail.com"
IMAGE_PATH = "명함.png"

# 데이터베이스 설정
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
            'body': """안녕하세요 {nickname}님, MELV MD 박혜란입니다.<br><br>저희 뷰티 브랜드 멜브(MELV)의 제품 무드와 시너지가 날 것 같아 함께 수익 쉐어형 커머스(공구)를 진행하고자 제안드립니다.<br><br><b>[브랜드 및 제품 소개]</b><br>브랜드명: MELV(멜브)<br>주력 제품: 립시럽, 립타투<br>성과: 카카오톡 선물하기 뷰티 랭킹 1위 달성<br>제품 확인하기: <a href='https://a-bly.com/app/markets/108879/'>에이블리 링크</a><br><br>상세 제안서 검토를 희망하시거나 미팅이 가능하시다면 회신 부탁드립니다.<br><br>감사합니다.<br>박혜란 드림"""
        },
        'seeding': {
            'subject': '[협찬] 뷰티 브랜드 멜브(MELV) 제품 시딩 제안드립니다.',
            'body': """안녕하세요 {nickname}님, MELV MD 박혜란입니다.<br><br>크리에이터님의 뷰티 콘텐츠 무드와 저희 브랜드 멜브(MELV)의 결이 정말 잘 어울릴 것 같아, 제품 시딩(협찬)을 제안드립니다.<br><br>제품 수령을 희망하신다면 [성함/연락처/주소]를 기재하여 편하게 회신 부탁드리겠습니다.<br><br>감사합니다.<br>박혜란 드림"""
        }
    },
    'SOLV': {
        'commerce': {
            'subject': '[제안] 뷰티 브랜드 솔브(SOLV) 커머스 협업 제안드립니다.',
            'body': """안녕하세요 {nickname}님, SOLV 담당자 박혜란입니다.<br><br>저희 브랜드 솔브(SOLV)와 함께 시너지를 낼 수 있는 수익 쉐어형 커머스 파트너십을 제안드립니다.<br><br><b>주력 제품:</b> 더블세럼 모델링팩 (3초 컷 홈에스테틱)<br>제품 확인하기: <a href='https://solv.co.kr/aboutus/productstory.html'>공식몰 링크</a><br><br>상세 제안서 검토나 미팅 일정을 잡고자 하신다면 편하게 회신 부탁드립니다.<br><br>감사합니다.<br>박혜란 드림"""
        },
        'seeding': {
            'subject': '[협찬] 뷰티 브랜드 솔브(SOLV) 화잘먹 모델링팩 시딩 제안드립니다.',
            'body': """안녕하세요 {nickname}님, SOLV 담당자 박혜란입니다.<br><br>크리에이터님 특유의 맑은 분위기와 저희 브랜드 솔브(SOLV)가 만나면 좋은 시너지가 날 것 같아 제품 시딩(협찬)을 제안드립니다.<br><br>제품 수령을 희망하신다면 [성함/연락처/주소]를 기재하여 편하게 회신 부탁드리겠습니다.<br><br>감사합니다.<br>박혜란 드림"""
        }
    },
    'UPPR': {
        'commerce': {
            'subject': '[제안] 라이프/패션 브랜드 어퍼(UPPR) 커머스 협업 제안드립니다.',
            'body': """안녕하세요 {nickname}님, UPPR 담당자 박혜란입니다.<br><br>저희 브랜드 어퍼(UPPR)의 힙한 무드와 크리에이터님의 핏이 아주 잘 맞을 것 같아 협업을 제안드립니다.<br><br><b>주력 제품:</b> 소두핏 볼캡 or 시그니처 체크셔츠<br>제품 확인하기: <a href='https://smartstore.naver.com/uppr'>스마트스토어 링크</a><br><br>감사합니다.<br>박혜란 드림"""
        },
        'seeding': {
            'subject': '[협찬] 라이프/패션 브랜드 어퍼(UPPR) 제품 시딩 제안드립니다.',
            'body': """안녕하세요 {nickname}님, UPPR 담당자 박혜란입니다.<br><br>데일리룩 코디를 잘 보고 있어 저희 어퍼 브랜드의 제품 시딩(협찬)을 제안드립니다.<br><br>제품 수령을 원하신다면 [성함/연락처/주소]와 함께 원하시는 품목을 기재하여 회신 부탁드리겠습니다.<br><br>감사합니다.<br>박혜란 드림"""
        }
    }
}

# --- [3. UI 레이아웃] ---
st.set_page_config(page_title="Glowup Rizz 대량 발송기", layout="wide")
tab1, tab2 = st.tabs(["✉️ 메일 발송", "📊 발송 로그"])

if 'nick_input' not in st.session_state: st.session_state.nick_input = ""
if 'email_input' not in st.session_state: st.session_state.email_input = ""

with tab1:
    st.title("✉️ 초개인화 대량 발송 시스템")
    
    col1, col2, col3 = st.columns(3)
    with col1: platform = st.radio("발송 계정", ["Gmail", "Naver"], horizontal=True)
    with col2: brand_choice = st.selectbox("브랜드", ["MELV", "SOLV", "UPPR"])
    with col3: type_choice = st.selectbox("종류", ["commerce", "seeding"])
    
    sender_name = st.text_input("서명 이름", "박혜란")

    col_in1, col_in2 = st.columns(2)
    with col_in1:
        st.session_state.nick_input = st.text_area("1. 닉네임 리스트", value=st.session_state.nick_input, height=150)
    with col_in2:
        st.session_state.email_input = st.text_area("2. 이메일 리스트", value=st.session_state.email_input, height=150)

    nicks = [n.strip() for n in st.session_state.nick_input.split('\n') if n.strip()]
    emails = [e.strip() for e in st.session_state.email_input.split('\n') if e.strip()]
    
    if nicks and emails:
        target_df = pd.DataFrame({"닉네임": nicks, "이메일": emails})
        
        st.subheader("👀 미리보기")
        selected_temp = templates[brand_choice][type_choice]
        preview_body = selected_temp['body'].format(nickname=nicks[0])
        
        with st.container(border=True):
            st.markdown(f"**제목:** {selected_temp['subject']}")
            st.markdown(f"<div style='font-size:14px;'>{preview_body}</div>", unsafe_allow_html=True)
            if os.path.exists(IMAGE_PATH): st.image(IMAGE_PATH, width=220)

        if st.button(f"🚀 {len(target_df)}명 발송 시작", type="primary", use_container_width=True):
            user_id = st.secrets["GMAIL_USER"] if platform == "Gmail" else st.secrets["NAVER_USER"]
            user_pw = st.secrets["GMAIL_PW"] if platform == "Gmail" else st.secrets["NAVER_PW"]
            
            progress = st.progress(0)
            status_text = st.empty()
            success_count = 0

            try:
                img_data = None
                file_ext = "png"
                if os.path.exists(IMAGE_PATH):
                    with open(IMAGE_PATH, 'rb') as f: img_data = f.read()
                    file_ext = os.path.splitext(IMAGE_PATH)[1][1:].lower()
                    if file_ext == 'jpg': file_ext = 'jpeg'

                # 발송 서버 연결
                if platform == "Naver":
                    server = smtplib.SMTP_SSL("smtp.naver.com", 465)
                else:
                    server = smtplib.SMTP("smtp.gmail.com", 587)
                    server.starttls()
                
                server.login(user_id, user_pw)

                for i, row in target_df.iterrows():
                    nick, email = row['닉네임'], row['이메일']
                    status_text.text(f"⏳ 발송 중: {nick} ({i+1}/{len(target_df)})")
                    
                    msg = MIMEMultipart('related')
                    msg['From'] = f"{sender_name} <{user_id}>"
                    msg['To'] = email
                    msg['Subject'] = selected_temp['subject']
                    msg.add_header('Reply-To', REPLY_TO)

                    final_html = f"<html><body><div style='font-family:sans-serif; font-size:14px;'>{selected_temp['body'].format(nickname=nick)}</div><br><img src='cid:card' style='width:220px;'></body></html>"
                    msg_alt = MIMEMultipart('alternative')
                    msg.attach(msg_alt)
                    msg_alt.attach(MIMEText(final_html, 'html', 'utf-8'))

                    if img_data:
                        image = MIMEImage(img_data, _subtype=file_ext)
                        image.add_header('Content-ID', '<card>')
                        msg.attach(image)

                    try:
                        server.send_message(msg)
                        status = "성공"
                        success_count += 1
                    except Exception as e: status = f"실패: {e}"
                    
                    conn = sqlite3.connect('mail_history.db')
                    conn.execute("INSERT INTO send_log (brand, type, nickname, email, status, sent_at) VALUES (?, ?, ?, ?, ?, ?)",
                                 (brand_choice, type_choice, nick, email, status, datetime.datetime.now().strftime("%y/%m/%d %H:%M")))
                    conn.commit(); conn.close()
                    
                    progress.progress((i + 1) / len(target_df))
                    time.sleep(1.5)

                server.quit()
                st.success(f"🎉 총 {success_count}건 발송 성공!")
                st.session_state.nick_input = ""
                st.session_state.email_input = ""
                st.rerun()

            except Exception as e:
                st.error(f"❌ 연결 오류: {e}")

with tab2:
    st.subheader("📊 발송 기록")
    conn = sqlite3.connect('mail_history.db')
    log_df = pd.read_sql_query("SELECT * FROM send_log ORDER BY id DESC", conn)
    conn.close()
    st.dataframe(log_df, use_container_width=True, hide_index=True)
