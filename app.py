import streamlit as st
import dropbox
import hashlib
import difflib
import os
from PIL import Image
from io import BytesIO

# ▼ Dropbox認証（リフレッシュトークン使用）
dbx = dropbox.Dropbox(
    oauth2_refresh_token=st.secrets["DROPBOX_REFRESH_TOKEN"],
    app_key=st.secrets["DROPBOX_APP_KEY"],
    app_secret=st.secrets["DROPBOX_APP_SECRET"]
)

# ▼ パス設定
TARGET_FOLDER = st.secrets["TARGET_FOLDER"]
EXPORT_FOLDER = st.secrets["EXPORT_FOLDER"]
THUMBNAIL_FOLDER = st.secrets["THUMBNAIL_FOLDER"]
ZIP_LIST_PATH = "zip_file_list.txt"
THUMBNAIL_HEIGHT = 500

# ▼ ユーティリティ
def make_safe_key(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()

def load_zip_list():
    try:
        with open(ZIP_LIST_PATH, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        st.error("zip_file_list.txt が見つかりません。")
        return []

zip_full_paths = load_zip_list()

def find_closest_path(filename):
    matches = difflib.get_close_matches(filename, zip_full_paths, n=1, cutoff=0.7)
    return matches[0] if matches else None

def show_thumbnail(name):
    thumbnail_name = os.path.splitext(name)[0] + ".jpg"
    path = f"{THUMBNAIL_FOLDER}/{thumbnail_name}"
    try:
        res = dbx.files_download(path)
        img = Image.open(BytesIO(res[1].content))
        st.image(img, caption=name, use_container_width=True)
    except:
        st.text(f"[No Thumbnail] {name}")

def show_zip_file_list(names):
    for name in names:
        key = make_safe_key(name)
        checked = st.checkbox(name, key=f"cb_{key}", value=(name in st.session_state.selected_files))
        if checked and name not in st.session_state.selected_files:
            st.session_state.selected_files.append(name)
        elif not checked and name in st.session_state.selected_files:
            st.session_state.selected_files.remove(name)
        show_thumbnail(name)

def save_export_log(exported):
    log_path = f"{TARGET_FOLDER}/export_log.csv"
    content = "\n".join(exported)
    dbx.files_upload(content.encode("utf-8"), log_path, mode=dropbox.files.WriteMode("overwrite"))

# ▼ アプリ本体
st.set_page_config(page_title="SideBooks Exporter", layout="wide")

if "selected_files" not in st.session_state:
    st.session_state.selected_files = []

st.title("📦 SideBooks向けZIPエクスポートツール")

st.markdown("### ✅ 選択中: " + str(len(st.session_state.selected_files)) + " 件")

# ▼ エクスポートボタン
if st.button("📤 選択したZIPをエクスポート"):
    failed = []
    for name in st.session_state.selected_files:
        src_path = f"{TARGET_FOLDER}/{name}"
        dest_path = f"{EXPORT_FOLDER}/{name}"
        try:
            dbx.files_copy_v2(src_path, dest_path, allow_shared_folder=True, autorename=True)
        except dropbox.exceptions.ApiError:
            alt_path = find_closest_path(name)
            if alt_path:
                try:
                    dbx.files_copy_v2(alt_path, dest_path, allow_shared_folder=True, autorename=True)
                    continue
                except Exception as e:
                    st.error(f"❌ {name} のコピーに失敗（代替: {alt_path}）: {e}")
                    failed.append(name)
            else:
                st.error(f"❌ {name} のコピーに失敗（該当ファイルなし）")
                failed.append(name)
    save_export_log(st.session_state.selected_files)
    if not failed:
        st.success("✅ エクスポート完了！")
    else:
        st.warning(f"⚠️ 一部失敗: {len(failed)} 件")

# ▼ ZIP一覧表示
zip_names = [os.path.basename(p) for p in zip_full_paths]
show_zip_file_list(zip_names)
