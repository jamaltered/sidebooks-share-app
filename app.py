import os
import re
import hashlib
import difflib
import requests
import streamlit as st
import dropbox

# === Secrets 設定 ===
APP_KEY = st.secrets["DROPBOX_APP_KEY"]
APP_SECRET = st.secrets["DROPBOX_APP_SECRET"]
REFRESH_TOKEN = st.secrets["DROPBOX_REFRESH_TOKEN"]
TARGET_FOLDER = st.secrets["TARGET_FOLDER"]         # 例: /成年コミック
THUMBNAIL_FOLDER = st.secrets["THUMBNAIL_FOLDER"]   # 例: /サムネイル
EXPORT_FOLDER = st.secrets["EXPORT_FOLDER"]         # 例: /SideBooksExport
ZIP_LIST_URL = st.secrets["ZIP_LIST_URL"]

# === Dropbox 接続 ===
dbx = dropbox.Dropbox(
    app_key=APP_KEY,
    app_secret=APP_SECRET,
    oauth2_refresh_token=REFRESH_TOKEN
)

# === zip_file_list.txt をロード ===
@st.cache_data
def load_zip_file_list():
    try:
        res = requests.get(ZIP_LIST_URL)
        res.raise_for_status()
        return res.text.strip().splitlines()
    except Exception as e:
        st.error(f"zip_file_list.txt の取得に失敗しました: {e}")
        return []

zip_paths = load_zip_file_list()

# === ページネーション設定 ===
PAGE_SIZE = 200
max_page = max(1, (len(zip_paths) + PAGE_SIZE - 1) // PAGE_SIZE)
page = st.number_input("ページ番号", min_value=1, max_value=max_page, step=1)

# === セッション状態 ===
if "selected_files" not in st.session_state:
    st.session_state.selected_files = set()

# === 一意キー生成 ===
def make_safe_key(name, fullpath):
    hash_digest = hashlib.md5(fullpath.encode()).hexdigest()
    return f"{name}_{hash_digest[:8]}"

# === 近似パス検索 ===
def find_similar_path(name):
    matches = difflib.get_close_matches(name, zip_paths, n=1, cutoff=0.7)
    return matches[0] if matches else None

# === サムネイル取得 ===
def get_thumbnail_path(name):
    base_name = os.path.splitext(os.path.basename(name))[0]
    candidates = [f"{THUMBNAIL_FOLDER}/{base_name}{ext}" for ext in [".jpg", ".jpeg", ".png", ".webp"]]
    for path in candidates:
        try:
            res = dbx.files_get_temporary_link(path)
            return res.link
        except:
            continue
    return None

# === SideBooksExport を空にする ===
def clear_export_folder():
    try:
        result = dbx.files_list_folder(EXPORT_FOLDER)
        for entry in result.entries:
            dbx.files_delete_v2(entry.path_lower)
    except:
        pass

# === エクスポート処理 ===
def export_selected_files():
    clear_export_folder()
    failed = []
    for name in st.session_state.selected_files:
        src_path = f"{TARGET_FOLDER}/{name}"
        dest_path = f"{EXPORT_FOLDER}/{name}"
        try:
            dbx.files_copy_v2(src_path, dest_path, allow_shared_folder=True, autorename=True)
        except dropbox.exceptions.ApiError:
            similar = find_similar_path(name)
            if similar:
                try:
                    dbx.files_copy_v2(similar, dest_path, allow_shared_folder=True, autorename=True)
                    continue
                except Exception as e:
                    failed.append(name)
            else:
                failed.append(name)
    return failed

# === ↑TOP ボタン ===
st.markdown("""
<a href="#top" class="top-button">↑ Top</a>
<style>
.top-button {
  position: fixed;
  bottom: 24px;
  left: 24px;
  background: #007bff;
  color: white;
  padding: 12px 16px;
  font-size: 18px;
  border-radius: 30px;
  text-decoration: none;
  z-index: 1000;
}
</style>
""", unsafe_allow_html=True)

# === UI描画 ===
start = (page - 1) * PAGE_SIZE
end = start + PAGE_SIZE
visible_items = zip_paths[start:end]

st.title("📚 ZIPファイル一覧")
st.markdown(f"✅ 選択中: {len(st.session_state.selected_files)}")

# === エクスポートボタンを上に表示 ===
if st.session_state.selected_files:
    if st.button("📤 選択中のZIPをエクスポート"):
        fails = export_selected_files()
        if fails:
            st.warning(f"一部ファイルのエクスポートに失敗しました: {fails}")
        else:
            st.success("✅ エクスポート完了！")

# === 一覧表示 ===
for fullpath in visible_items:
    name = os.path.basename(fullpath)
    key = make_safe_key(name, fullpath)
    cols = st.columns([1, 4])
    with cols[0]:
        checked = st.checkbox(name, key=f"cb_{key}", value=(name in st.session_state.selected_files))
        if checked:
            st.session_state.selected_files.add(name)
        else:
            st.session_state.selected_files.discard(name)
    with cols[1]:
        thumb = get_thumbnail_path(name)
        if thumb:
            st.image(thumb, caption=name, use_container_width=True)
        else:
            st.write("❌ サムネイルなし")
