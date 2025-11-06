import streamlit as st
import pandas as pd
from datetime import datetime, time, timedelta
import time as t
from sqlalchemy import text # <<< 修正点： この行を追加しました

# --- 定数設定 ---
START_HOUR = 9
END_HOUR = 17
INTERVAL_MINUTES = 30
TABLE_NAME = 'reservations_log' # テーブル名 (Excelファイルパスの代わり)

# --- ページ設定 ---
st.set_page_config(
    page_title="シンプル予約ツール (DB版)",
    page_icon="📅",
    layout="centered"
)

# --- データベース接続と初期化 ---
@st.cache_resource
def get_db_connection():
    """Tursoデータベースへの接続を取得し、テーブルがなければ作成する"""
    conn = st.connection("turso", type="sql")
    
    with conn.session as session:
        # テーブルが存在しない場合のみ作成する
        session.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                予約対象 VARCHAR(255),
                日付 VARCHAR(20),
                開始時間 VARCHAR(10),
                長さ VARCHAR(50),
                予約確定日時 VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        session.commit()
    return conn

# グローバルに接続を取得
try:
    conn = get_db_connection()
except Exception as e:
    st.error(f"データベース接続に失敗しました。Streamlit Cloud の Secret 設定を確認してください。エラー: {e}")
    st.stop()


# --- 関数: 既存予約データの読み込み ---
@st.cache_data(ttl=5) # 5秒間は再実行しないようにキャッシュを設定
def load_reservations():
    """データベースから既存の予約データを読み込む"""
    try:
        # データベースから全データを読み込む
        query = f"SELECT * FROM {TABLE_NAME};"
        df = conn.query(query, ttl=0) # DB問い合わせ時はキャッシュを無効化
        
        if df.empty:
            # 予約がまだない場合は空のDataFrameを返す
            return pd.DataFrame(columns=['予約対象', '日付', '開始時間', '長さ', '予約確定日時', 'start_datetime', 'end_datetime'])

        # 日付と時間を結合してdatetimeオブジェクトを作成する
        df['start_datetime'] = pd.to_datetime(df['日付'] + ' ' + df['開始時間'])
        
        # 予約終了時刻を計算して列に追加する
        def calculate_end_time(row):
            duration_str = row['長さ']
            
            if '分' in duration_str and '時間' not in duration_str:
                minutes = int(duration_str.replace('分', '').strip())
                return row['start_datetime'] + timedelta(minutes=minutes)
            elif '時間30分' in duration_str:
                hours = int(duration_str.split('時間')[0].strip())
                return row['start_datetime'] + timedelta(hours=hours, minutes=30)
            elif '時間' in duration_str:
                hours = int(duration_str.replace('時間', '').strip())
                return row['start_datetime'] + timedelta(hours=hours)
            
            return row['start_datetime'] + timedelta(hours=1) # デフォルト1時間
            
        df['end_datetime'] = df.apply(calculate_end_time, axis=1)
        return df

    except Exception as e:
        st.error(f"🚨 予約台帳の読み込みエラーが発生しました。詳細: {e}")
        # st.dataframe(df) # デバッグ用にDFを表示
        st.stop()

# --- 関数: データベースに追記 ---
def append_and_save(new_df):
    """新しいデータをデータベースに追記する"""
    try:
        with conn.session as session:
            for index, row in new_df.iterrows():
                # データを辞書型に変換
                reservation_data = {
                    "target": row['予約対象'],
                    "date": row['日付'],
                    "time": row['開始時間'],
                    "duration": row['長さ'],
                    "now": row['予約確定日時']
                }
                
                # パラメータ化クエリでSQLインジェクションを防止
                session.execute(text(f"""
                    INSERT INTO {TABLE_NAME} (予約対象, 日付, 開始時間, 長さ, 予約確定日時)
                    VALUES (:target, :date, :time, :duration, :now)
                """), reservation_data)
            
            session.commit()
            
        st.success("🎉 予約が確定し、データベースに保存されました！")
        st.balloons()
        
        # 追記後にキャッシュをクリアして最新のデータを再読み込みさせる
        st.cache_data.clear()
        
        # 追記されたデータ（最後の数件）を表示して確認
        st.subheader("📚 最新の予約データ (最終5件)")
        updated_df = load_reservations()
        st.dataframe(updated_df[['予約対象', '日付', '開始時間', '長さ']].tail(5), hide_index=True, use_container_width=True)
        
    except Exception as e:
        st.error(f"❌ データベースへの書き込み中にエラーが発生しました。詳細: {e}")
        st.stop()
        
# --- メイン処理 ---
st.title("📅 シンプル予約ツール (DB接続版)")
st.markdown("### ご希望の日時と予約対象を選択してください。")
st.info(f"予約データはクラウドデータベース (テーブル名: `{TABLE_NAME}`) に保存されます。")

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

# 選択された内容を整形して表示
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
        
        # 予約の長さをtimedeltaオブジェクトに変換
        duration_delta = timedelta()
        if '分' in selected_duration and '時間' not in selected_duration:
            minutes = int(selected_duration.replace('分', '').strip())
            duration_delta = timedelta(minutes=minutes)
        elif '時間30分' in selected_duration:
            hours = int(selected_duration.split('時間')[0].strip())
            duration_delta = timedelta(hours=hours, minutes=30)
        elif '時間' in selected_duration:
            hours = int(selected_duration.replace('時間', '').strip())
            duration_delta = timedelta(hours=hours)
        else:
            duration_delta = timedelta(hours=1) # フォールバック

        target_end_dt = target_start_dt + duration_delta

    except Exception as e:
        st.error(f"🚨 選択された日時の解析に失敗しました。: {e}")
        st.stop()
        
    # --- 2. ダブルブッキングチェックロジック ---
    is_booked = False
    
    # 同じ予約対象（部屋など）に絞り込む
    target_reservations = reservations_df[reservations_df['予約対象'] == selected_target]
    
    # 予約が存在する場合のみチェック
    if not target_reservations.empty:
        for index, row in target_reservations.iterrows():
            
            # 既存予約の開始時刻と終了時刻
            existing_start = row['start_datetime']
            existing_end = row['end_datetime']
            
            # 予約が重複しているかの判定ロジック
            # (Aの開始 < Bの終了) かつ (Bの開始 < Aの終了)
            if (target_start_dt < existing_end) and (existing_start < target_end_dt):
                is_booked = True
                st.error(f"""
                ❌ **ダブルブッキングの可能性があります！**
                選択された時間帯は既に予約済みです。
                - **既存予約:** {row['start_datetime'].strftime('%Y/%m/%d %H:%M')} - {row['end_datetime'].strftime('%H:%M')}
                """)
                t.sleep(0.1) # エラー表示のため
                break
    
    # --- 3. 予約確定処理 ---
    if not is_booked:
        # 新しい予約データをDataFrameとして作成
        new_reservation_data = {
            '予約対象': [selected_target],
            '日付': [selected_date.strftime('%Y-%m-%d')],
            '開始時間': [selected_time_str],
            '長さ': [selected_duration],
            '予約確定日時': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        }
        new_df = pd.DataFrame(new_reservation_data)
        
        # 追記と保存を実行
        append_and_save(new_df)


# --- 既存予約データの表示 (デバッグ/確認用) ---
if not reservations_df.empty:
    st.markdown("---")
    st.subheader("📌 既存の全予約データ (確認用)")
    st.dataframe(reservations_df[['予約対象', '日付', '開始時間', '長さ']], hide_index=True, use_container_width=True)


# --- フッター ---
st.markdown("---")
st.caption("powered by Streamlit & Turso")


