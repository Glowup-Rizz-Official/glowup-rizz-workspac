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

# --- [2. 템플릿 데이터베이스] ---
templates = {
    'MELV': {
        'commerce': {
            'subject': '[제안] 카카오 선물하기 1위 MELV, 크리에이터님을 위한 수익 쉐어형(RS) 파트너십 제안',
            'body': """안녕하세요 {nickname}님
뷰티 브랜드 MELV(멜브) MD 박혜란입니다.

평소 {nickname}님께서 보여주시는 감각적인 뷰티 무드가 저희 멜브 제품과 잘 어울릴 것 같아, 함께 해보면 좋을 것 같아 연락드렸습니다.

[브랜드 및 제품 경쟁력]
저희 멜브는 '카카오톡 선물하기 뷰티 랭킹 1위'를 달성한 브랜드로, 실제 구매로 이어지는 비율이 데이터로도 확인되고 있습니다.

- 주력 제품: 립시럽(맑은 유리알 광택), 립타투(24시간 지속력/뮤티드 컬러/오버립)
- 제품 확인: https://a-bly.com/app/markets/108879/

[협업 제안 내용]
검증된 제품인 만큼, {nickname}님과 전용 링크를 통한 판매 수익 쉐어(RS) 공동구매를 진행하고 싶습니다.

혹시 일정상 본격적인 공동구매가 부담스러우시다면, 인스타그램 프로필이나 게시물 하단에 '단독 최저가 링크'만 가볍게 걸어두시는 방식도 괜찮습니다. 쿠팡 파트너스처럼 운영하시되, 브랜드 직영이라 수수료율은 더 높게 드리고 있어요. 콘텐츠 무드는 그대로 유지하시면서 1위 제품의 실질적인 수익을 챙기실 수 있는 구조입니다. :)

수수료율 등 궁금하신 점 있으시면 편하게 회신 주세요.
감사합니다.
박혜란 드림"""
        },
        'seeding': {
            'subject': '[협찬] 카카오 1위 멜브(MELV) 립타투&시럽 전 컬러 키트 시딩 제안드립니다.',
            'body': """안녕하세요! {nickname}님,
뷰티 브랜드 MELV(멜브) MD 박혜란입니다. :)

평소 {nickname}님 콘텐츠 잘 보고 있었는데요, 저희 브랜드 분위기랑 잘 맞을 것 같아서 제품을 꼭 한번 보내드리고 싶었어요.

[시딩 제공 제품: 카카오 선물하기 1위 달성템]

- MELV 립시럽 (2종): 끈적임 없는 맑은 광택과 깊은 보습감
- MELV 립타투 (3종): 뮤티드 컬러로 입술에 착 붙는 강력한 지속력
- https://a-bly.com/app/markets/108879/

제품 받아보시고 {nickname}님만의 감성으로 인스타그램에 게시물/릴스를 1회 가볍게 올려주시는 방식입니다. 전 컬러 빠짐없이 꽉 채워서 보내드릴게요.

업로드하실 때 팔로워분들이 궁금해하실 것 같아서 '전용 최저가 수익 링크'도 같이 드릴 수 있어요. 본문이나 프로필에 링크만 걸어두시면 쿠팡 파트너스보다 훨씬 높은 브랜드 직영 수수료를 정산해 드립니다. 올리시는 콘텐츠에 실질적인 수익도 같이 챙겨가셨으면 좋겠습니다. :)

진행 가능하시면 [성함 / 연락처 / 주소] 남겨주세요. 정성껏 포장해서 보내드리겠습니다.
감사합니다!
박혜란 드림"""
        }
    },
    'SOLV': {
        'commerce': {
            'subject': '[제안] 1만 개 완판 대란템 솔브(SOLV), 수익 쉐어형 커머스 파트너십 제안드립니다.',
            'body': """안녕하세요 {nickname}님,
기초 뷰티 브랜드 SOLV(솔브) MD 박혜란입니다.

{nickname}님의 맑은 뷰티 무드를 인상 깊게 보다가, 저희 솔브랑 잘 맞을 것 같아 연락드렸습니다.

[브랜드 및 제품 경쟁력]
저희 '솔브 더블세럼 모델링팩'은 론칭 후 입소문만으로 1만 개가 완판되어, 현재는 대기 예약으로 판매되고 있는 제품이에요.

- 특장점: 물 조절 필요 없는 3초 컷 홈에스테틱, 화잘먹 윤광 코팅
- 제품 확인: https://solv.co.kr/aboutus/productstory.html

[협업 제안 내용]
실제 수요가 확인된 제품인 만큼, {nickname}님과 전용 링크를 통한 수익 쉐어(RS) 방식의 공동구매를 먼저 제안드리고 싶습니다.

다만 일정상 본격적인 공구가 부담스러우시다면, 인스타그램 프로필이나 게시물 하단에 '단독 최저가 링크'만 걸어두시는 방식도 함께 제안드려요.

쿠팡 파트너스랑 운영 방식은 같은데, 본사 직영이라 수수료율이 더 높습니다. 완판된 이력이 있는 제품이다 보니 링크 하나만으로도 콘텐츠 무드 해치지 않고 실질적인 수익을 가져가실 수 있어요. :)

궁금하신 부분 있으시면 편하게 회신 부탁드립니다.
감사합니다.
박혜란 드림"""
        },
        'seeding': {
            'subject': '[협찬] 1만 개 완판템 솔브(SOLV) 화잘먹 모델링팩 제품 시딩 제안드립니다.',
            'body': """안녕하세요 {nickname}님,
SOLV 담당자 박혜란입니다.

{nickname}님 특유의 맑은 분위기와 피부결을 보다가 저희 솔브(SOLV)랑 정말 잘 어울리겠다 싶어서 연락드렸어요.

[제공 제품: 1만 개 전량 완판 대란템]
1차 물량은 전량 완판되어 지금은 예약 판매로 진행할 정도로 반응이 좋은 제품이에요. {nickname}님을 위해 넉넉하게 준비해 드릴게요.

- 솔브 더블세럼 모델링팩: 물 조절 없이 1제와 2제 세럼을 섞어 쓰는 시원한 쿨링 젤리팩
- https://solv.co.kr/aboutus/productstory.html

이번 시딩은 제품 직접 써보시고, 인스타그램(피드 또는 릴스)에 판매 링크 삽입, 솔브 계정(@solv.kr) 태그와 함께 1회 가볍게 올려주시는 방식이에요. 🩵

업로드하실 때 '전용 최저가 수익 링크'도 함께 드릴 수 있어요. 프로필이나 본문에 링크만 걸어두시면 쿠팡보다 높은 브랜드 직영 수수료를 정산해 드립니다. 올리시는 콘텐츠에 실질적인 리워드도 꼭 챙겨가셨으면 해서요. :)

제품 받아보고 싶으시면 [성함/연락처/주소] 편하게 남겨주세요.
감사합니다.
박혜란 드림"""
        }
    },
    'UPPR': {
        'commerce': {
            'subject': '[제안] 독보적인 핏의 OOTD, 패션 브랜드 어퍼(UPPR) 수익 쉐어 파트너십 제안드립니다.',
            'body': """안녕하세요 {nickname}님,
패션 브랜드 어퍼(UPPR) MD 박혜란입니다.

평소 보여주시는 아웃핏이랑 스타일링이 정말 좋아서, 저희 브랜드랑 잘 맞을 것 같아 연락드렸습니다.

[브랜드 및 제품 경쟁력]
저희 어퍼(UPPR) 주력 제품들은 패션에 관심 많은 분들 사이에서 '핏 보장템'으로 불리며 실제 구매 전환율도 좋은 편이에요.

- 볼캡: 광대와 두상을 커버해 주는 소두핏 연출
- 시그니처 체크셔츠: 볼캡과 잘 어울리는 감각적인 오버핏 꾸안꾸룩
- 골반뽕 부츠컷 데님팬츠: 골반라인 살려주는 부츠컷 데님팬츠
- 제품 확인: https://smartstore.naver.com/uppr

[협업 제안 내용]
{nickname}님 데일리룩에 저희 제품을 자연스럽게 녹여내서, 전용 판매 링크를 통한 수익 쉐어(RS) 커머스를 같이 해보고 싶어요. 핏이 좋으셔서 팔로워분들 반응도 좋을 것 같아요.

캘린더 일정상 공동구매가 부담스러우시다면, 인스타그램 프로필 링크나 게시물 하단에 '단독 최저가 링크'만 걸어두시는 방식도 괜찮아요.

쿠팡 파트너스랑 운영 방식은 동일한데, 브랜드 직영이라 수수료율이 더 높습니다. '소정의 수수료를 제공받을 수 있음' 문구만 적어주시면, 평소 콘텐츠 무드 그대로 유지하시면서 판매 수익도 챙기실 수 있어요. :)

수수료율이나 진행 방식 등 논의할 부분 있으시면 편하게 회신 주세요.
감사합니다.
박혜란 드림"""
        },
        'seeding': {
            'subject': '[협찬] {nickname}님의 힙한 데일리룩을 위한 어퍼(UPPR) 특별 시딩 제안드립니다.',
            'body': """안녕하세요 {nickname}님,
패션 브랜드 UPPR(어퍼) MD 박혜란입니다.

평소 올려주시는 데일리룩 보면서, 저희 어퍼(UPPR) 제품을 {nickname}님 스타일로 소화해 주시면 정말 잘 어울리겠다 싶어서 연락드렸어요.

[제공 제품: 어퍼 시그니처 아이템]
{nickname}님 핏을 더 돋보이게 해 줄 아이템을 선물로 보내드릴게요.

- UPPR 제품 중 원하시는 제품 선물
- 제품 확인: https://a-bly.com/app/markets/107175/

제품 착용하시고 인스타그램(피드 또는 릴스)에 판매 링크 삽입, 공식 계정(@uppr_official) 태그와 함께 1회 올려주시는 방식이에요. 딱딱한 리뷰 형식은 전혀 필요 없고요, 평소 즐겨 입으시는 옷에 저희 제품 가볍게 툭 매치해서 꾸안꾸룩으로 보여주시면 충분해요.

업로드하실 때 팔로워분들을 위한 '전용 최저가 수익 링크'도 같이 드릴 수 있어요. 쿠팡 파트너스처럼 프로필이나 본문에 링크만 걸어두시면 쿠팡보다 높은 브랜드 직영 수수료가 {nickname}님 통장으로 정산됩니다.

예쁜 아웃핏 올리시면서 실질적인 수익도 같이 챙겨가셨으면 해요! :)

받아보고 싶으시다면 [성함 / 연락처 / 주소]와 [원하시는 품목 및 사이즈] 편하게 남겨주세요.
감사합니다.
박혜란 드림"""
        }
    },
    'SSOK': {
        'commerce': {
            'subject': "[제안] 런칭 3일 만에 14,000포 판매 대란템 쏙쉐이크, 수익 쉐어 파트너십 제안드립니다.",
            'body': """안녕하세요 {nickname}님,
다이어트 쉐이크 브랜드 쏙쉐이크 담당자 박혜란입니다.

{nickname}님의 건강하고 긍정적인 라이프스타일을 보면서, 저희 브랜드가 추구하는 방향이랑 잘 맞을 것 같아 연락드렸어요.

[브랜드 및 제품 경쟁력]
런칭 3일 만에 14,000포가 팔렸는데, 직접 드셔보신 분들이 맛이랑 포만감 얘기를 많이 해주시더라고요.

- 비린맛/텁텁함 ZERO: 맛없는 영양식이라는 편견을 깬 '속세의 맛'
- 입터짐 방지 & 든든함: 씹히는 토핑과 단백질 20g으로, 한 잔만으로 든든한 한 끼 대용식
- 제품 확인: https://zigzag.kr/catalog/products/168991502?utm_source=shopping_naver_all&tab=detail

[협업 제안 내용]
판매 데이터가 확인된 제품인 만큼, {nickname}님과 전용 링크를 통한 수익 쉐어(RS) 공동구매를 먼저 제안드리고 싶어요.

캘린더 일정상 공동구매가 부담스러우시다면, 인스타그램 프로필 링크나 게시물 하단에 '단독 최저가 링크'만 걸어두시는 방식도 괜찮습니다.

쿠팡 파트너스랑 운영 방식은 같고, 본사 직영이라 수수료율은 더 높아요. 14,000포 실판매 이력이 있는 제품이라 링크 하나만으로도 기존 콘텐츠 무드 건드리지 않고 수익을 가져가실 수 있는 구조예요. :)

궁금하신 점 있으시면 편하게 회신 주세요.
감사합니다.
박혜란 드림"""
        },
        'seeding': {
            'subject': "[협찬] 런칭 3일 만에 14,000포 완판 대란템, 쏙쉐이크 넉넉하게 시딩 제안드립니다.",
            'body': """안녕하세요! {nickname}님,
쏙쉐이크 담당자 박혜란입니다. :)

평소 {nickname}님 콘텐츠 즐겨 보고 있었는데, 저희 브랜드랑 분위기가 잘 어울릴 것 같아서 이번 제품 꼭 챙겨드리고 싶었어요.

[시딩 제품: 쏙쉐이크 본품 세트]
런칭 3일 만에 14,000포가 나간 제품인데, 드셔보신 분들이 맛이랑 포만감이 생각보다 좋다고 많이 얘기해 주세요.

- 배고프고 맛없는 다이어트는 그만: 텁텁함과 비린맛을 잡은 속세의 맛
- 씹는 맛이 살아있는 든든함: 단백질 20g, 한 잔으로 든든한 한 끼 대용식
- 제품 확인: https://zigzag.kr/catalog/products/168991502?utm_source=shopping_naver_all&tab=detail

직접 넉넉하게 드셔보시고, {nickname}님만의 감성으로 인스타그램(또는 블로그)에 판매 링크 삽입(+공식 계정 @sssockshake 태그 등) 가볍게 1회 올려주시는 방식이에요.

팔로워분들이 궁금해하실 것 같아서 '전용 최저가 수익 링크'도 같이 드릴게요! 프로필이나 본문에 링크만 걸어두시면 되고, 브랜드 직영이라 쿠팡보다 수수료가 높아요. 어차피 올리실 일상 피드에 실질적인 리워드도 함께 챙겨가셨으면 좋겠어요. :)

진행 가능하시면 [성함 / 연락처 / 주소] 남겨주세요. 예쁘게 포장해서 넉넉히 보내드릴게요.
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
