from app import app

if __name__ == "__main__":
    # Chạy server trên host 0.0.0.0 port 5000 như yêu cầu
    app.run(host="0.0.0.0", port=5000, debug=True)
