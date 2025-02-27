import requests

def read_data(text ,a):
    timeout=100
    # URL của Flask server
    url = "http://127.0.0.1:5000/update_sheet"
    
    # Dữ liệu gửi đến server
    data = {
        "cdt": a,
        "value": text
    }
    response = requests.post(url, json=data, timeout=timeout)

a = "Sari đc 000001"
data = "a Lâm dạo này chắc làm ăn nhiều bạc lắm. Hôm qua thiếu phòng t1000 ở số 20 ngõ 18 Khương Hạ nhé anh"
read_data(data, a)
