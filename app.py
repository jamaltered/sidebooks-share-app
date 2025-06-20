import os
import re
import dropbox
import streamlit as st
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()
APP_KEY = os.getenv("DROPBOX_APP_KEY")
APP_SECRET = os.getenv("DROPBOX_APP_SECRET")
REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN")

# Dropboxクライアントの初期化
dbx = dropbox.Dropbox(
    app_key=APP_KEY,
    app_secret=APP_SECRET,
    oauth2_refresh_token=REFRESH_TOKEN
)

# フォルダ設定
TARGET_FOLDER = "/成年コミック"
THUMBNAIL_FOLDER = "/サムネイル"

st.set_page_config(page_title="ZIPビューア", layout="wide")
st.title("📦 ZIP画像一覧ビューア（Dropbox共有フォルダ）")

# ユーザー名取得
try:
    user_name = dbx.users_get_current_account().name.display_name
    st.markdown(f"こんにちは、**{user_name}** さん")
except Exception:
    st.warning("Dropboxの認証情報が不足しています")
    st.stop()

# ZIPファイル一覧の取得
def list_zip_files():
    zip_files = []
    try:
        result = dbx.files_list_folder(TARGET_FOLDER, recursive=True)
        zip_files.extend([entry for entry in result.entries if entry.name.endswith(".zip")])
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            zip_files.extend([entry for entry in result.entries if entry.name.endswith(".zip")])
    except Exception as e:
        st.error(f"ZIPファイルの取得に失敗: {e}")
    return zip_files

# サムネイル一覧の取得
def list_thumbnails():
    thumbnails = []
    try:
        result = dbx.files_list_folder(THUMBNAIL_FOLDER)
        thumbnails.extend([entry.name for entry in result.entries if entry.name.endswith(".jpg")])
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            thumbnails.extend([entry.name for entry in result.entries if entry.name.endswith(".jpg")])
    except Exception as e:
        st.error(f"サムネイルの取得に失敗: {e}")
    return thumbnails

# 一時リンク取得
def get_temporary_image_url(path):
    try:
        res = dbx.files_get_temporary_link(path)
        return res.link
    except:
        return None

# 初期状態
if "selected_files" not in st.session_state:
    st.session_state.selected_files = set()

# ZIPとサムネイル一覧取得
zip_files = list_zip_files()
thumbnails = list_thumbnails()
zip_set = {entry.name for entry in zip_files}

st.markdown("### 表示するZIPファイルを選んでください")

# グリッド表示（5列）
cols_per_row = 5
columns = st.columns(cols_per_row)
i = 0

for thumb in sorted(thumbnails):
    zip_name = thumb.replace(".jpg", ".zip")
    if zip_name not in zip_set:
        continue

    title_display = re.sub(r"^\(成年コミック\)\s*", "", zip_name.replace(".zip", ""))
    thumb_path = f"{THUMBNAIL_FOLDER}/{thumb}"
    url = get_temporary_image_url(thumb_path)

    if url:
        col = columns[i % cols_per_row]
        with col:
            st.markdown(f'''
                <div style="border:1px solid #ddd; border-radius:10px; padding:8px; margin:6px; text-align:center; background-color:#f9f9f9;">
                    <img src="{url}" style="height:200px; object-fit:cover; border-radius:5px;" />
                    <div style="margin-top:8px;">
                        <input type="checkbox" id="{zip_name}" name="{zip_name}" {'checked' if zip_name in st.session_state.selected_files else ''} onchange="window.location.href='?toggle={zip_name}'" />
                        <label for="{zip_name}" style="font-size:13px; font-weight:500; color:#111;">{title_display}</label>
                    </div>
                </div>
            ''', unsafe_allow_html=True)
        i += 1

# 選択済み表示・エクスポートボタン
if st.session_state.selected_files:
    st.markdown("---")
    st.markdown("### ✅ 選択されたZIPファイル：")
    for f in sorted(st.session_state.selected_files):
        st.write(f)
    st.download_button("📤 ダウンロード用リンクを生成（未実装）", "準備中...", key="export_btn")
