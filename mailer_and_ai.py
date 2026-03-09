import smtplib
from email.message import EmailMessage
import google.generativeai as genai

class MailManager:
    def __init__(self, sender_email, app_password, gemini_api_key):
        self.sender_email = sender_email
        self.app_password = app_password # 구글 계정 설정에서 '앱 비밀번호' 생성 필요
        self.reply_to = "hcommerceinc1@gmail.com"
        
        # Gemini AI 설정
        genai.configure(api_key=gemini_api_key)
        self.ai_model = genai.GenerativeModel('gemini-3.1-pro') # 최신 모델 사용

    def send_bulk_emails(self, target_emails, brand, template_type):
        if self.app_password == "여러분의_이메일_앱비밀번호":
            print("앱 비밀번호가 설정되지 않아 메일을 보낼 수 없습니다.")
            return

        # SMTP 서버 연결 (Gmail 기준)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(self.sender_email, self.app_password)
            
            for email in target_emails:
                msg = EmailMessage()
                msg['Subject'] = f"[{brand}] 인플루언서 협업 제안 ({template_type})"
                msg['From'] = self.sender_email
                msg['To'] = email
                msg.add_header('reply-to', self.reply_to) # 회신은 이쪽으로!
                
                content = f"안녕하세요, {brand}입니다. 미팅 요청 무방 편하게 유선 연락 주세요.\n(여기에 이미지 첨부 로직 추가)"
                msg.set_content(content)
                
                server.send_message(msg)
                print(f"{email} 로 발송 완료")

    def check_replies_and_analyze(self, email_body):
        # Gemini에게 이메일 내용 분석을 지시하는 프롬프트 (Prompt Engineering)
        prompt = f"""
        다음은 인플루언서가 보낸 답장 메일입니다.
        이 메일 내용 중에 '원고료', '광고비', '단가', '비용'과 관련된 언급이 있는지 확인해 주세요.
        만약 돈과 관련된 요구사항이 있다면 'YES', 없다면 'NO'라고만 대답해 주세요.
        
        메일 내용:
        {email_body}
        """
        response = self.ai_model.generate_content(prompt)
        return "YES" in response.text.upper()
