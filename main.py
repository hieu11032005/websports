from dotenv import load_dotenv # <-- Dòng này cần ở đây
load_dotenv() # <-- Và dòng này cũng cần ở đây

from app import app # Bây giờ app mới được import sau khi .env đã được tải

if __name__ == "__main__":
    # Chạy server trên host 0.0.0.0 port 5000 như yêu cầu
    app.run(host="0.0.0.0", port=5000, debug=True)