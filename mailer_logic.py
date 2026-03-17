import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import googleapiclient.discovery
import google.generativeai as genai
import os

class OutreachMaster:
    def __init__(self, youtube_key, gemini_key, email_user, email_pw):
        self.youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=youtube_key)
        genai.configure(api_key=gemini_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.email_user = email_user
        self.email_pw = email_pw
        self.reply_to = "hcommerceinc1@gmail.com"

    def get_recent_videos(self, channel_url):
        """채널 링크에서 최근 영상 10개의 제목과 설명을 가져옵니다."""
        try:
            # URL에서 채널 ID 또는 핸들 추출 (간단 구현)
            handle = channel_url.split('@')[-1] if '@' in channel_url else channel_url.split('/')[-1]
            search_res = self.youtube.search().list(q=handle, type='channel', part='id').execute()
            channel_id = search_res['items'][0]['id']['channelId']
            
            video_res = self.youtube.search().list(
                channelId=channel_id, order="date", part="snippet", maxResults=10, type="video"
            ).execute()
            
            videos = [item['snippet']['title'] for item in video_res.get('items', [])]
            return ", ".join(videos)
        except:
            return "최근 활동 중"

    def generate_ai_body(self, brand, template_type, channel_name, video_context, sender_name):
        """Gemini를 사용하여 영상 내용을 언급하는 초개인화 문구를 생성합니다."""
        prompt = f"""
        너는 브랜드 {brand}의 마케팅 담당자 {sender_name}이야.
        크리에이터 '{channel_name}'님에게 {template_type} 제안 메일을 보낼거야.
        
        [크리에이터 최근 영상 정보]
        {video_context}
        
        [작성 규칙]
        1. 위 영상 제목들 중 하나를 구체적으로 언급하며 "최근 올리신 ~ 영상을 정말 인상 깊게 보았습니다"라는 문구로 시작해줘.
        2. {brand}의 무드와 크리에이터의 영상 스타일이 어떻게 어울리는지 1문장 추가해줘.
        3. 정중하고 친근한 톤으로 작성하고, 전체 길이는 4~5문장 내외로 해줘.
        4. HTML 태그 <br>을 사용해서 줄바꿈을 해줘.
        """
        response = self.model.generate_content(prompt)
        return response.text.strip()

    def send_email(self, receiver_email, subject, body, sender_name, image_path="명함.png"):
        """이미지 명함이 포함된 이메일을 발송합니다."""
        msg = MIMEMultipart('related')
        msg['Subject'] = subject
        msg['From'] = f"{sender_name} <{self.email_user}>"
        msg['To'] = receiver_email
        msg.add_header('Reply-To', self.reply_to)

        html_body = f"""
        <html>
            <body>
                <p style='font-family: sans-serif; line-height: 1.6;'>{body}</p>
                <br>
                <img src="cid:business_card" style="width: 250px; height: auto;">
            </body>
        </html>
        """
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        if os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                img = MIMEImage(f.read())
                img.add_header('Content-ID', '<business_card>')
                msg.attach(img)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(self.email_user, self.email_pw)
            server.send_message(msg)
