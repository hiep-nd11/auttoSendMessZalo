from flask import Flask, request, jsonify
import os.path
import time
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import openai
import json
from datetime import datetime


openai.api_key = "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"

app = Flask(__name__)
# Phạm vi quyền truy cập (đọc và ghi Google Sheets)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ID Google Sheet (thay bằng ID của bạn nếu cần)
SHEET_TONG = "19XR8tZOI09FvWyEihNAgVvl53ZBgXPI7jvCpDHSRUV0"
SHEET_INFO = "12qu0zJEihV9DOWnqJ80KWuTaBEJZvzgoFEKoRn22NPA"
# Phạm vi cột cần thêm dữ liệu (Cột A)
# SAMPLE_RANGE_NAME = "AI_source!A:A"
RANGE_UPDATE_1 = "AI_source!A:D"
RANGE_UPDATE_2 = "2!A:D"

#############################################
#############################################
#############################################
def execute_with_timeout(func, timeout, *args, **kwargs):
    """
    Chạy một hàm với giới hạn timeout.
    """
    start_time = time.time()
    while True:
        try:
            return func(*args, **kwargs)
        except HttpError as e:
            if time.time() - start_time > timeout:
                print("Timeout reached!")
                raise TimeoutError("Operation timed out") from e
            else:
                print("Retrying due to error:", e)

#############################################
#############################################
#############################################
# Ham xu ly api chay tach text ra json
def get_date_string(dt):
    if isinstance(dt, datetime):
        return dt.strftime('%Y-%m-%d')
    return dt  # Nếu không phải datetime thì giữ nguyên

def extract_info(message):
    prompt = f"""
    Trích xuất thông tin từ dòng tin nhắn sau và trả về hợp lệ dưới dạng text:
    Tin nhắn: "{message}"
    Yêu cầu:
    - status: trả về một trong ba trạng thái: "full" nếu phòng kín, "empty" nếu phòng trống, "missing" nếu thiếu phòng
    - address: địa chỉ dưới dạng string (ví dụ: "số 8 ngách 70 ngõ 38 Phạm Hùng")
    - room: Số phòng dạng string (ví dụ: "403")

    Ví dụ output:
    {{
        "status": "full",
        "address": "số 8 ngách 70 ngõ 38 Phạm Hùng",
        "room": "406"
    }}

    Chỉ trả về dưới dạng text, không thêm bất kỳ nội dung nào khác.
    """
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Bạn là một trợ lý AI."},
            {"role": "user", "content": prompt}
        ]
    )
    output = response['choices'][0]['message']['content']

    try:
        json_output = json.loads(output)
        return json_output
    except json.JSONDecodeError:
        return {"error": "Không thể chuyển đổi sang JSON", "raw_output": output}




















def append_with_index(sheet, spreadsheet_id, range_name, data):
    current_time = datetime.now()
    formatted_date = get_date_string(current_time)
    # Lấy số dòng hiện tại trong bảng
    current_data = sheet.values().get(
        spreadsheetId = spreadsheet_id,
        range = range_name
    ).execute().get('values', [])
    
    # Xác định số thứ tự bắt đầu
    start_index = len(current_data)  # Đếm từ 1 (hoặc tùy chỉnh theo yêu cầu)


    
    # Chuyển dữ liệu vào dạng danh sách với số thứ tự
    indexed_data = [
        [start_index, 
         data[status],
         data[],
         formatted_date 
         ]
    ]
    
    # Tạo body cho request
    body = {
        "values": indexed_data
    }

    # Append dữ liệu vào bảng
    result = sheet.values().append(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body=body
    ).execute()
    
    return result

# Ham xu ly update thong tin len google sheet
def update_google_sheet(data):
    creds = None
    
    # Kiểm tra xem token.json đã tồn tại chưa (dùng để lưu thông tin đăng nhập)
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    
    # Nếu chưa có thông tin đăng nhập hoặc token không hợp lệ
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Lưu thông tin đăng nhập vào file token.json
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()
        
        # Dữ liệu cần thêm
        new_data = [data]
        

        d = extract_info(data)

        append_with_index(sheet, SAMPLE_SPREADSHEET_ID ,RANGE, d)

        return {"message": f"Dữ liệu đã được thêm vào Google Sheet: {new_data}"}
    except TimeoutError:
        return {"error": "Operation timed out after 10 seconds"}
    except HttpError as err:
        return {"error": f"An error occurred: {err}"}

@app.route('/update_sheet', methods=['POST'])
def update_sheet():
    # Nhận dữ liệu JSON từ client
    data = request.json
    if not data or 'value' not in data:
        return jsonify({"error": "Missing 'value' in request body"}), 400
    
    # Lấy dữ liệu từ client
    value = data['value']
    cdt = data['cdt']
    
    # Gọi hàm để cập nhật Google Sheets
    result = update_google_sheet(value)
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result), 200

if __name__ == "__main__":
    app.run(debug=True, port=5000)
