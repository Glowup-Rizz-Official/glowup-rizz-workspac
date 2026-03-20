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

# --- [1. 발송 서버 설정] ---
SMTP_SETTINGS = {
    "Gmail": {"host": "smtp.gmail.com", "port": 587},
    "Naver": {"host": "smtp.naver.com", "port": 587}
}

REPLY_TO = "hcommerceinc1@gmail.com"
IMAGE_PATH = "명함.png"

# 데이터베이스 초기화
def init_db():
    conn = sqlite3.connect('mail_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS send_log 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, brand TEXT, type TEXT, nickname TEXT, email TEXT, status TEXT, sent_at TEXT)''')
    conn.commit()
    conn.close()

init_db()

# 입력창 초기화 함수
def clear_inputs():
    st.session_state.nick_list = ""
    st.session_state.email_list = ""

# --- [2. 템플릿 데이터베이스] ---
templates = {
    'MELV': {
        'commerce': {
            'subject': '[제안] 뷰티 브랜드 멜브(MELV) 커머스 협업 제안드립니다.',
            'body': """안녕하세요 {nickname}님, MELV MD 박혜란입니다.<br><br>저희 뷰티 브랜드 멜브(MELV)의 제품 무드와 시너지가 날 것 같아 함께 수익 쉐어형 커머스(공구)를 진행하고자 제안드립니다.<br><br><b>[브랜드 및 제품 소개]</b><br>브랜드명: MELV(멜브)<br>주력 제품: 립시럽(맑은 유리알 광택), 립타투(24시간 지속력/뮤티드 컬러/오버립)<br>성과 지표: 카카오톡 선물하기 뷰티 랭킹 1위 달성, 실사용자 리뷰 및 재구매율 기반 제품력 입증 완료<br>제품 확인하기: <a href='https://a-bly.com/app/markets/108879/'>에이블리 링크</a><br><br>단순 광고를 넘어 함께 윈윈할 수 있는 커머스 파트너십을 맺고 싶습니다.<br>관련하여 상세 제안서 검토를 희망하시거나 미팅이 가능하시다면 회신 부탁드립니다.<br><br>감사합니다.<br>박혜란 드림"""
        },
        'seeding': {
            'subject': '[협찬] 뷰티 브랜드 멜브(MELV) 제품 시딩 제안드립니다.',
            'body': """안녕하세요 {nickname}님, MELV MD 박혜란입니다.<br><br>크리에이터님의 뷰티 콘텐츠 무드와 저희 브랜드 멜브(MELV)의 결이 정말 잘 어울릴 것 같아, 제품 시딩(협찬)을 제안드리고자 연락드렸습니다.<br><br><b>[브랜드 및 제품 소개]</b><br>브랜드명: MELV(멜브)<br>제공 제품: 립시럽(맑은 광택) & 립타투(24시간 지속/오버립) 베스트 라인업<br>제품 확인하기: <a href='https://a-bly.com/app/markets/108879/'>에이블리 링크</a><br><br>이번 제품 시딩은 직접 사용해 보신 후 인스타그램(피드 또는 릴스)에 1회 업로드해 주시는 형태로 진행됩니다. 평소 크리에이터님이 보여주시는 예쁜 감성 그대로 자연스럽게 담아주시면 됩니다! ☺️<br><br>제품 수령을 희망하신다면 [성함/연락처/주소]를 기재하여 편하게 회신 부탁드리겠습니다.<br><br>감사합니다.<br>박혜란 드림"""
        }
    },
    'SOLV': {
        'commerce': {
            'subject': '[제안] 뷰티 브랜드 솔브(SOLV) 커머스 협업 제안드립니다.',
            'body': """안녕하세요 {nickname}님, SOLV 담당자 박혜란입니다.<br><br>평소 올려주시는 콘텐츠를 인상 깊게 보았습니다. 저희 브랜드 솔브(SOLV)와 크리에이터님이 함께 시너지를 낼 수 있는 수익 쉐어형 커머스(공구) 파트너십을 제안드립니다.<br><br><b>[브랜드 및 제품 소개]</b><br>브랜드명: SOLV(솔브)<br>주력 제품: 더블세럼 모델링팩 (물 조절 필요 없는 3초 컷 홈에스테틱)<br>특장점: 쿨링 진정은 물론 완벽한 화잘먹 피부 완성<br>제품 확인하기: <a href='https://solv.co.kr/aboutus/productstory.html'>공식몰 링크</a><br><br>상세 제안서 검토나 미팅 일정을 잡고자 하신다면 편하게 회신 부탁드립니다.<br><br>감사합니다.<br>박혜란 드림"""
        },
        'seeding': {
            'subject': '[협찬] 뷰티 브랜드 솔브(SOLV) 화잘먹 모델링팩 시딩 제안드립니다.',
            'body': """안녕하세요 {nickname}님, SOLV 담당자 박혜란입니다.<br><br>크리에이터님 특유의 맑은 분위기와 저희 브랜드 솔브(SOLV)가 만나면 좋은 시너지가 날 것 같아 제품 시딩(협찬)을 제안드립니다.<br><br><b>제공 제품:</b> 솔브 더블세럼 모델링팩<br>제품 확인하기: <a href='https://solv.co.kr/aboutus/productstory.html'>공식몰 링크</a><br><br>제품 수령을 희망하신다면 [성함/연락처/주소]를 기재하여 편하게 회신 부탁드리겠습니다.<br><br>감사합니다.<br>박혜란 드림"""
        }
    },
    'UPPR': {
        'commerce': {
            'subject': '[제안] 라이프/패션 브랜드 어퍼(UPPR) 커머스 협업 제안드립니다.',
            'body': """안녕하세요 {nickname}님, UPPR 담당자 박혜란입니다.<br><br>저희 브랜드 어퍼(UPPR)의 힙한 무드와 크리에이터님의 핏이 아주 잘 맞을 것 같아 협업을 제안드립니다.<br><br><b>주력 제품:</b> 코듀로이 볼캡 or 시그니처 체크셔츠<br>특장점: 광대와 두상을 완벽하게 커버하는 소두핏 볼캡<br>제품 확인하기: <a href='https://smartstore.naver.com/uppr'>스마트스토어 링크</a><br><br>언제든 편하게 회신 부탁드립니다.<br><br>감사합니다.<br>박혜란 드림"""
        },
        'seeding': {
            'subject': '[협찬] 라이프/패션 브랜드 어퍼(UPPR) 제품 시딩 제안드립니다.',
            'body': """안녕하세요 {nickname}님, UPPR 담당자 박혜란입니다.<br><br>평소 올려주시는 감각적인 데일리룩 코디를 잘 보고 있어 저희 제품을 꼭 한번 경험해 보셨으면 하는 마음에 시딩을 제안드립니다.<br><br><b>제공 제품:</b> UPPR 코듀로이 볼캡 or 오버핏 셔츠<br>제품 확인하기: <a href='https://smartstore.naver.com/uppr'>스마트스토어 링크</a><br><br>원하시는 품목 및 사이즈를 기재하여 회신 부탁드리겠습니다.<br><br>감사합니다.<br>박혜란 드림"""
        }
    }
}

