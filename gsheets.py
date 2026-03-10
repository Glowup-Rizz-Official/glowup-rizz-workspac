import gspread
import pandas as pd
from datetime import datetime

class GoogleSheetsManager:
    def __init__(self, creds_dict, sheet_name):
        try:
            # 💡 [핵심 수정] 구버전 oauth2client를 버리고, 최신 gspread 네이티브 인증 사용
            self.client = gspread.service_account_from_dict(dict(creds_dict))
            
            # 💡 [핵심 수정] 시트 이름뿐만 아니라, 전체 URL을 입력해도 인식하도록 자동화
            if "http" in sheet_name:
                self.spreadsheet = self.client.open_by_url(sheet_name)
            else:
                self.spreadsheet = self.client.open(sheet_name)
                
            self.error_msg = ""
            
        except gspread.exceptions.SpreadsheetNotFound:
            self.spreadsheet = None
            self.error_msg = "시트를 찾을 수 없습니다. (이름/URL 오타 또는 '편집자' 권한 공유 누락)"
        except Exception as e:
            self.spreadsheet = None
            self.error_msg = str(e)

    def append_searched_data(self, brand_name, df_selected):
        if not self.spreadsheet: return False, f"시트 연결 오류: {self.error_msg}"
        try:
            sheet = self.spreadsheet.worksheet(brand_name)
            today = datetime.now().strftime("%y/%m/%d")
            
            rows_to_insert = []
            for _, row in df_selected.iterrows():
                contact = "이메일" if row.get("이메일") else "디엠"
                nickname = str(row.get("닉네임", ""))
                
                # 유튜브와 인스타/블로그의 컬럼명 차이 보정
                link = str(row.get("프로필링크", ""))
                if not link and "URL" in row: 
                    link = str(row.get("URL", ""))
                    
                email = str(row.get("이메일", ""))
                platform = row.get("플랫폼", "")
                
                insta = link if platform == "인스타" else ""
                tiktok = link if platform == "틱톡" else ""
                blog = link if platform == "블로그" or "blog" in link else ""
                youtube = link if platform == "유튜브" else ""
                
                if brand_name in ["MELV", "SOLV"]:
                    rows_to_insert.append([contact, nickname, insta or youtube, tiktok, blog, email, "", today, ""])
                elif brand_name == "UPPR":
                    rows_to_insert.append([contact, nickname, insta or youtube, tiktok, blog, email, "", "", "", today, ""])
            
            if rows_to_insert:
                sheet.append_rows(rows_to_insert)
            return True, f"{len(rows_to_insert)}명의 인플루언서가 '{brand_name}' 탭에 저장되었습니다!"
            
        except gspread.exceptions.WorksheetNotFound:
            return False, f"'{brand_name}' 탭을 찾을 수 없습니다."
        except Exception as e:
            return False, str(e)

    def get_all_records(self, brand_name):
        if not self.spreadsheet: return []
        try: return self.spreadsheet.worksheet(brand_name).get_all_records()
        except: return []

    def overwrite_sheet(self, brand_name, df):
        if not self.spreadsheet: return False, f"시트 오류: {self.error_msg}"
        try:
            sheet = self.spreadsheet.worksheet(brand_name)
            sheet.clear()
            df = df.fillna("")
            data = [df.columns.values.tolist()] + df.values.tolist()
            sheet.update(data)
            return True, f"'{brand_name}' DB가 성공적으로 수정 및 연동되었습니다."
        except Exception as e: return False, str(e)

    def update_content_metrics(self, brand_name, scraper_function):
        if not self.spreadsheet: return f"🚨 시트 연결 오류: {self.error_msg}"
        tab_name = f"{brand_name}콘텐츠수치"
        try:
            sheet = self.spreadsheet.worksheet(tab_name)
            all_values = sheet.get_all_values()
            today = datetime.now().strftime("%y/%m/%d")
            updated_count = 0
            
            for i, row in enumerate(all_values):
                row_num = i + 1
                if len(row) > 6 and str(row[6]).startswith("http") and (len(row) <= 8 or str(row[8]).strip() == ""):
                    metrics = scraper_function(row[6])
                    if metrics:
                        cells_to_update = [
                            {'range': f'H{row_num}', 'values': [[today]]},
                            {'range': f'I{row_num}', 'values': [[metrics.get('조회수', 0)]]},
                            {'range': f'J{row_num}', 'values': [[metrics.get('좋아요', 0)]]},
                            {'range': f'K{row_num}', 'values': [[metrics.get('댓글', 0)]]}
                        ]
                        sheet.batch_update(cells_to_update)
                        updated_count += 1
            return f"{tab_name} 탭의 {updated_count}건 링크 성과를 업데이트 완료했습니다!"
        except Exception as e: return f"업데이트 실패: {e}"
