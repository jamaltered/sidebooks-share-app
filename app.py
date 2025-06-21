import streamlit as st
import dropbox
import hashlib
import difflib
import os
import re
import requests

# --- Dropbox認証 ---
dbx = dropbox.Dropbox(
    app_key=st.secrets["DROPBOX_APP_KEY"],
    app_secret=st.secrets["DROPBOX_APP_SECRET"],
    oauth2_refresh_token=st.secrets["DROPBOX_REFRESH_TOKEN"]
)

TARGET_FOLDER = st.secrets["TARGET_FOLDER"]
EXPORT_FOLDER = st.secrets["EXPORT_FOLDER"]
THUMBNAIL_FOLDER = st.secrets["THUMBNAIL_FOLDER"]
ZIP_LIST_URL = st.secrets["ZIP_LIST_URL"]

# --- ZIPファイル一覧を取得 ---
@st.cache_data
def load_zip_file_list():
    try:
        response = requests.get(ZIP_LIST_URL)
        response.raise_for_status()
        return [line.strip() for line in response.text.splitlines() if line.strip().endswith(".zip")]
    except Exception:
        st.error("zip_file_list.txt の取得に失敗しました。")
        return []

# --- サムネイルのリネーム規則に合わせて変換 ---
def normalize_filename(zip_name):
    match = re.match(r"^\(.*?\)\s*\[(.+?)\]\s*(.+?)\.zip$", zip_name)
    if match:
        author, title = match.groups()
        return f"[{author}] {title}".strip()
    else:
        return os.path.splitext(zip_name)[0]

# --- サムネイルパスを取得 ---
def get_thumbnail_path(zip_name):
    thumb_name = normalize_filename(zip_name)
    return f"{THUMBNAIL_FOLDER}/{thumb_name}.jpg"

# --- Dropbox一時リンク取得 ---
@st.cache_data(ttl=600)
def get_temp_link(dropbox_path):
    try:
        metadata = dbx.files_get_temporary_link(dropbox_path)
        return metadata.link
    except:
        return None

# --- ハッシュキー生成（重複回避用） ---
def make_safe_key(name, fullpath):
    hash_digest = hashlib.md5(fullpath.encode()).hexdigest()
    return f"{hash_digest}"

# --- 選択ファイルのログ保存 ---
def save_export_log(selected_files):
    log_text = "\n".join(selected_files)
    dbx.files_upload(log_text.encode("utf-8"), f"{TARGET_FOLDER}/export_log.csv", mode=dropbox.files.WriteMode.overwrite)

# --- フォルダを空にして再作成 ---
def clear_export_folder():
    try:
        dbx.files_delete_v2(EXPORT_FOLDER)
    except:
        pass
    dbx.files_create_folder_v2(EXPORT_FOLDER)

# --- ZIPファイル一覧表示 ---
def show_zip_file_list(zip_paths):
    page_size = 50
    max_page = max(1, (len(zip_paths) - 1) // page_size + 1)
    page = st.number_input("ページ番号", min_value=1, max_value=max_page, step=1)
    start = (page - 1) * page_size
    end = min(start + page_size, len(zip_paths))

    st.markdown('<a href="#top">↑TOP</a>', unsafe_allow_html=True)

    for full_path in zip_paths[start:end]:
        name = os.path.basename(full_path)
        key = make_safe_key(name, full_path)
        checked = st.checkbox(name, key=f"cb_{key}", value=(name in st.session_state.selected_files))
        if checked and name not in st.session_state.selected_files:
            st.session_state.selected_files.append(name)
        elif not checked and name in st.session_state.selected_files:
            st.session_state.selected_files.remove(name)

        thumb_path = get_thumbnail_path(name)
        thumb_url = get_temp_link(thumb_path)
        if thumb_url:
            st.image(thumb_url, caption=name, use_container_width=True)
        else:
            st.markdown("*サムネイルなし*")

# --- 近似一致でDropboxパス検索 ---
def find_similar_dropbox_path(name, path_list):
    matches = difflib.get_close_matches(name, path_list, n=1, cutoff=0.7)
    return matches[0] if matches else None

# --- メイン処理 ---
st.set_page_config(page_title="SideBooks Export", layout="wide")
st.title("📚 SideBooks Exporter")
st.markdown('<div id="top"></div>', unsafe_allow_html=True)

if "selected_files" not in st.session_state:
    st.session_state.selected_files = []

zip_paths = load_zip_file_list()

# --- 選択数とエクスポートボタン ---
st.markdown(f"### 選択中：{len(st.session_state.selected_files)} 件")
if st.session_state.selected_files:
    if st.button("📤 選択中のZIPをエクスポート"):
        clear_export_folder()
        failed = []
        for name in st.session_state.selected_files:
            match_path = find_similar_dropbox_path(f"{TARGET_FOLDER}/{name}", zip_paths)
            if match_path:
                try:
                    dbx.files_copy_v2(match_path, f"{EXPORT_FOLDER}/{name}", allow_shared_folder=True, autorename=True)
                except Exception as e:
                    st.error(f"❌ {name} のコピーに失敗: {e}")
                    failed.append(name)
            else:
                st.error(f"❌ {name} が見つかりませんでした。")
                failed.append(name)
        save_export_log(st.session_state.selected_files)
        if not failed:
            st.success("✅ エクスポートが完了しました。")
        else:
            st.warning(f"⚠️ 一部失敗しました（{len(failed)} 件）")

st.divider()
show_zip_file_list(zip_paths)
