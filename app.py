import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime

# Google Sheets 設定
SPREADSHEET_ID = "1YHq6QSH1c4JY5Gv-7A4Oundgwr4TVLSUJPpZVYrvKk4"  # URLの /d/ と /edit の間の部分
SHEET_NAME = "Sheet1"

# Renderでは環境変数からJSONを読み込む
import json, os
creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = service_account.Credentials.from_service_account_info(creds_dict)

service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()



st.title("📅 シンプル予約ツール")

target = st.selectbox("対象を選択", ["座敷A", "座敷B"])
date = st.date_input("日付を選択")
start_time = st.time_input("開始時間")
duration = st.selectbox("利用時間", ["30分", "1時間", "2時間"])

if st.button("予約を確定"):
    new_row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        target,
        str(date),
        start_time.strftime("%H:%M"),
        duration
    ]
    sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A:E",
        valueInputOption="USER_ENTERED",
        body={"values": [new_row]}
    ).execute()
    st.success("✅ 予約を確定しました！")








