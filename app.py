import streamlit as st
import dropbox
import os
import hashlib
import difflib
import requests

# ====================== 設定 ======================
APP_KEY = st.secrets["APP_KEY"]
APP_SECRET = st.secrets["APP_SECRET"]
REFRESH_TOKEN = st.secrets["REFRESH_TOKEN"]
TARGET_FOLDER = st.secrets["TARGET_FOLDER"]
EXPORT_FOLDER = st.secrets["EXPORT_FOLDER"]
THUMBNAIL_FOLDER = st.secrets["THUMBNAIL_FOLDER"]
ZIP_LIST_URL = st.secrets["ZIP_LIST_URL"]

PER_PAGE = 50

# ====================== 初期化 ======================
dbx = dropbox.Dropbox(
    app_key=APP_KEY,
    app_secret=APP_SECRET,
    oauth2_refresh_token=REFRESH_TOKEN
)

if "selected_files" not in st.session_state:
    st.session_state.selected_files = []

# ====================== 関数 ======================
def load_zip_file_list():
    res = requests.get(ZIP_LIST_URL)
    return [line.strip() for line in res.text.splitlines() if line.strip().endswith(".zip")]

def get_thumbnail_path(zip_name):
    base_name = os.path.splitext(zip_name)[0]
    hash_str = hashlib.md5(zip_name.encode("utf-8")).hexdigest()
    return f"{THUMBNAIL_FOLDER}/{hash_str}.jpg"

def make_safe_key(name):
    return hashlib.md5(name.encode("utf-8")).hexdigest()

def show_zip_file_list(zip_paths, page):
    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE
    page_items = zip_paths[start:end]

    for path in page_items:
        name = os.path.basename(path)
        col1, col2 = st.columns([1, 5])
        with col1:
            thumb_path = get_thumbnail_path(name)
            st.image(thumb_path, use_container_width=True)
        with col2:
            st.markdown(f"**{name}**")
            key = make_safe_key(name)
            checked = st.checkbox("選択", key=f"cb_{key}", value=(name in st.session_state.selected_files))
            if checked and name not in st.session_state.selected_files:
                st.session_state.selected_files.append(name)
            elif not checked and name in st.session_state.selected_files:
                st.session_state.selected_files.remove(name)
        st.markdown("---")

def delete_all_in_export_folder():
    try:
        result = dbx.files_list_folder(EXPORT_FOLDER)
        for entry in result.entries:
            dbx.files_delete_v2(f"{EXPORT_FOLDER}/{entry.name}")
    except dropbox.exceptions.ApiError as e:
        st.error(f"エクスポートフォルダ削除中にエラー: {e}")

def try_export_file(name, zip_paths):
    src_path = f"{TARGET_FOLDER}/{name}"
    dest_path = f"{EXPORT_FOLDER}/{name}"
    try:
        dbx.files_copy_v2(src_path, dest_path, allow_shared_folder=True, autorename=True)
        return True
    except dropbox.exceptions.ApiError:
        matches = difflib.get_close_matches(name, [os.path.basename(p) for p in zip_paths], n=1, cutoff=0.7)
        if matches:
            matched_name = matches[0]
            matched_path = next((p for p in zip_paths if os.path.basename(p) == matched_name), None)
            if matched_path:
                try:
                    dbx.files_copy_v2(matched_path, dest_path, allow_shared_folder=True, autorename=True)
                    return True
                except Exception:
                    return False
        return False

# ====================== UI構築 ======================
st.title("📚 コミック一覧")

# エクスポートボタン（上部）
st.markdown("### ✅選択中: " + str(len(st.session_state.selected_files)))
if st.button("📤 選択中のZIPをエクスポート"):
    failed = []
    delete_all_in_export_folder()
    zip_paths = load_zip_file_list()
    for name in st.session_state.selected_files:
        if not try_export_file(name, zip_paths):
            st.error(f"❌ {name} のコピー元が見つかりませんでした。")
            failed.append(name)
    if failed:
        st.warning(f"{len(failed)}件のエクスポートに失敗しました。")
    else:
        st.success("✅ エクスポートが完了しました。")

# ZIP一覧
zip_paths = load_zip_file_list()
total_pages = (len(zip_paths) - 1) // PER_PAGE + 1
page = st.number_input("ページ", min_value=1, max_value=total_pages, value=1, step=1)
st.markdown("---")
show_zip_file_list(zip_paths, page)

# ↑TOPボタン
st.markdown('<a href="#top">⬆️ Top</a>', unsafe_allow_html=True)
