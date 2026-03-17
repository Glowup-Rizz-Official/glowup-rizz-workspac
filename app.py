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
EMAIL_USER = st.secrets["EMAIL_USER"]
EMAIL_PW = st.secrets["EMAIL_PW"]
REPLY_TO = "hcommerceinc1@gmail.com"
IMAGE_PATH = "명함.png" # 파일 이름을 '명함.png'로 해서 같은 폴더에 두세요.

# 데이터베이스 설정 (발송 로그 저장용)
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
            'body': """안녕하세요 {nickname}님, MELV MD 박혜란입니다.<br><br>저희 뷰티 브랜드 멜브(MELV)의 제품 무드와 시너지가 날 것 같아 함께 수익 쉐어형 커머스(공구)를 진행하고자 제안드립니다.<br><br><b>[브랜드 및 제품 소개]</b><br>브랜드명: MELV(멜브)<br>주력 제품: 립시럽(맑은 유리알 광택), 립타투(24시간 지속력/뮤티드 컬러/오버립)<br>성과 지표: 카카오톡 선물하기 뷰티 랭킹 1위 달성, 실사용자 리뷰 및 재구매율 기반 제품력 입증 완료<br>제품 확인하기: <a href='https://a-bly.com/app/markets/108879/'>에이블리 링크</a><br><br><b>[협업 제안 내용]</b><br>협업 형태: 인플루언서 전용 링크를 통한 판매 수익 쉐어 (RS)<br>플랫폼: 에이블리, 카카오톡 선물하기, 지그재그 등 협의 가능<br><br>단순 광고를 넘어 함께 윈윈할 수 있는 커머스 파트너십을 맺고 싶습니다.<br>관련하여 상세 제안서 검토를 희망하시거나 미팅이 가능하시다면 회신 부탁드립니다.<br><br>감사합니다.<br>박혜란 드림"""
        },
        'seeding': {
            'subject': '[협찬] 뷰티 브랜드 멜브(MELV) 제품 시딩 제안드립니다.',
            'body': """안녕하세요 {nickname}님, MELV MD 박혜란입니다.<br><br>크리에이터님의 뷰티 콘텐츠 무드와 저희 브랜드 멜브(MELV)의 결이 정말 잘 어울릴 것 같아, 제품 시딩(협찬)을 제안드리고자 연락드렸습니다.<br><br><b>[브랜드 및 제품 소개]</b><br>브랜드명: MELV(멜브)<br>제공 제품: 립시럽(맑은 광택) & 립타투(24시간 지속/오버립) 베스트 라인업<br>제품 확인하기: <a href='https://a-bly.com/app/markets/108879/'>에이블리 링크</a><br><br>이번 제품 시딩은 직접 사용해 보신 후 인스타그램(피드 또는 릴스)에 1회 업로드해 주시는 형태로 진행됩니다. 정해진 틀이나 형식에 얽매이기보다는, 평소 크리에이터님이 보여주시는 예쁜 감성 그대로 묻어나지 않는 립타투와 투명한 립시럽의 시너지를 자연스럽게 담아주시면 됩니다! ☺️<br><br>또한 업로드해 주실 때 저희 멜브 공식 계정(@melv.kr) 태그와 함께, 전달해 드릴 제품 판매 링크를 기재해 주시면 정말 감사하겠습니다.<br>제품 수령을 희망하신다면 [성함/연락처/주소]를 기재하여 편하게 회신 부탁드리겠습니다.<br><br>감사합니다.<br>박혜란 드림"""
        }
    },
    'SOLV': {
        'commerce': {
            'subject': '[제안] 뷰티 브랜드 솔브(SOLV) 커머스 협업 제안드립니다.',
            'body': """안녕하세요 {nickname}님, SOLV 담당자 박혜란입니다.<br><br>평소 올려주시는 콘텐츠를 인상 깊게 보았습니다. 저희 브랜드 솔브(SOLV)와 크리에이터님이 함께 시너지를 낼 수 있는 수익 쉐어형 커머스(공구) 파트너십을 제안드립니다.<br><br><b>[브랜드 및 제품 소개]</b><br>브랜드명: SOLV(솔브)<br>주력 제품: 더블세럼 모델링팩 (물 조절 필요 없는 3초 컷 홈에스테틱)<br>특장점: 쿨링 진정은 물론, 떼어낸 후에도 마르지 않는 윤광 코팅으로 완벽한 화잘먹 피부 완성<br>제품 확인하기: <a href='https://solv.co.kr/aboutus/productstory.html'>공식몰 링크</a><br><br>상호 윈윈할 수 있는 탄탄한 커머스 파트너십을 구축하고 싶습니다.<br>상세 제안서 검토나 미팅 일정을 잡고자 하신다면 편하게 회신 부탁드립니다.<br><br>감사합니다.<br>박혜란 드림"""
        },
        'seeding': {
            'subject': '[협찬] 뷰티 브랜드 솔브(SOLV) 화잘먹 모델링팩 시딩 제안드립니다.',
            'body': """안녕하세요 {nickname}님, SOLV 담당자 박혜란입니다.<br><br>크리에이터님 특유의 맑은 분위기와 저희 브랜드 솔브(SOLV)가 만나면 좋은 시너지가 날 것 같아 제품 시딩(협찬)을 제안드립니다.<br><br><b>[브랜드 및 제품 소개]</b><br>브랜드명: SOLV(솔브)<br>제공 제품: 솔브 더블세럼 모델링팩 (번거로운 물 조절 없이 1제와 2제 세럼을 섞어 쓰는 아이스 젤리팩)<br>제품 확인하기: <a href='https://solv.co.kr/aboutus/productstory.html'>공식몰 링크</a><br><br>평소 크리에이터님 특유의 무드로 '화잘먹 윤광 코팅' 효과를 일상 속에서 예쁘게 보여주시면 충분합니다. 🩵<br>제품 수령을 희망하신다면 [성함/연락처/주소]를 기재하여 편하게 회신 부탁드리겠습니다.<br><br>감사합니다.<br>박혜란 드림"""
        }
    },
    'UPPR': {
        'commerce': {
            'subject': '[제안] 라이프/패션 브랜드 어퍼(UPPR) 커머스 협업 제안드립니다.',
            'body': """안녕하세요 {nickname}님, UPPR 담당자 박혜란입니다.<br><br>저희 브랜드 어퍼(UPPR)의 힙한 무드와 크리에이터님의 핏이 아주 잘 맞을 것 같아, 판매 수익 쉐어형 커머스(공구) 진행을 제안드리고자 연락드렸습니다.<br><br><b>[브랜드 및 제품 소개]</b><br>브랜드명: UPPR(어퍼)<br>주력 제품: 코듀로이 볼캡 or 시그니처 체크셔츠<br>특장점: 광대와 두상을 완벽하게 커버하는 소두핏 볼캡과 오버핏 셔츠로 감각적인 꾸안꾸 스타일링 완성<br>제품 확인하기: <a href='https://smartstore.naver.com/uppr'>스마트스토어 링크</a><br><br>관련하여 상세 제안서 확인이 필요하시거나 논의할 부분이 있으시다면 언제든 회신 부탁드립니다.<br><br>감사합니다.<br>박혜란 드림"""
        },
        'seeding': {
            'subject': '[협찬] 라이프/패션 브랜드 어퍼(UPPR) 제품 시딩 제안드립니다.',
            'body': """안녕하세요 {nickname}님, UPPR 담당자 박혜란입니다.<br><br>평소 올려주시는 감각적인 데일리룩 코디를 잘 보고 있어, 저희 어퍼(UPPR) 브랜드의 제품을 꼭 한번 경험해 보셨으면 하는 마음에 시딩(협찬)을 제안드립니다.<br><br><b>[브랜드 및 제품 소개]</b><br>브랜드명: UPPR(어퍼)<br>제공 제품: UPPR 코듀로이 볼캡 (얼굴형 완벽 커버) or 시그니처 체크셔츠 (오버핏)<br>제품 확인하기: <a href='https://smartstore.naver.com/uppr'>스마트스토어 링크</a><br><br>평소 크리에이터님이 즐겨 입으시는 데일리룩에 가볍게 툭 매치해서 힙하고 편안한 꾸안꾸룩으로 연출해 주시면 정말 좋을 것 같아요! 🧢<br>제품 수령을 원하신다면 [성함/연락처/주소]와 함께 [원하시는 품목 및 사이즈]를 기재하여 회신 부탁드리겠습니다.<br><br>감사합니다.<br>박혜란 드림"""
        }
    }
}

