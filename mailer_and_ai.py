import smtplib
import imaplib
import email
from email.message import EmailMessage
from email.header import decode_header
import google.generativeai as genai
from PIL import Image
import io

class MailManager:
    def __init__(self, email_account, app_pw, gemini_api_key):
        self.my_email = email_account  
        self.app_pw = app_pw
        self.reply_to = "hcommerceinc1@gmail.com" 
        
        genai.configure(api_key=gemini_api_key)
        self.ai_model = genai.GenerativeModel('models/gemini-2.0-flash')

    def generate_email_content(self, brand, template_type):
        subject = f"[{brand}] 크리에이터님, {brand}에서 브랜드 협업을 제안 드립니다."
        if template_type == "시딩 제안용":
            body = f"안녕하세요 크리에이터님! 트렌디한 감성의 브랜드 {brand}입니다.\n\n제공해 드리는 저희 {brand}의 제품을 경험해 보시고, 콘텐츠로 소개해주실 수 있을까요?\n\n감사합니다."
        else: 
            body = f"안녕하세요 크리에이터님! 라이프스타일 브랜드 {brand}입니다.\n\n크리에이터님과 함께 시너지를 낼 수 있는 특별한 R/S(수익분배) 형태의 커머스 협업을 제안 드립니다.\n\n감사합니다."
        return subject, body

    def send_bulk_emails(self, target_emails, brand, template_type):
        subject, body = self.generate_email_content(brand, template_type)
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.my_email, self.app_pw)
                for email_addr in target_emails:
                    msg = EmailMessage()
                    msg['Subject'] = subject
                    msg['From'] = self.my_email
                    msg['To'] = email_addr
                    msg.add_header('reply-to', self.reply_to)
                    msg.set_content(body)
                    
                    try:
                        img = Image.open('명함.png')
                        img.thumbnail((400, 400)) 
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format='PNG')
                        msg.add_attachment(img_byte_arr.getvalue(), maintype='image', subtype='png', filename='명함_resized.png')
                    except Exception:
                        pass
                    server.send_message(msg)
            return True, "메일 발송 성공"
        except Exception as e:
            return False, f"메일 발송 에러: {e}"

    def check_replies_and_analyze(self):
        analyzed_results = []
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(self.my_email, self.app_pw)
            mail.select("inbox")

            status, messages = mail.search(None, "UNSEEN")
            email_ids = messages[0].split()

            if not email_ids:
                return True, "새로 수신된 메일이 없습니다.", []

            for e_id in email_ids:
                res, msg_data = mail.fetch(e_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        else:
                            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')

                        prompt = f"""
                        다음 메일 내용 중에 '원고료', '광고비', '비용', '단가' 등 금전적인 요구가 포함되어 있다면 'YES', 아니면 'NO'만 답변해.
                        메일 내용: {body}
                        """
                        ai_response = self.ai_model.generate_content(prompt).text.strip().upper()
                        requires_money = "YES" in ai_response
                        
                        analyzed_results.append({
                            "유가요구여부": requires_money,
                            "내용요약": body[:50] + "..." 
                        })

            return True, f"총 {len(email_ids)}건의 새 메일을 분석했습니다.", analyzed_results

        except Exception as e:
            return False, f"수신함 접근 실패: {e}", []
