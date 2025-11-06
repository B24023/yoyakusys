import streamlit as st
import pandas as pd
from datetime import datetime, time, timedelta
import time as t

# --- 定数設定 ---
START_HOUR = 9
END_HOUR = 17
INTERVAL_MINUTES = 30
# データベースのテーブル名
TABLE_NAME = 'reservations'

# --- ページ設定 ---
st.set_page_config(
    page_title="シンプル予約ツール (DB版)",
    page_icon="📅",
    layout="centered"
)

# --- データベース接続と初期化 ---
@st.cache_resource
def get_db_connection():
    """Secrets.tomlの "connections.turso" を使ってDBに接続"""
    # st.connectionは、Secrets.tomlの[connections.turso]を自動で読み込みます
    conn = st.connection("turso", type="sql")
    
    # テーブルが存在しない場合、初めての実行時にテーブルを作成する
    # TEXT: 文字列, DATETIME: 日時
    with conn.session as s:
        s.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reservation_target TEXT NOT NULL,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                duration TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        s.commit()
        
    return conn

# グローバルに接続を取得
try:
    conn = get_db_connection()
except Exception as e:
    st.error(f"🚨 データベース接続に失敗しました。Streamlit CloudのSecrets設定を確認してください。エラー: {e}")
    st.stop()


# --- 関数: 既存予約データの読み込み ---
@st.cache_data(ttl=5) # 5秒間はキャッシュ
def load_reservations():
    """データベースから既存の予約データを読み込む"""
    try:
        # SQLクエリで全データを取得し、pandas DataFrameに変換
        df = conn.query(f'SELECT * FROM {TABLE_NAME}', ttl=0) # キャッシュを使わず最新を取得
        
        if df.empty:
            # 必要な列を定義した空のDataFrameを返す
            cols = ['reservation_target', 'date', 'start_time', 'duration', 'created_at', 'start_datetime', 'end_datetime']
            return pd.DataFrame(columns=cols)

        # --- DataFrameの加工 (Excelの時と同じ処理) ---
        
        # start_datetimeの作成
        df['start_datetime'] = pd.to_datetime(df['date'] + ' ' + df['start_time'])
        
        # end_datetimeの計算
        def calculate_end_time(row):
            duration_str = str(row.get('duration', '1時間'))
            hours, minutes = 0, 0
            if '時間' in duration_str:
                parts = duration_str.split('時間')
                try: hours = int(parts[0].strip())
                except ValueError: hours = 0
                if '分' in parts[1]:
                    try: minutes = int(parts[1].replace('分', '').strip())
                    except ValueError: minutes = 0
            elif '分' in duration_str:
                try: minutes = int(duration_str.replace('分', '').strip())
                except ValueError: minutes = 0
            else:
                hours = 1 # デフォルト1時間
            
            return row['start_datetime'] + timedelta(hours=hours, minutes=minutes)

        df['end_datetime'] = df.apply(calculate_end_time, axis=1)
        
        # 列名をExcelの時と合わせる（後方互換性のため）
        df = df.rename(columns={
            'reservation_target': '予約対象',
            'date': '日付',
            'start_time': '開始時間',
            'duration': '長さ',
            'created_at': '予約確定日時'
        })
        
        return df
        
    except Exception as e:
        st.error(f"🚨 予約データの読み込みエラー: {e}")
        # エラー時は空のDFを返す
        cols = ['予約対象', '日付', '開始時間', '長さ', '予約確定日時', 'start_datetime', 'end_datetime']
        return pd.DataFrame(columns=cols)

# --- 関数: データベースに追記 ---
def append_reservation(target, date_str, time_str, duration_str, created_at_str):
    """新しいデータをデータベースに INSERT (追記) する"""
    try:
        # 'with conn.session' を使うと自動的にトランザクションが管理される
        with conn.session as s:
            # SQLのINSERT文
            # :variable_name の形式で、安全に値を挿入（SQLインジェクション対策）
            s.execute(
                f"""
                INSERT INTO {TABLE_NAME} 
                (reservation_target, date, start_time, duration, created_at) 
                VALUES 
                (:target, :date, :time, :duration, :created)
                """,
                params=dict(
                    target=target,
                    date=date_str,
                    time=time_str,
                    duration=duration_str,
                    created=created_at_str
                )
            )
            s.commit()
            
        st.success("🎉 予約が確定し、データベースに保存されました！")
        st.balloons()
        
        # 追記後のデータを表示
        st.subheader("📚 最新の予約データ (最終5件)")
        latest_df = conn.query(f'SELECT reservation_target as 予約対象, date as 日付, start_time as 開始時間, duration as 長さ, created_at as 予約確定日時 FROM {TABLE_NAME} ORDER BY id DESC LIMIT 5', ttl=0)
        st.dataframe(latest_df, hide_index=True, use_container_width=True)
        
    except Exception as e:
        st.error(f"❌ データベースへの書き込み中にエラーが発生しました。エラー詳細: {e}")
        st.stop()
        
