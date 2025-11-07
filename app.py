import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime

# Google Sheets 設定
SPREADSHEET_ID = "あなたのスプレッドシートIDをここに"  # URLの /d/ と /edit の間の部分
SHEET_NAME = "Sheet1"

# Renderでは環境変数からJSONを読み込む
import json, os
creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = service_account.Credentials.from_service_account_info(creds_dict)

service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

st.title("📅 シンプル予約ツール（Google Sheets 版）")

target = st.selectbox("対象を選択", ["ミーティングルーム A", "ミーティングルーム B"])
date = st.date_input("日付を選択")
start_time = st.time_input("開始時間")
duration = st.selectbox("長さ", ["30分", "1時間", "2時間"])

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
    st.success("✅ Google Sheets に予約を記録しました！")
