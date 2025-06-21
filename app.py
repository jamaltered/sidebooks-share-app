import streamlit as st
import dropbox
import os
import difflib
import hashlib

# --- Dropbox接続 ---
APP_KEY = st.secrets["DROPBOX_APP_KEY"]
APP_SECRET = st.secrets["DROPBOX_APP_SECRET"]
REFRESH_TOKEN = st.secrets["DROPBOX_REFRESH_TOKEN"]

dbx = dropbox.Dropbox(
    app_key=APP_KEY,
    app_secret=APP_SECRET,
    oauth2_refresh_token=REFRESH_TOKEN
)

# --- 各種定数 ---
TARGET_FOLDER = st.secrets["TARGET_FOLDER"]  # 例: /成年コミック
EXPORT_FOLDER = st.secrets["EXPORT_FOLDER"]  # 例: /SideBooksExport
THUMBNAIL_FOLDER = st.secrets["THUMBNAIL_FOLDER"]  # 例: /サムネイル
ZIP_LIST_PATH = "zip_file_list.txt"

# --- 近似一致検索 ---
def find_closest_match(filename, path_list, cutoff=0.7):
    matches = difflib.get_close_matches(filename, path_list, n=1, cutoff=cutoff)
    return matches[0] if matches else None

# --- 一意なキー生成 ---
def hash_key(name):
    return hashlib.md5(name.encode('utf-8')).hexdigest()

# --- エクスポートログ保存 ---
def save_export_log(exported):
    log_path = os.path.join(ZIP_LIST_PATH.rsplit("/", 1)[0], "export_log.csv")
    with open(log_path, "w", encoding="utf-8") as f:
        for name in exported:
            f.write(f"{name}\n")

# --- zip_file_list.txt 読み込み ---
@st.cache_data
def load_zip_file_list():
    with open(ZIP_LIST_PATH, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines()]

# --- メイン画面表示 ---
st.title("📚 SideBooks ZIP共有ツール")

if "selected_files" not in st.session_state:
    st.session_state.selected_files = []

all_zip_paths = load_zip_file_list()
file_names = [os.path.basename(p) for p in all_zip_paths]

# --- ZIP一覧表示 ---
st.subheader("📦 ZIPファイル一覧")

for name in file_names:
    key = hash_key(name)
    checked = st.checkbox("", key=f"cb_{key}", value=name in st.session_state.selected_files)
    st.write(name)
    if checked:
        if name not in st.session_state.selected_files:
            st.session_state.selected_files.append(name)
    else:
        if name in st.session_state.selected_files:
            st.session_state.selected_files.remove(name)

# --- エクスポート処理 ---
if st.session_state.selected_files:
    st.markdown("### ✅ 選択中のZIPをエクスポート")
    if st.button("📤 エクスポート実行"):
        failed = []
        for name in st.session_state.selected_files:
            try:
                src_path = f"{TARGET_FOLDER}/{name}"
                dest_path = f"{EXPORT_FOLDER}/{name}"
                try:
                    dbx.files_copy_v2(src_path, dest_path, allow_shared_folder=True, autorename=True)
                except dropbox.exceptions.ApiError:
                    # 近似検索で対応
                    match = find_closest_match(src_path, all_zip_paths)
                    if match:
                        dbx.files_copy_v2(match, dest_path, allow_shared_folder=True, autorename=True)
                    else:
                        failed.append(name)
            except Exception as e:
                st.error(f"❌ {name} のコピーに失敗: {e}")
                failed.append(name)
        if failed:
            st.warning("⚠️ 一部のファイルはエクスポートできませんでした。")
            for f in failed:
                st.write(f"・{f}")
        else:
            st.success("✅ エクスポート完了！")
        save_export_log(st.session_state.selected_files)
