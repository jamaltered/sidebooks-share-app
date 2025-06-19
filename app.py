import os
import re
import io
import time
import datetime
import streamlit as st
import dropbox
import pandas as pd
from dotenv import load_dotenv

# .env 読み込み
load_dotenv()

# Dropbox認証
dbx = dropbox.Dropbox(
    app_key=os.getenv("DROPBOX_APP_KEY"),
    app_secret=os.getenv("DROPBOX_APP_SECRET"),
    oauth2_refresh_token=os.getenv("DROPBOX_REFRESH_TOKEN")
)

SOURCE_FOLDER = "/成年コミック"
THUMBNAIL_FOLDER = "/サムネイル"
EXPORT_FOLDER = "/SideBooksExport"
LOG_PATH = f"{SOURCE_FOLDER}/export_log.csv"

# 連番やシリーズと判定するパターン
def is_serialized(name):
    name = os.path.splitext(name)[0]
    return bool(re.search(r"(上|中|下|前|後|\b\d+\b|[IVX]{1,5}|\d+-\d+)$", name, re.IGNORECASE))

def clean_title(name):
    name = os.path.splitext(name)[0]
    name = name.replace("(成年コミック)", "").strip()
    return name

def extract_author(name):
    match = re.match(r"\[([^\]]+)\]", name)
    return match.group(1) if match else ""

def get_thumbnails():
    try:
        res = dbx.files_list_folder(THUMBNAIL_FOLDER)
        return [entry.name for entry in res.entries if entry.name.endswith(".jpg")]
    except Exception as e:
        st.error(f"サムネイル取得失敗: {e}")
        return []

def map_zip_paths():
    zip_map = {}
    try:
        res = dbx.files_list_folder(SOURCE_FOLDER, recursive=True)
        entries = res.entries
        while res.has_more:
            res = dbx.files_list_folder_continue(res.cursor)
            entries.extend(res.entries)
        for entry in entries:
            if isinstance(entry, dropbox.files.FileMetadata) and entry.name.lower().endswith(".zip"):
                zip_map[entry.name] = entry.path_display
    except Exception as e:
        st.error(f"ZIPファイル一覧取得失敗: {e}")
    return zip_map

def export_zip(zip_name, src_path):
    try:
        with dbx.files_download_to_file("/tmp/temp.zip", src_path):
            with open("/tmp/temp.zip", "rb") as f:
                dbx.files_upload(f.read(), f"{EXPORT_FOLDER}/{zip_name}", mode=dropbox.files.WriteMode.overwrite)
        return True
    except Exception as e:
        st.error(f"{zip_name} のエクスポートに失敗: {e}")
        return False

def write_export_log(log_data):
    try:
        df = pd.DataFrame(log_data, columns=["timestamp", "username", "filename"])
        with io.StringIO() as csv_buffer:
            df.to_csv(csv_buffer, index=False)
            dbx.files_upload(csv_buffer.getvalue().encode("utf-8"), LOG_PATH, mode=dropbox.files.WriteMode.overwrite)
    except Exception as e:
        st.warning(f"ログ保存失敗: {e}")

# Streamlit UI開始
st.set_page_config(page_title="SideBooks ZIP共有", layout="wide")
st.title("📦 ZIP画像一覧ビューア（Dropbox共有フォルダ）")

try:
    user_name = dbx.users_get_current_account().name.display_name
except Exception:
    user_name = "guest"

st.markdown(f"こんにちは、{user_name} さん")

# 表示順切り替え
sort_option = st.selectbox("並び順を選択してください", ["タイトル順", "作家順"])

# ファイル取得
thumbnails = get_thumbnails()
zip_paths = map_zip_paths()

# 重複除去＋連番考慮
unique_titles = {}
selected_titles = []

for thumb in thumbnails:
    zip_name = thumb.replace(".jpg", ".zip")
    clean = clean_title(zip_name)
    if is_serialized(clean) or clean not in unique_titles:
        unique_titles[clean] = zip_name  # 上書きなしで記録

# 並び替え
if sort_option == "作家順":
    sorted_items = sorted(unique_titles.items(), key=lambda x: extract_author(x[1]))
else:
    sorted_items = sorted(unique_titles.items(), key=lambda x: x[0].lower())

# ジャンプリンク作成
st.markdown("🔤 **ジャンプ：** " + " ".join([f"[{c}](#{c})" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]))

# チェックボックスUI
selection = []
current_letter = ""
for clean, zip_name in sorted_items:
    first = clean[0].upper()
    if first != current_letter and first.isalpha():
        st.markdown(f"<h2 id='{first}'>===== {first} =====</h2>", unsafe_allow_html=True)
        current_letter = first
    col1, col2 = st.columns([1, 9])
    with col1:
        checked = st.checkbox("選択", key=zip_name)
    with col2:
        st.image(f"https://content.dropboxapi.com/2/files/download", width=120,
                 headers={"Dropbox-API-Arg": f'{{"path": "{THUMBNAIL_FOLDER}/{zip_name.replace(".zip", ".jpg")}"}}'})
        st.caption(clean)
    if checked:
        selection.append(zip_name)

# エクスポート処理
if selection:
    if st.button("📤 選択したZIPをエクスポート"):
        success_logs = []
        for zip_name in selection:
            if zip_name in zip_paths:
                ok = export_zip(zip_name, zip_paths[zip_name])
                if ok:
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    success_logs.append([timestamp, user_name, zip_name])
        if success_logs:
            write_export_log(success_logs)
            st.success(f"{len(success_logs)} 件をエクスポート＆ログ記録しました！")
