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
            self.error_msg = ""
        except Exception as e:
            self.spreadsheet = None
            self.error_msg = str(e)

    def append_searched_data(self, brand_name, df_selected):
        """검색 탭에서 체크박스로 선택한 인플루언서들을 지정한 브랜드 탭 맨 아래에 추가합니다."""
        if not self.spreadsheet: return False, f"시트 연결 오류: {self.error_msg}"
        try:
            sheet = self.spreadsheet.worksheet(brand_name)
            today = datetime.now().strftime("%y/%m/%d")
            
            rows_to_insert = []
            for _, row in df_selected.iterrows():
                contact = "이메일" if row.get("이메일") else "디엠"
                nickname = str(row.get("닉네임", ""))
                link = str(row.get("프로필링크", ""))
                email = str(row.get("이메일", ""))
                
                # A열:연락경로, B:닉네임, C:인스타, D:틱톡, E:블로그, F:이메일
                platform = row.get("플랫폼", "")
                insta = link if platform == "인스타" else ""
                tiktok = link if platform == "틱톡" else ""
                blog = link if platform == "블로그" or "blog" in link else ""
                youtube = link if platform == "유튜브" else ""
                
                # 유튜브면 인스타 자리에 넣거나 비고에 넣음 (현재 양식에 유튜브칸이 없으므로 링크는 C열 쪽에 배치)
                if brand_name in ["MELV", "SOLV"]:
                    rows_to_insert.append([contact, nickname, insta or youtube, tiktok, blog, email, "", today, ""])
                elif brand_name == "UPPR":
                    rows_to_insert.append([contact, nickname, insta or youtube, tiktok, blog, email, "", "", "", today, ""])
            
            if rows_to_insert:
                sheet.append_rows(rows_to_insert)
            return True, f"{len(rows_to_insert)}명의 인플루언서가 '{brand_name}' 탭에 저장되었습니다!"
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
                # G열(업로드 시 링크)은 인덱스 6
                if len(row) > 6 and row[6].startswith("http") and (len(row) <= 8 or str(row[8]).strip() == ""):
                    metrics = scraper_function(row[6]) # 셀레니움으로 해당 링크 진입
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
