import streamlit as st
import dropbox
import hashlib
import requests
import os

from dropbox.exceptions import ApiError
from io import BytesIO
from PIL import Image

# 🔐 Secrets から取得
APP_KEY = st.secrets["DROPBOX_APP_KEY"]
APP_SECRET = st.secrets["DROPBOX_APP_SECRET"]
REFRESH_TOKEN = st.secrets["DROPBOX_REFRESH_TOKEN"]
TARGET_FOLDER = st.secrets["TARGET_FOLDER"]
EXPORT_FOLDER = st.secrets["EXPORT_FOLDER"]
THUMBNAIL_FOLDER = st.secrets["THUMBNAIL_FOLDER"]
ZIP_LIST_URL = st.secrets["ZIP_LIST_URL"]

# Dropboxクライアント
dbx = dropbox.Dropbox(
    app_key=APP_KEY,
    app_secret=APP_SECRET,
    oauth2_refresh_token=REFRESH_TOKEN
)

# ✅ ファイル名を一意なキーに
def make_safe_key(name, fullpath):
    return hashlib.md5(fullpath.encode()).hexdigest()[:10]

# ✅ サムネイルパスを取得
def get_thumbnail_path(zip_path):
    base = os.path.splitext(os.path.basename(zip_path))[0]
    safe_name = base.replace("/", "_")
    return f"{THUMBNAIL_FOLDER}/{safe_name}.jpg"

# ✅ zip_file_list.txt 読み込み
@st.cache_data
def load_zip_file_list():
    res = requests.get(ZIP_LIST_URL)
    if res.status_code == 200:
        return [line.strip() for line in res.text.splitlines()]
    else:
        st.error("zip_file_list.txt の取得に失敗しました。")
        return []

# ✅ サムネとチェックボックス付き一覧表示
def show_zip_file_list(zip_paths, page_size=30):
    if "selected_files" not in st.session_state:
        st.session_state.selected_files = []

    page = st.number_input("ページ番号", min_value=1, max_value=(len(zip_paths) - 1) // page_size + 1, step=1)
    start, end = (page - 1) * page_size, page * page_size
    for fullpath in zip_paths[start:end]:
        name = os.path.basename(fullpath)
        key = make_safe_key(name, fullpath)
        cols = st.columns([1, 4])
        with cols[0]:
            checked = st.checkbox("選択", key=f"cb_{key}", value=(name in st.session_state.selected_files))
            if checked and name not in st.session_state.selected_files:
                st.session_state.selected_files.append(name)
            elif not checked and name in st.session_state.selected_files:
                st.session_state.selected_files.remove(name)
        with cols[1]:
            st.markdown(f"**{name}**")
            thumb_path = get_thumbnail_path(fullpath)
            try:
                img_data = dbx.files_download(thumb_path)[1].content
                st.image(Image.open(BytesIO(img_data)), use_container_width=True)
            except:
                st.write("（サムネイルなし）")

# ✅ エクスポート先フォルダを初期化
def clear_export_folder():
    try:
        res = dbx.files_list_folder(EXPORT_FOLDER)
        for entry in res.entries:
            dbx.files_delete_v2(entry.path_display)
    except ApiError as e:
        st.error(f"エクスポート先の削除に失敗: {e}")

# ✅ エクスポートログ保存
def save_export_log(files):
    content = "\n".join(files).encode("utf-8")
    log_path = f"{TARGET_FOLDER}/export_log.csv"
    dbx.files_upload(content, log_path, mode=dropbox.files.WriteMode("overwrite"))

# ==========================
# 🔽 Streamlit UI
# ==========================

st.title("📚 コミック一覧")
st.markdown("#### ✅ 選択中: " + str(len(st.session_state.get("selected_files", []))))

# ✅ エクスポート処理
if st.button("📤 選択中のZIPをエクスポート"):
    if not st.session_state.get("selected_files"):
        st.warning("ファイルが選択されていません。")
    else:
        clear_export_folder()
        zip_file_paths = load_zip_file_list()
        exported, failed = [], []
        for name in st.session_state.selected_files:
            matches = [p for p in zip_file_paths if os.path.basename(p) == name]
            if not matches:
                st.error(f"❌ {name} のコピー元が見つかりませんでした。")
                failed.append(name)
                continue
            src_path = matches[0]
            dest_path = f"{EXPORT_FOLDER}/{name}"
            try:
                dbx.files_copy_v2(src_path, dest_path, allow_shared_folder=True, autorename=True)
                exported.append(name)
            except ApiError as e:
                st.error(f"❌ {name} のコピーに失敗: {e}")
                failed.append(name)
        if exported:
            save_export_log(exported)
            st.success("✅ エクスポートが完了しました。")
        if failed:
            st.warning(f"{len(failed)} 件のエクスポートに失敗しました。")

# ✅ 一覧表示
zip_paths = load_zip_file_list()
show_zip_file_list(zip_paths)

st.markdown("[↑Top](#コミック一覧)")
