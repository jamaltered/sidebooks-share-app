import os
import hashlib
import difflib
import requests
import streamlit as st
import dropbox

# ================== Dropbox認証 ==================
APP_KEY = st.secrets["DROPBOX_APP_KEY"]
APP_SECRET = st.secrets["DROPBOX_APP_SECRET"]
REFRESH_TOKEN = st.secrets["DROPBOX_REFRESH_TOKEN"]
TARGET_FOLDER = st.secrets["TARGET_FOLDER"]
THUMBNAIL_FOLDER = st.secrets["THUMBNAIL_FOLDER"]
EXPORT_FOLDER = st.secrets["EXPORT_FOLDER"]
ZIP_LIST_URL = st.secrets["ZIP_LIST_URL"]

dbx = dropbox.Dropbox(
    app_key=APP_KEY,
    app_secret=APP_SECRET,
    oauth2_refresh_token=REFRESH_TOKEN
)

# ================== 初期設定 ==================
st.set_page_config(page_title="SideBooks Exporter", layout="wide")
st.markdown('<a id="top"></a>', unsafe_allow_html=True)

if "selected_files" not in st.session_state:
    st.session_state.selected_files = set()

# ================== zip_file_list.txt 読み込み ==================
def load_zip_file_list():
    try:
        res = requests.get(ZIP_LIST_URL)
        res.raise_for_status()
        return [line.strip() for line in res.text.strip().splitlines()]
    except Exception as e:
        st.error("❌ zip_file_list.txt の取得に失敗しました。")
        return []

zip_file_list = load_zip_file_list()

# ================== サムネイルURL取得 ==================
def get_thumbnail_path(zip_name):
    thumb_name = os.path.splitext(zip_name)[0] + ".jpg"
    return f"{THUMBNAIL_FOLDER}/{thumb_name}"

def get_thumbnail_url(path):
    try:
        return dbx.files_get_temporary_link(path).link
    except:
        return None

# ================== 一意キー生成 ==================
def make_safe_key(name, fullpath):
    base = f"{name}_{fullpath}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()

# ================== エクスポート処理 ==================
def export_selected_files():
    # 事前にフォルダを空にする
    try:
        result = dbx.files_list_folder(EXPORT_FOLDER)
        for entry in result.entries:
            dbx.files_delete_v2(entry.path_lower)
    except Exception as e:
        st.error(f"❌ EXPORTフォルダのクリアに失敗: {e}")
        return

    failed = []
    for name in st.session_state.selected_files:
        src_path = f"{TARGET_FOLDER}/{name}"
        dest_path = f"{EXPORT_FOLDER}/{name}"
        try:
            dbx.files_copy_v2(src_path, dest_path, allow_shared_folder=True, autorename=True)
        except dropbox.exceptions.ApiError:
            # 見つからなければ近似一致で探す
            matches = difflib.get_close_matches(name, zip_file_list, n=1, cutoff=0.7)
            if matches:
                try:
                    dbx.files_copy_v2(matches[0], dest_path, allow_shared_folder=True, autorename=True)
                    continue
                except Exception as e:
                    failed.append(name)
                    st.warning(f"⚠️ 近似コピー失敗: {name} → {matches[0]}")
            else:
                failed.append(name)
                st.error(f"❌ コピー失敗（該当なし）: {name}")
    if failed:
        st.warning(f"⚠️ 一部失敗しました（{len(failed)}件）")
    else:
        st.success("✅ エクスポート完了")

# ================== 表示用 ==================
def show_zip_file_list(zip_paths):
    PER_PAGE = 200
    total = len(zip_paths)
    max_page = max(1, (total - 1) // PER_PAGE + 1)
    page = st.number_input("ページ番号", min_value=1, max_value=max_page, step=1, value=1)

    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE
    current_page_files = zip_paths[start:end]

    # TOPボタン
    st.markdown("""
        <a href="#top" class="top-button">↑ TOP</a>
        <style>
        .top-button {
            position: fixed;
            bottom: 24px;
            left: 24px;
            background: #007bff;
            color: #ffffff;
            padding: 12px 16px;
            border-radius: 50px;
            text-decoration: none;
            font-weight: bold;
            z-index: 9999;
        }
        </style>
    """, unsafe_allow_html=True)

    # 選択数とエクスポートボタン
    st.markdown(f"### ✅ 選択中: {len(st.session_state.selected_files)} 件")
    if st.session_state.selected_files:
        if st.button("📤 選択中のZIPをエクスポート"):
            export_selected_files()

    # サムネイル表示
    for fullpath in current_page_files:
        name = os.path.basename(fullpath)
        thumb_path = get_thumbnail_path(name)
        thumb_url = get_thumbnail_url(thumb_path)

        cols = st.columns([1, 4])
        with cols[0]:
            key = make_safe_key(name, fullpath)
            checked = st.checkbox(name, key=f"cb_{key}", value=(name in st.session_state.selected_files))
            if checked:
                st.session_state.selected_files.add(name)
            else:
                st.session_state.selected_files.discard(name)
        with cols[1]:
            if thumb_url:
                st.image(thumb_url, caption=name, use_container_width=True)
            else:
                st.warning(f"🖼️ サムネイルなし: {name}")

# ================== 実行 ==================
if zip_file_list:
    show_zip_file_list(zip_file_list)
else:
    st.stop()