# --- [3. UI 레이아웃] ---
st.set_page_config(page_title="Glowup Rizz 대량 발송기", layout="wide")
tab1, tab2 = st.tabs(["✉️ 메일 발송", "📊 발송 로그"])

with tab1:
    st.title("✉️ 초개인화 대량 발송 시스템")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        brand_choice = st.selectbox("브랜드 선택", ["MELV", "SOLV", "UPPR"])
        type_choice = st.selectbox("템플릿 종류", ["commerce", "seeding"], format_func=lambda x: "커머스 제안" if x == "commerce" else "시딩(협찬) 제안")
    
    with col2:
        sender_name = st.text_input("담당자 서명 이름", "박혜란")
        st.caption("※ '명함.png' 파일이 같은 폴더에 있어야 이미지가 첨부됩니다.")

    st.divider()

    # 입력 칸 (복붙용)
    col_input1, col_input2 = st.columns(2)
    with col_input1:
        nick_input = st.text_area("1. 닉네임/채널명 리스트 (줄바꿈으로 구분)", height=200, placeholder="박혜란\n김철수\n최영희...")
    with col_input2:
        email_input = st.text_area("2. 이메일 주소 리스트 (줄바꿈으로 구분)", height=200, placeholder="rizzsender@gmail.com\ntest@naver.com...")

    # 데이터 매칭 확인
    nicks = [n.strip() for n in nick_input.split('\n') if n.strip()]
    emails = [e.strip() for e in email_input.split('\n') if e.strip()]
    
    if nicks and emails:
        if len(nicks) != len(emails):
            st.warning(f"⚠️ 닉네임({len(nicks)}개)과 이메일({len(emails)}개)의 개수가 맞지 않습니다! 순서대로 매칭되니 확인해주세요.")
        
        target_df = pd.DataFrame({"닉네임": nicks, "이메일": emails})
        
        # --- [4. 미리보기 섹션] ---
        st.divider()
        st.subheader("👀 발송 미리보기 (첫 번째 대상 기준)")
        
        sample_nick = nicks[0]
        sample_email = emails[0]
        selected_temp = templates[brand_choice][type_choice]
        preview_subject = selected_temp['subject']
        preview_body = selected_temp['body'].format(nickname=sample_nick)

        with st.container(border=True):
            st.markdown(f"**받는 사람:** {sample_nick} ({sample_email})")
            st.markdown(f"**제목:** {preview_subject}")
            st.divider()
            st.markdown(f"<div style='font-family: sans-serif; font-size: 14px;'>{preview_body}</div>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            # 이미지 미리보기 (Small 사이즈로 제한)
            if os.path.exists(IMAGE_PATH):
                st.image(IMAGE_PATH, width=250, caption="첨부될 명함 이미지 (Small)")
            else:
                st.error("⚠️ '명함.png' 파일을 찾을 수 없습니다.")

        # --- [5. 발송 버튼 및 로직] ---
        if st.button(f"🚀 {len(target_df)}명에게 메일 일괄 전송 시작", type="primary", use_container_width=True):
            success_count = 0
            fail_count = 0
            
            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                # 이미지 데이터 읽기
                img_data = None
                file_ext = "png"
                if os.path.exists(IMAGE_PATH):
                    with open(IMAGE_PATH, 'rb') as f:
                        img_data = f.read()
                    file_ext = os.path.splitext(IMAGE_PATH)[1][1:].lower()

                # SMTP 연결
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(EMAIL_USER, EMAIL_PW)

                for i, row in target_df.iterrows():
                    nick = row['닉네임']
                    email = row['이메일']
                    
                    status_text.text(f"⏳ 발송 중: {nick} ({i+1}/{len(target_df)})")
                    
                    # 메일 생성
                    msg = MIMEMultipart('related')
                    msg['From'] = EMAIL_USER
                    msg['To'] = email
                    msg['Subject'] = preview_subject
                    msg.add_header('Reply-To', REPLY_TO)

                    msg_alt = MIMEMultipart('alternative')
                    msg.attach(msg_alt)
                    
                    # 개인화된 본문
                    final_body = selected_temp['body'].format(nickname=nick)
                    html_content = f"""
                    <html><body>
                        <p style="font-family: sans-serif; font-size: 14px; line-height: 1.6; color: #333333;">{final_body}</p>
                        <br><img src="cid:business_card" style="width: 250px; height: auto;">
                    </body></html>
                    """
                    msg_alt.attach(MIMEText(html_content, 'html', 'utf-8'))

                    # 이미지 첨부
                    if img_data:
                        image = MIMEImage(img_data, _subtype=file_ext)
                        image.add_header('Content-ID', '<business_card>')
                        image.add_header('Content-Disposition', 'inline', filename="card.png")
                        msg.attach(image)

                    # 전송 및 DB 저장
                    try:
                        server.send_message(msg)
                        status = "성공"
                        success_count += 1
                    except Exception as e:
                        status = f"실패: {e}"
                        fail_count += 1
                    
                    # 로그 저장
                    conn = sqlite3.connect('mail_history.db')
                    conn.execute("INSERT INTO send_log (brand, type, nickname, email, status, sent_at) VALUES (?, ?, ?, ?, ?, ?)",
                                 (brand_choice, type_choice, nick, email, status, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    conn.close()

                    progress_bar.progress((i + 1) / len(target_df))
                    time.sleep(1) # 스팸 방지용 대기

                server.quit()
                st.success(f"✅ 발송 완료! (성공: {success_count}건 / 실패: {fail_count}건)")
                st.balloons()

            except Exception as e:
                st.error(f"❌ SMTP 연결 오류: {e}")

# --- [6. 발송 로그 탭] ---
with tab2:
    st.subheader("📅 최근 발송 기록")
    if st.button("🔄 로그 새로고침"):
        st.rerun()

    conn = sqlite3.connect('mail_history.db')
    log_df = pd.read_sql_query("SELECT * FROM send_log ORDER BY id DESC", conn)
    conn.close()

    if not log_df.empty:
        st.dataframe(log_df, use_container_width=True)
        
        # 로그 초기화 버튼
        if st.button("🗑️ 전체 로그 삭제"):
            conn = sqlite3.connect('mail_history.db')
            conn.execute("DELETE FROM send_log")
            conn.commit()
            conn.close()
            st.success("로그가 초기화되었습니다.")
            st.rerun()
    else:
        st.info("아직 발송 기록이 없습니다.")