# --- [3. UI 레이아웃] ---
st.set_page_config(page_title="Glowup Rizz 대량 발송기", layout="wide")
tab1, tab2 = st.tabs(["✉️ 메일 발송", "📊 발송 로그"])

# 세션 상태 초기화 (입력값 유지/삭제용)
if 'nick_list' not in st.session_state: st.session_state.nick_list = ""
if 'email_list' not in st.session_state: st.session_state.email_list = ""

with tab1:
    st.title("✉️ 메일 대량 발송 시스템")
    
    col_set1, col_set2, col_set3 = st.columns([1, 1, 1])
    with col_set1:
        selected_platform = st.radio("발송 이메일 선택", ["Gmail", "Naver"], horizontal=True)
    with col_set2:
        brand_choice = st.selectbox("브랜드 선택", ["MELV", "SOLV", "UPPR"])
    with col_set3:
        type_choice = st.selectbox("템플릿 종류", ["commerce", "seeding"], format_func=lambda x: "커머스 제안" if x == "commerce" else "시딩(협찬) 제안")
    
    sender_name = st.text_input("담당자 서명 이름", "박혜란")

    st.divider()

    col_input1, col_input2 = st.columns(2)
    with col_input1:
        st.session_state.nick_list = st.text_area("1. 닉네임 리스트", value=st.session_state.nick_list, height=150, placeholder="줄바꿈으로 구분")
    with col_input2:
        st.session_state.email_list = st.text_area("2. 이메일 리스트", value=st.session_state.email_list, height=150, placeholder="줄바꿈으로 구분")

    nicks = [n.strip() for n in st.session_state.nick_list.split('\n') if n.strip()]
    emails = [e.strip() for e in st.session_state.email_list.split('\n') if e.strip()]
    
    if nicks and emails:
        target_df = pd.DataFrame({"닉네임": nicks, "이메일": emails})
        
        # --- [4. 미리보기] ---
        st.subheader("👀 개인화 미리보기")
        selected_temp = templates[brand_choice][type_choice]
        preview_body = selected_temp['body'].format(nickname=nicks[0])
        
        with st.container(border=True):
            st.markdown(f"**받는 사람:** {nicks[0]} ({emails[0]})")
            st.markdown(f"**제목:** {selected_temp['subject']}")
            st.divider()
            st.markdown(f"<div style='font-size: 14px;'>{preview_body}</div>", unsafe_allow_html=True)
            if os.path.exists(IMAGE_PATH):
                st.image(IMAGE_PATH, width=220, caption="명함 이미지 (Small)")

        # --- [5. 발송 버튼] ---
        if st.button(f"🚀 {len(target_df)}명에게 {selected_platform}로 발송 시작", type="primary", use_container_width=True):
            success_count = 0
            
            # 발송 계정 정보 가져오기
            user_id = st.secrets["GMAIL_USER"] if selected_platform == "Gmail" else st.secrets["NAVER_USER"]
            user_pw = st.secrets["GMAIL_PW"] if selected_platform == "Gmail" else st.secrets["NAVER_PW"]
            server_info = SMTP_SETTINGS[selected_platform]

            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                # 이미지 로드
                img_data = None
                if os.path.exists(IMAGE_PATH):
                    with open(IMAGE_PATH, 'rb') as f: img_data = f.read()

                server = smtplib.SMTP(server_info["host"], server_info["port"])
                server.starttls()
                server.login(user_id, user_pw)

                for i, row in target_df.iterrows():
                    nick, email = row['닉네임'], row['이메일']
                    status_text.text(f"⏳ 발송 중: {nick} ({i+1}/{len(target_df)})")
                    
                    msg = MIMEMultipart('related')
                    msg['From'] = user_id
                    msg['To'] = email
                    msg['Subject'] = selected_temp['subject']
                    msg.add_header('Reply-To', REPLY_TO)

                    # 본문 조립
                    final_html = f"<html><body><p style='line-height:1.6;'>{selected_temp['body'].format(nickname=nick)}</p><br><img src='cid:card' style='width:220px;'></body></html>"
                    msg_alt = MIMEMultipart('alternative')
                    msg.attach(msg_alt)
                    msg_alt.attach(MIMEText(final_html, 'html', 'utf-8'))

                    if img_data:
                        image = MIMEImage(img_data)
                        image.add_header('Content-ID', '<card>')
                        msg.attach(image)

                    try:
                        server.send_message(msg)
                        status = "성공"
                        success_count += 1
                    except Exception as e: status = f"실패: {e}"
                    
                    # DB 로그 기록
                    conn = sqlite3.connect('mail_history.db')
                    conn.execute("INSERT INTO send_log (brand, type, nickname, email, status, sent_at) VALUES (?, ?, ?, ?, ?, ?)",
                                 (brand_choice, type_choice, nick, email, status, datetime.datetime.now().strftime("%y/%m/%d %H:%M")))
                    conn.commit(); conn.close()
                    
                    progress_bar.progress((i + 1) / len(target_df))
                    time.sleep(1)

                server.quit()
                st.success(f"🎉 {success_count}건 발송 성공!")
                
                # 발송 성공 시 입력창 초기화 및 새로고침
                clear_inputs()
                st.rerun()

            except Exception as e:
                st.error(f"❌ 접속 오류: {e}")

# --- [6. 발송 로그] ---
with tab2:
    st.subheader("📊 발송 기록 관리")
    conn = sqlite3.connect('mail_history.db')
    log_df = pd.read_sql_query("SELECT * FROM send_log ORDER BY id DESC", conn)
    conn.close()
    st.dataframe(log_df, use_container_width=True, hide_index=True)
    if st.button("로그 전체 삭제"):
        conn = sqlite3.connect('mail_history.db'); conn.execute("DELETE FROM send_log"); conn.commit(); conn.close()
        st.rerun()
