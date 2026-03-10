import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime

class GoogleSheetsManager:
    def __init__(self, creds_dict, sheet_name):
        self.scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        try:
            self.creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(creds_dict), self.scope)
            self.client = gspread.authorize(self.creds)
            self.spreadsheet = self.client.open(sheet_name)
        except Exception as e:
            self.spreadsheet = None
            self.error_msg = str(e)

    def insert_influencer_to_brand(self, brand_name, influencer_data):
        if not self.spreadsheet:
            return False, f"시트 연결 실패: {self.error_msg} (권한이나 시트 이름을 확인하세요)"
        
        try:
            sheet = self.spreadsheet.worksheet(brand_name)
            today = datetime.now().strftime("%y/%m/%d")
            contact_method = "이메일" if influencer_data.get('이메일') else "디엠"
            
            nickname = influencer_data.get('닉네임', '')
            insta = influencer_data.get('인스타', '')
            tiktok = influencer_data.get('틱톡', '')
            blog = influencer_data.get('블로그', '')
            email = influencer_data.get('이메일', '')

            # 브랜드별 양식에 맞춰 데이터 삽입
            if brand_name in ["MELV", "SOLV"]:
                row_data = [contact_method, nickname, insta, tiktok, blog, email, "", today, ""]
            elif brand_name == "UPPR":
                row_data = [contact_method, nickname, insta, tiktok, blog, email, "", "", "", today, ""]
            else:
                return False, "알 수 없는 브랜드입니다."
            
            sheet.append_row(row_data)
            return True, f"{brand_name} 탭에 데이터가 성공적으로 추가되었습니다."
            
        except gspread.exceptions.WorksheetNotFound:
            return False, f"'{brand_name}' 탭을 찾을 수 없습니다. 시트 하단의 탭 이름을 정확히 확인해주세요."
        except Exception as e:
            return False, f"업데이트 중 알 수 없는 에러 발생: {e}"

    def update_content_metrics(self, brand_name, scraper_function):
        """콘텐츠수치 탭의 G열 링크를 읽어와서 조회수 등을 업데이트합니다."""
        if not self.spreadsheet: return "시트 연결 오류"
        
        tab_name = f"{brand_name}콘텐츠수치"
        try:
            sheet = self.spreadsheet.worksheet(tab_name)
            all_values = sheet.get_all_values()
            today = datetime.now().strftime("%y/%m/%d")
            updated_count = 0
            
            for i, row in enumerate(all_values):
                row_num = i + 1
                # G열(링크)이 있고, I열(조회수)이 아직 비어있는 경우에만 작동
                if len(row) > 6 and row[6].startswith("http") and (len(row) <= 8 or row[8] == ""):
                    metrics = scraper_function(row[6]) 
                    if metrics:
                        cells_to_update = [
                            {'range': f'C{row_num}', 'values': [[metrics['게재일']]]},
                            {'range': f'H{row_num}', 'values': [[today]]},
                            {'range': f'I{row_num}', 'values': [[metrics['조회수']]]},
                            {'range': f'J{row_num}', 'values': [[metrics['좋아요']]]},
                            {'range': f'K{row_num}', 'values': [[metrics['댓글']]]},
                            {'range': f'L{row_num}', 'values': [[metrics['저장']]]},
                            {'range': f'M{row_num}', 'values': [[metrics['공유']]]},
                            {'range': f'N{row_num}', 'values': [[metrics['리포스트']]]}
                        ]
                        sheet.batch_update(cells_to_update)
                        updated_count += 1
                        
            return f"{tab_name} 탭에서 총 {updated_count}건의 콘텐츠 수치를 업데이트했습니다!"
        except gspread.exceptions.WorksheetNotFound:
            return f"{tab_name} 탭을 찾을 수 없습니다."
