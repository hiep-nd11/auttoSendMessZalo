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
import gspread
from datetime import datetime
import re
from id_speadsheet import choose_id_speadsheet
from rapidfuzz import process, fuzz


app = Flask(__name__)
#khai bao openai api
openai.api_key = "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"

#Khai bao google api
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

#khai bao google sheet
SHEET_TONG_THIEU = "19XR8tZOI09FvWyEihNAgVvl53ZBgXPI7jvCpDHSRUV0"
SHEET_TONG_TRONG = ""
SHEET_THONG_TIN = "1uSuMnqUy43Rc7PY3Iqwgl0_nyKGOemHLmXXSSiLsC5k"
RANGE_THONGTIN_TENZALO = "sheet1!A1:C"
RANGE_CDT = "sheet1!A2:A"
RANGE_THONGTIN_LINKZALO = "sheet1!C2:C"
RANGE_THONGTIN_LINKCAPNHAT = "sheet1!E2:E"
#khai bao

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

# Ham xu ly chay ra thoi gian thuc ngay thang nam
def get_date_string(dt):
    if isinstance(dt, datetime):
        return dt.strftime('%Y-%m-%d')
    return dt  # Nếu không phải datetime thì giữ nguyên

# Ham nhan du lieu text va cho dau ra la thong tin status, address, room
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

def find_most_similar_address(target_address, address_list):
    best_match = process.extractOne(target_address, address_list, scorer=fuzz.ratio)
    return best_match  

def status_room(message, address_list):

    #Đưa vào chương trình python xử lý openai
    extracted_info = extract_info(message)
    if not extracted_info:
        return {"error": "GPT không trả về dữ liệu hợp lệ"}

    gpt_status = extracted_info.get("status", "")

    if gpt_status == "full":
        return -2, 0, 0
    elif gpt_status == "missing":
        gpt_address = extracted_info.get("address", "")
        gpt_room = extracted_info.get("room", "")

        return -1, gpt_address, gpt_room

    elif gpt_status == "empty":
        gpt_address = extracted_info.get("address", "")
        gpt_room = extracted_info.get("room", "")
        gpt_out = f"{gpt_address} {gpt_room}"
        print(gpt_out)

        if gpt_out:
            best_match = find_most_similar_address(gpt_out, address_list)
            if best_match:
                matched_address = best_match[2]
                print(matched_address)

                return matched_address, gpt_address, gpt_room
    
    else:
        return 0,0,0

def get_date_string(dt):
    if isinstance(dt, datetime):
        return dt.strftime('%Y-%m-%d')
    return dt  # Nếu không phải datetime thì giữ nguyên

def process_message(message, cdt):
    creds = None
    
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

        #Lay du lieu ten zalo, ten cdt, link nhom google sheet
        tenzalo = sheet.values().get(spreadsheetId=SHEET_THONG_TIN, range=RANGE_THONGTIN_TENZALO).execute()
        values = tenzalo.get('values', [])

        filtered_values = [f"{row[0]} {row[2]}" for row in values if len(row) > 2]
        print(filtered_values)

        stt, addr, room = status_room(message, filtered_values)

        if stt == -2:
            print("Phòng kín không làm gì")
        elif stt == -1:
            print("Phòng thiếu, chèn vào bảng phòng thiếu")
            range_name = "Danhsachphongthieu!A:A"
            current_data = sheet.values().get(
                spreadsheetId = SHEET_THONG_TIN,
                range = range_name
            ).execute().get('values', [])
            start_index = len(current_data)
            current_time = datetime.now()
            formatted_date = get_date_string(current_time)
            new_value = [[start_index, cdt, addr, room]]
            body = {'values': new_value}
            sheet.values().append(
                spreadsheetId=SHEET_THONG_TIN,
                range=range_name,
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body=body
            ).execute()
            print("Chèn vào trong bảng thiếu ở sheet tổng")

        elif stt == 0:
            print("Dữ liệu phòng bị sai")
        else:

            new_value = [["trống"]]
            
            #r[0] -> ten zalo cđt
            #r[1] -> nhom spreadsheet

            for r in values:
                print(r[0], r[1])
                if r[0] == cdt and r[1] == '':
                    range_name = 'khongcosheet!A:A'
                    print("Phòng trống nhưng không có link, trả về bảng phòng trống ở sheet tổng")
                    current_data = sheet.values().get(
                        spreadsheetId = SHEET_THONG_TIN,
                        range = range_name
                    ).execute().get('values', [])
                    start_index = len(current_data)

                    current_time = datetime.now()
                    formatted_date = get_date_string(current_time)
                    new_value = [[start_index, r[0], formatted_date]]
                    
                    body = {'values': new_value}
                    sheet.values().append(
                        spreadsheetId=SHEET_THONG_TIN,
                        range=range_name,
                        valueInputOption="RAW",
                        insertDataOption="INSERT_ROWS",
                        body=body
                    ).execute()
                    print("Thông tin đã được chèn thêm.")

                elif r[0] == cdt and r[1] != '':
                    id = choose_id_speadsheet(r[1])
                    
                    body = {'values': new_value}
                    cell_range = f'sheet1!F{stt + 1}'
                    print("Chèn vào đây")

                    try:
                        result = sheet.values().update(
                            spreadsheetId = id,
                            range = cell_range,
                            valueInputOption = "RAW",
                            body = body
                        ).execute()
                        print("Cập nhật thành công:", result)
                    except Exception as e:
                        print("Lỗi khi cập nhật:", e)

    except TimeoutError:
        return {"error": "Operation timed out after 10 seconds"}
    except HttpError as err:
        return {"error": f"An error occurred: {err}"}


input_message = "a Lâm dạo này chắc làm ăn nhiều bạc lắm. Hôm qua thiếu số phòng Sari đc 000010 ở 10nguyenvietcong nhé anh"

process_message(input_message)

@app.route('/update_sheet', methods=['POST'])

##############
# Ham update_sheet lay du lieu data tu request va truyen vao process
##############

def update_sheet():
    # Nhận dữ liệu JSON từ client   
    data = request.json
    if not data or 'value' not in data:
        return jsonify({"error": "Missing 'value' in request body"}), 400

    value = data['value']   #Tin nhan cuoi cung lay tu zalo
    cdt = data['cdt']       #Ma chu dau tu

    #Check danh sach chu dau tu xem co speadsheet khong

    result = process_message(value, cdt)
    #Check result xem co la phong kin/trong/thieu hay khong:
        
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result), 200

if __name__ == "__main__":
    app.run(debug=True, port=5000)
