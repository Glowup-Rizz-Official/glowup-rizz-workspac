import smtplib
from email.message import EmailMessage
import google.generativeai as genai
from PIL import Image
import io

class MailManager:
    def __init__(self, sender_email, app_password, gemini_api_key):
        self.sender_email = sender_email
        self.app_password = app_password
        self.reply_to = "hcommerceinc1@gmail.com"
        genai.configure(api_key=gemini_api_key)
        self.ai_model = genai.GenerativeModel('gemini-3.1-pro')

    def generate_email_content(self, brand, template_type):
        """메일 제목과 본문을 생성하여 반환합니다 (미리보기 및 발송용)"""
        subject = f"[{brand}] 인플루언서 협업 제안 ({template_type})"
        body = f"""안녕하세요, {brand}입니다.
귀하의 콘텐츠가 저희 브랜드와 잘 맞아 {template_type}을 드리고자 연락드렸습니다.
미팅 요청 무방하며, 편하게 유선 연락 주셔도 좋습니다.

긍정적인 회신 기다리겠습니다.
감사합니다.

({brand} 담당자 드림)"""
        return subject, body

    def send_bulk_emails(self, target_emails, brand, template_type):
        subject, body = self.generate_email_content(brand, template_type)
        
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.sender_email, self.app_password)
                
                for email in target_emails:
                    msg = EmailMessage()
                    msg['Subject'] = subject
                    msg['From'] = self.sender_email
                    msg['To'] = email
                    msg.add_header('reply-to', self.reply_to)
                    msg.set_content(body)
                    
                    # 명함 이미지 리사이징 및 첨부
                    try:
                        img = Image.open('명함.png')
                        # 명함 사이즈를 가로 400px 비율에 맞춰 적당하게 줄임
                        img.thumbnail((400, 400)) 
                        
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format='PNG')
                        img_data = img_byte_arr.getvalue()
                        
                        msg.add_attachment(img_data, maintype='image', subtype='png', filename='명함_resized.png')
                    except FileNotFoundError:
                        print("명함.png 파일이 없어 텍스트만 발송합니다.")

                    server.send_message(msg)
            return True, "메일 발송 성공"
        except Exception as e:
            return False, f"메일 발송 에러: {e}"
