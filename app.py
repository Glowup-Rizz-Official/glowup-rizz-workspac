import streamlit as st
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from email.utils import formataddr
import pandas as pd
import sqlite3
import datetime
import time
import os

# --- [1. 기본 설정 및 보안] ---
REPLY_TO = "hcommerceinc1@gmail.com"
IMAGE_PATH = "명함.png"

# 브랜드별 PPT 제안서 매칭 (쏙쉐이크 PPT가 있다면 아래에 "SSOK": "파일명.pptx" 로 추가하세요)
PPT_FILES = {
    "MELV": "MELV_커머스_제안서.pptx",
    "SOLV": "SOLV_커머스_제안서.pptx"
}

# 데이터베이스 초기화
def init_db():
    conn = sqlite3.connect('mail_log.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS send_log 
                 (channel_name TEXT, email TEXT, status TEXT, sent_at TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- [2. 템플릿 데이터베이스 (쏙쉐이크 추가)] ---
templates = {
    'MELV': {
        'commerce': {
            'subject': '[제안] 뷰티 브랜드 멜브(MELV) 커머스 협업 제안드립니다.',
            'body': """안녕하세요 {nickname}님, MELV MD 박혜란입니다.

저희 뷰티 브랜드 멜브(MELV)의 제품 무드와 시너지가 날 것 같아 함께 수익 쉐어형 커머스(공구)를 진행하고자 제안드립니다.

[브랜드 및 제품 소개]
브랜드명: MELV(멜브)
주력 제품: 립시럽(맑은 유리알 광택), 립타투(24시간 지속력/뮤티드 컬러/오버립)
성과 지표: 카카오톡 선물하기 뷰티 랭킹 1위 달성, 실사용자 리뷰 및 재구매율 기반 제품력 입증 완료
제품 확인하기
https://a-bly.com/app/markets/108879/

[협업 제안 내용]
협업 형태: 인플루언서 전용 링크를 통한 판매 수익 쉐어 (RS)
플랫폼: 에이블리, 카카오톡 선물하기, 지그재그 등 협의 가능

단순 광고를 넘어 함께 윈윈할 수 있는 커머스 파트너십을 맺고 싶습니다.
관련하여 상세 제안서 검토를 희망하시거나 미팅이 가능하시다면 회신 부탁드립니다.

감사합니다.
박혜란 드림"""
        },
        'seeding': {
            'subject': '[협찬] 뷰티 브랜드 멜브(MELV) 제품 시딩 제안드립니다.',
            'body': """안녕하세요 {nickname}님, MELV MD 박혜란입니다.

크리에이터님의 뷰티 콘텐츠 무드와 저희 브랜드 멜브(MELV)의 결이 정말 잘 어울릴 것 같아, 제품 시딩(협찬)을 제안드리고자 연락드렸습니다.

[브랜드 및 제품 소개]
브랜드명: MELV(멜브)
제공 제품: 립시럽(맑은 광택) & 립타투(24시간 지속/오버립) 베스트 라인업
제품 확인하기
https://a-bly.com/app/markets/108879/

이번 제품 시딩은 직접 사용해 보신 후 인스타그램(피드 또는 릴스)에 1회 업로드해 주시는 형태로 진행됩니다. 
정해진 틀이나 형식에 얽매이기보다는, 평소 크리에이터님이 보여주시는 예쁜 감성 그대로 묻어나지 않는 립타투와 투명한 립시럽의 시너지를 자연스럽게 담아주시면 됩니다! ☺️

또한 업로드해 주실 때 저희 멜브 공식 계정(@melv.kr) 태그와 함께, 전달해 드릴 제품 판매 링크를 기재해 주시면 정말 감사하겠습니다.
제품 사용 후 만족스러우시다면 추후 커머스 등 더 좋은 인연으로도 이어질 수 있기를 기대합니다.

제품 수령을 희망하신다면 [성함/연락처/주소]를 기재하여 편하게 회신 부탁드리겠습니다.

감사합니다.
박혜란 드림"""
        }
    },
    'SOLV': {
        'commerce': {
            'subject': '[제안] 뷰티 브랜드 솔브(SOLV) 커머스 협업 제안드립니다.',
            'body': """안녕하세요 {nickname}님, SOLV 담당자 박혜란입니다.

평소 올려주시는 콘텐츠를 인상 깊게 보았습니다. 저희 브랜드 솔브(SOLV)와 크리에이터님이 함께 시너지를 낼 수 있는 수익 쉐어형 커머스(공구) 파트너십을 제안드립니다.

[브랜드 및 제품 소개]
브랜드명: SOLV(솔브)
주력 제품: 더블세럼 모델링팩 (물 조절 필요 없는 3초 컷 홈에스테틱)
특장점: 쿨링 진정은 물론, 떼어낸 후에도 마르지 않는 윤광 코팅으로 완벽한 화잘먹 피부 완성
제품 확인하기
https://solv.co.kr/aboutus/productstory.html

[협업 제안 내용]
협업 형태: 인플루언서 전용 링크를 통한 판매 수익 쉐어 (RS)
플랫폼: 에이블리, 지그재그 등 협의 가능

단순한 일회성 홍보를 넘어, 상호 윈윈할 수 있는 탄탄한 커머스 파트너십을 구축하고 싶습니다.
상세 제안서 검토나 미팅 일정을 잡고자 하신다면 편하게 회신 부탁드립니다.

감사합니다.
박혜란 드림"""
        },
        'seeding': {
            'subject': '[협찬] 뷰티 브랜드 솔브(SOLV) 화잘먹 모델링팩 시딩 제안드립니다.',
            'body': """안녕하세요 {nickname}님, SOLV 담당자 박혜란입니다.

크리에이터님 특유의 맑은 분위기와 저희 브랜드 솔브(SOLV)가 만나면 좋은 시너지가 날 것 같아 제품 시딩(협찬)을 제안드립니다.

[브랜드 및 제품 소개]
브랜드명: SOLV(솔브)
제공 제품: 솔브 더블세럼 모델링팩 (번거로운 물 조절 없이 1제와 2제 세럼을 섞어 쓰는 아이스 젤리팩)
제품 확인하기
https://solv.co.kr/aboutus/productstory.html

이번 시딩은 제품을 직접 경험해 보시고 인스타그램(피드 또는 릴스)에 1회 업로드해 주시는 일정으로 생각하고 있습니다. 
형식적인 리뷰보다는, 평소 크리에이터님 특유의 무드로 '화잘먹 윤광 코팅' 효과를 일상 속에서 예쁘게 보여주시면 충분합니다. 🩵

더불어, 업로드하실 때 솔브 공식 계정(@solv.kr) 태그와 함께 제품 판매 링크를 걸어주시면 저희에게 정말 큰 힘이 될 것 같습니다!
이번 만남을 시작으로 좋은 인연이 닿아 추후 커머스 등으로 관계를 확장해 나가길 기대합니다.

제품 수령을 희망하신다면 [성함/연락처/주소]를 기재하여 편하게 회신 부탁드리겠습니다.

감사합니다.
박혜란 드림"""
        }
    },
    'UPPR': {
        'commerce': {
            'subject': '[제안] 라이프/패션 브랜드 어퍼(UPPR) 커머스 협업 제안드립니다.',
            'body': """안녕하세요 {nickname}님, UPPR 담당자 박혜란입니다.

저희 브랜드 어퍼(UPPR)의 힙한 무드와 크리에이터님의 핏이 아주 잘 맞을 것 같아, 판매 수익 쉐어형 커머스(공구) 진행을 제안드리고자 연락드렸습니다.

[브랜드 및 제품 소개]
브랜드명: UPPR(어퍼)
주력 제품: 코듀로이 볼캡 or 시그니처 체크셔츠
특장점: 광대와 두상을 완벽하게 커버하는 소두핏 볼캡과, 볼캡과 찰떡궁합인 오버핏 셔츠로 감각적인 꾸안꾸 스타일링 완성
제품 확인하기
https://smartstore.naver.com/uppr

[협업 제안 내용]
협업 형태: 판매 링크를 통한 판매 수익 쉐어 (RS)
플랫폼: 네이버 쇼핑 커넥트 (에이블리, 지그재그 등도 협의 가능)

크리에이터님과 함께 성공적인 판매 레퍼런스를 만들어가고 싶습니다.
관련하여 상세 제안서 확인이 필요하시거나 논의할 부분이 있으시다면 언제든 회신 부탁드립니다.

감사합니다.
박혜란 드림"""
        },
        'seeding': {
            'subject': '[협찬] 라이프/패션 브랜드 어퍼(UPPR) 제품 시딩 제안드립니다.',
            'body': """안녕하세요 {nickname}님, UPPR 담당자 박혜란입니다.

평소 올려주시는 감각적인 데일리룩 코디를 잘 보고 있어, 저희 어퍼(UPPR) 브랜드의 제품을 꼭 한번 경험해 보셨으면 하는 마음에 시딩(협찬)을 제안드립니다.

[브랜드 및 제품 소개]
브랜드명: UPPR(어퍼)
제공 제품: UPPR 코듀로이 볼캡 (얼굴형 완벽 커버) or 시그니처 체크셔츠 (오버핏)
제품 확인하기
https://smartstore.naver.com/uppr

이번 협찬은 제품 착용 후 인스타그램(피드 또는 릴스)에 1회 업로드해 주시는 형태로 진행하고자 합니다. 
딱딱한 리뷰 형식보다는, 평소 크리에이터님이 즐겨 입으시는 데일리룩에 가볍게 툭 매치해서 힙하고 편안한 꾸안꾸룩으로 연출해 주시면 정말 좋을 것 같아요! 🧢

게시물 작성 시 저희 어퍼 공식 계정(@uppr_official) 태그와 함께 전달해 드릴 제품 판매 링크도 같이 남겨주시면 정말 감사하겠습니다.
만족스러운 핏을 경험하셨다면 추후 더 큰 비즈니스 협업으로도 이어질 수 있기를 희망합니다.

제품 수령을 원하신다면 [성함/연락처/주소]와 함께 [원하시는 품목(코듀로이 볼캡 또는 시그니처 체크셔츠) 및 사이즈]를 기재하여 편하게 회신 부탁드리겠습니다.

감사합니다.
박혜란 드림"""
        }
    },
    'SSOK': {
        'commerce': {
            'subject': "[쏙쉐이크] '속세의 맛' 다이어트 쉐이크 커머스 제안 드립니다.",
            'body': """안녕하세요 {nickname}님,
쏙쉐이크 담당자 박혜란입니다.

평소 크리에이터님의 건강하고 긍정적인 라이프스타일을 즐겨 보고 있었습니다. 저희 브랜드가 추구하는 ‘지속 가능한 다이어트’의 방향성과 시너지가 크게 날 것 같아, 수익 쉐어형 커머스(공구)를 제안드리고자 연락드렸습니다.

[브랜드 및 제품 소개]
브랜드명: 쏙쉐이크
주력 제품: 진짜 속세의 맛을 구현한 고단백 쉐이크 (단백질 20g 함유)
제품 소구점: 
* 비린맛/텁텁함 ZERO: 영양성분이 좋으면 맛이 없다는 편견을 깨기 위해 1년간 수십 차례 테스트하여 완성한 진짜 간식 같은 맛
* 압도적인 포만감: 토핑을 아끼지 않아 물에 타 먹어도 묽지 않고 한 잔만으로 배부른 한 끼 대용식
* 입터짐 완벽 방지: 초콜릿, 디저트가 생각날 때 대체 가능한 달콤함으로 요요 없는 다이어트 루틴 형성

[협업 제안 내용]
협업 형태: 인플루언서 전용 링크를 통한 판매 수익 쉐어 (RS)
특별 혜택: 첫 런칭 기념 한정 수량 무료배송 프로모션 지원 가능 (팬분들의 구매 전환율 극대화)
플랫폼: 자사몰, 스마트스토어 등 협의 가능

단순히 1회성으로 소비되는 광고를 넘어, 크리에이터님과 팬분들 모두 만족하고 윈윈할 수 있는 커머스 파트너십을 맺고 싶습니다.
관련하여 상세 제안서 검토를 희망하시거나 미팅이 가능하시다면 회신 부탁드립니다.

감사합니다.
박혜란 드림"""
        },
        'seeding': {
            'subject': "[쏙쉐이크] 식단 관리의 신세계, 속세맛 쉐이크 시딩 제안 드립니다.",
            'body': """안녕하세요 {nickname}님!
쏙쉐이크 담당자 박혜란입니다. :)

평소 크리에이터님의 콘텐츠를 보며 특유의 매력적인 분위기에 팬이 되었습니다. 저희 브랜드가 지향하는 이미지와 너무 잘 어우러지실 것 같아, 이번 런칭 제품을 가장 먼저 보내드리고 싶어 연락드렸습니다.

[시딩 제품: 쏙쉐이크 본품 세트]
* 배고프고 맛없는 다이어트는 그만: 한 통 사놓고 3일 만에 질려서 포기하던 기존 쉐이크의 텁텁함과 비린맛을 완벽하게 잡았습니다.
* 씹는 맛이 살아있는 든든함: 토핑을 아끼지 않아 물에 타도 진하고, 한 잔만으로 한 끼 대용이 가능합니다. (단백질 20g, 하루 권장량 36% 충족)
* 죄책감 없는 속세의 맛: 초코, 과자 대신 먹어도 충족되는 달콤함으로 입터짐을 막아줍니다.

제품 받아보시고 크리에이터님만의 감성으로 인스타그램(또는 유튜브)에 가볍게 노출만 부탁드리고 싶습니다. :)
혹시 단순 시딩 외에도 전용 링크를 통한 수익 쉐어형(RS) 협업에도 관심이 있으시다면 언제든 말씀해 주세요.

진행이 가능하시다면 받아보실 **[성함 / 연락처 / 주소]**를 남겨주세요. 예쁘게 포장해서 넉넉히 보내드리겠습니다.

궁금하신 사항 있으시면 편하게 문의 부탁드립니다.

감사합니다!
박혜란 드림"""
        }
    }
}

# --- [3. UI 레이아웃] ---
st.set_page_config(page_title="Glowup Rizz 대량 발송기", layout="wide")
tab1, tab2 = st.tabs(["✉️ 메일 발송", "📊 발송 로그"])

if 'n_input' not in st.session_state: st.session_state.n_input = ""
if 'e_input' not in st.session_state: st.session_state.e_input = ""

with tab1:
    st.title("✉️ 초개인화 대량 발송 시스템")
    
    col1, col2, col3 = st.columns(3)
    with col1: platform = st.radio("발송 계정 선택", ["Gmail", "Naver"], horizontal=True)
    with col2: brand_choice = st.selectbox("브랜드 선택", ["MELV", "SOLV", "UPPR", "SSOK"])
    with col3: type_choice = st.selectbox("템플릿 종류", ["commerce", "seeding"], format_func=lambda x: "커머스 제안" if x == "commerce" else "시딩 제안")
    
    sender_name = st.text_input("담당자 서명 이름", "박혜란")

    st.divider()

    ci1, ci2 = st.columns(2)
    with ci1: st.session_state.n_input = st.text_area("1. 닉네임 리스트 (줄바꿈 구분)", value=st.session_state.n_input, height=180)
    with ci2: st.session_state.e_input = st.text_area("2. 이메일 리스트 (줄바꿈 구분)", value=st.session_state.e_input, height=180)

    nicks = [n.strip() for n in st.session_state.n_input.split('\n') if n.strip()]
    emails = [e.strip() for e in st.session_state.e_input.split('\n') if e.strip()]
    
    if nicks and emails:
        st.subheader("👀 실시간 미리보기")
        s_temp = templates[brand_choice][type_choice]
        
        # 줄바꿈(\n)을 HTML 태그(<br>)로 완벽하게 치환
        p_body = s_temp['body'].format(nickname=nicks[0]).replace('\n', '<br>')
        
        with st.container(border=True):
            st.markdown(f"**제목:** {s_temp['subject']}")
            if type_choice == 'commerce' and brand_choice in PPT_FILES:
                st.info(f"📎 첨부 예정 파일: {PPT_FILES[brand_choice]}")
            st.divider()
            st.markdown(f"<div style='font-size: 14px; line-height: 1.6;'>{p_body}</div>", unsafe_allow_html=True)
            if os.path.exists(IMAGE_PATH): st.image(IMAGE_PATH, width=230)

        if st.button(f"🚀 {len(nicks)}명에게 일괄 발송 시작", type="primary", use_container_width=True):
            user_id = st.secrets["GMAIL_USER"] if platform == "Gmail" else st.secrets["NAVER_USER"]
            user_pw = st.secrets["GMAIL_PW"] if platform == "Gmail" else st.secrets["NAVER_PW"]
            
            progress = st.progress(0)
            status_text = st.empty()
            success_count = 0

            try:
                img_data, f_ext = None, "png"
                if os.path.exists(IMAGE_PATH):
                    with open(IMAGE_PATH, 'rb') as f: img_data = f.read()
                    f_ext = os.path.splitext(IMAGE_PATH)[1][1:].lower()
                    if f_ext == 'jpg': f_ext = 'jpeg'

                for i, (nick, email) in enumerate(zip(nicks, emails)):
                    status_text.text(f"⏳ 발송 중: {nick} ({i+1}/{len(nicks)})")
                    
                    if platform == "Naver":
                        server = smtplib.SMTP_SSL("smtp.naver.com", 465)
                    else:
                        server = smtplib.SMTP("smtp.gmail.com", 587)
                        server.starttls()
                    
                    server.login(user_id, user_pw)

                    msg = MIMEMultipart('related')
                    
                    # RFC-5322 오류 완벽 방지: formataddr 사용
                    msg['From'] = formataddr((sender_name, user_id))
                    msg['To'] = email
                    msg['Subject'] = s_temp['subject']
                    msg.add_header('Reply-To', REPLY_TO)

                    # 전송되는 메일 본문에도 줄바꿈 태그 완벽 적용
                    final_body = s_temp['body'].format(nickname=nick).replace('\n', '<br>')
                    f_html = f"<html><body><div style='font-family:sans-serif; font-size:14px; line-height:1.6;'>{final_body}</div><br><img src='cid:card' style='width:230px;'></body></html>"
                    
                    msg_alt = MIMEMultipart('alternative')
                    msg.attach(msg_alt)
                    msg_alt.attach(MIMEText(f_html, 'html', 'utf-8'))

                    if img_data:
                        image = MIMEImage(img_data, _subtype=f_ext)
                        image.add_header('Content-ID', '<card>')
                        msg.attach(image)

                    # PPT 첨부 로직
                    if type_choice == 'commerce' and brand_choice in PPT_FILES:
                        ppt_path = PPT_FILES[brand_choice]
                        if os.path.exists(ppt_path):
                            with open(ppt_path, "rb") as f:
                                part = MIMEApplication(f.read(), Name=os.path.basename(ppt_path))
                                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(ppt_path)}"'
                                msg.attach(part)

                    server.send_message(msg)
                    server.quit()
                    success_count += 1
                    
                    conn = sqlite3.connect('mail_log.db')
                    conn.execute("INSERT INTO send_log (channel_name, email, status, sent_at) VALUES (?, ?, ?, ?)",
                                 (nick, email, "성공", datetime.datetime.now().strftime("%y/%m/%d %H:%M")))
                    conn.commit()
                    conn.close()
                    
                    progress.progress((i + 1) / len(nicks))
                    time.sleep(1.5)

                st.success(f"🎉 총 {success_count}건 발송 성공!")
                st.session_state.n_input = ""
                st.session_state.e_input = ""
                time.sleep(1)
                st.rerun()

            except Exception as e:
                st.error(f"❌ 오류 발생: {e}")

with tab2:
    st.subheader("📊 발송 로그")
    conn = sqlite3.connect('mail_log.db')
    log_df = pd.read_sql_query("SELECT * FROM send_log ORDER BY sent_at DESC", conn)
    conn.close()
    st.dataframe(log_df, use_container_width=True, hide_index=True)