# --- メイン処理 ---
st.title("📅 シンプル予約ツール (データベース版)")
st.markdown("### ご希望の日時と予約対象を選択してください。")
st.info("予約データはクラウド上のデータベースに安全に保存されます。")

# 既存の予約台帳を読み込む
reservations_df = load_reservations()

# --- 予約対象の選択 ---
targets = ["ミーティングルーム A", "専門スタッフ B", "テニスコート 3"]
selected_target = st.selectbox(
    "1. 予約したい対象を選択してください",
    targets
)
st.write("---")

# --- 日付と時間の選択 ---
st.header("🗓️ 日付と時間の選択")

# 日付の選択
today = datetime.now().date()
selected_date = st.date_input(
    "2. 予約日を選択",
    value=today,
    min_value=today
)

# 時間の選択オプションを生成
available_times = []
current_time = datetime.combine(selected_date, time(START_HOUR, 0))
end_datetime_limit = datetime.combine(selected_date, time(END_HOUR, 0))

while current_time <= end_datetime_limit:
    available_times.append(current_time.strftime("%H:%M"))
    current_time += timedelta(minutes=INTERVAL_MINUTES)

selected_time_str = st.selectbox(
    "3. 予約開始時間を選択",
    available_times
)

# 予約時間の長さの選択
duration_options = ["30分", "1時間", "1時間30分", "2時間"]
selected_duration = st.selectbox(
    "4. 予約の長さ（時間）を選択",
    duration_options,
    index=1
)

st.write("---")

# --- 予約内容の確認と確定 ---
st.header("📝 予約内容の確認と確定")

st.markdown(f"""
- **対象:** **{selected_target}**
- **日付:** **{selected_date.strftime('%Y年%m月%d日')}**
- **開始時間:** **{selected_time_str}**
- **長さ:** **{selected_duration}**
""")

# 予約確定ボタンと処理
if st.button("✅ 上記の内容で予約を確定する", type="primary"):
    
    # 1. 予約したい日時のdatetimeオブジェクトを作成
    try:
        target_start_dt = datetime.combine(selected_date, datetime.strptime(selected_time_str, '%H:%M').time())
        
        # (ダブルブッキングチェック用の) 予約の長さをtimedeltaオブジェクトに変換
        duration_delta = timedelta()
        hours, minutes = 0, 0
        if '時間' in selected_duration:
            parts = selected_duration.split('時間')
            try: hours = int(parts[0].strip())
            except ValueError: hours = 0
            if '分' in parts[1]:
                try: minutes = int(parts[1].replace('分', '').strip())
                except ValueError: minutes = 0
        elif '分' in selected_duration:
            try: minutes = int(selected_duration.replace('分', '').strip())
            except ValueError: minutes = 0
        
        duration_delta = timedelta(hours=hours, minutes=minutes)
        if duration_delta.total_seconds() == 0:
            duration_delta = timedelta(hours=1) # 万が一0分なら1時間にする

        target_end_dt = target_start_dt + duration_delta

    except Exception as e:
        st.error(f"🚨 日時の解析に失敗しました: {e}")
        st.stop()
        
    # --- 2. ダブルブッキングチェックロジック ---
    is_booked = False
    
    # 同じ予約対象（部屋など）に絞り込む
    if not reservations_df.empty:
        target_reservations = reservations_df[reservations_df['予約対象'] == selected_target]
    else:
        target_reservations = pd.DataFrame()
    
    # 予約が存在する場合のみチェック
    if not target_reservations.empty:
        for index, row in target_reservations.iterrows():
            existing_start = row['start_datetime']
            existing_end = row['end_datetime']
            
            if (target_start_dt < existing_end) and (existing_start < target_end_dt):
                is_booked = True
                st.error(f"""
                ❌ **ダブルブッキングの可能性があります！**
                選択された時間帯は既に予約済みです。
                - **既存予約:** {row['start_datetime'].strftime('%Y/%m/%d %H:%M')} - {row['end_datetime'].strftime('%H:%M')}
                """)
                t.sleep(0.1)
                break
    
    # --- 3. 予約確定処理 ---
    if not is_booked:
        # データベースに保存する文字列データ
        date_str_to_db = selected_date.strftime('%Y-%m-%d')
        time_str_to_db = selected_time_str
        duration_str_to_db = selected_duration
        created_at_str_to_db = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 追記と保存を実行
        append_reservation(
            selected_target,
            date_str_to_db,
            time_str_to_db,
            duration_str_to_db,
            created_at_str_to_db
        )

# --- 既存予約データの表示 (デバッグ/確認用) ---
if not reservations_df.empty:
    st.markdown("---")
    st.subheader("📌 既存の全予約データ (確認用)")
    st.dataframe(reservations_df[['予約対象', '日付', '開始時間', '長さ', '予約確定日時']], hide_index=True, use_container_width=True)

# --- フッター ---
st.markdown("---")
st.caption("powered by Streamlit & Turso (SQLite)")


