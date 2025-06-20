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
EXPORT_FOLDER = "/SideBooksExport"
LOG_PATH = f"{THUMBNAIL_FOLDER}/export_log.csv"

st.set_page_config(page_title="コミック一覧", layout="wide")

# 初期状態
if "selected_files" not in st.session_state:
    st.session_state.selected_files = set()
if "page" not in st.session_state:
    st.session_state.page = 1

selected_count = len(st.session_state.selected_files)

# サムネイル取得・ページ処理
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

def list_thumbnails():
    thumbnails = []
    try:
        result = dbx.files_list_folder(THUMBNAIL_FOLDER)
        thumbnails.extend([entry.name for entry in result.entries if entry.name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            thumbnails.extend([entry.name for entry in result.entries if entry.name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
    except Exception as e:
        st.error(f"サムネイルの取得に失敗: {e}")
    return thumbnails

def get_temporary_image_url(path):
    try:
        res = dbx.files_get_temporary_link(path)
        return res.link
    except:
        return None

zip_files = list_zip_files()
thumbnails = list_thumbnails()
zip_set = {entry.name for entry in zip_files}

# ページネーション
PER_PAGE = 500
max_pages = (len(thumbnails) + PER_PAGE - 1) // PER_PAGE

# トップリンク（常に表示）
st.markdown("""
    <style>
    .scroll-to-top {
        position: fixed;
        bottom: 30px;
        right: 30px;
        background: #007bff;
        color: white;
        padding: 10px 15px;
        border-radius: 8px;
        text-decoration: none;
        z-index: 1000;
    }
    </style>
    <a class="scroll-to-top" href="#top">↑ Top</a>
    <div id="top"></div>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if st.button("⬅ 前へ"):
        if st.session_state.page > 1:
            st.session_state.page -= 1
with col2:
    st.session_state.page = st.selectbox("ページ番号", options=list(range(1, max_pages + 1)), format_func=lambda x: f"{x} / {max_pages}", index=st.session_state.page - 1)
with col3:
    if st.button("次へ ➡"):
        if st.session_state.page < max_pages:
            st.session_state.page += 1

page = st.session_state.page
start_idx = (page - 1) * PER_PAGE
end_idx = start_idx + PER_PAGE
visible_thumbs = sorted(thumbnails)[start_idx:end_idx]

# 以下は既存コードのまま続けてOK（省略）
