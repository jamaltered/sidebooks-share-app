import streamlit as st
import dropbox
import os
import hashlib
import difflib

# ================== 設定 ==================
APP_KEY = st.secrets["DROPBOX_APP_KEY"]
APP_SECRET = st.secrets["DROPBOX_APP_SECRET"]
REFRESH_TOKEN = st.secrets["DROPBOX_REFRESH_TOKEN"]
TARGET_FOLDER = st.secrets["TARGET_FOLDER"]
EXPORT_FOLDER = st.secrets["EXPORT_FOLDER"]
THUMBNAIL_FOLDER = st.secrets["THUMBNAIL_FOLDER"]
ZIP_LIST_PATH = "/mnt/data/zip_file_list_extracted/zip_file_list.txt"
THUMB_HEIGHT = 500
FILES_PER_PAGE = 40

# ============ Dropbox認証 ===============
from dropbox.oauth import DropboxOAuth2FlowNoRedirect
from dropbox import DropboxOAuth2Flow, Dropbox

dbx = dropbox.Dropbox(
    app_key=APP_KEY,
    app_secret=APP_SECRET,
    oauth2_refresh_token=REFRESH_TOKEN
)

# ============ ユーティリティ関数 ============
def make_safe_key(name, fullpath):
    return hashlib.md5((name + fullpath).encode()).hexdigest()

def get_thumbnail_path(name):
    base = name.rsplit("/", 1)[-1].replace(".zip", "")
    for f in os.listdir(THUMBNAIL_FOLDER):
        if f.startswith(base):
            return os.path.join(THUMBNAIL_FOLDER, f)
    return None

def load_zip_file_list():
    with open(ZIP_LIST_PATH, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip().endswith(".zip")]

def save_export_log(selected):
    log_path = os.path.join(TARGET_FOLDER, "export_log.csv")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("Exported ZIP Files\n")
        for name in selected:
            f.write(name + "\n")

def clear_export_folder():
    try:
        res = dbx.files_list_folder(EXPORT_FOLDER)
        for entry in res.entries:
            dbx.files_delete_v2(entry.path_display)
    except Exception as e:
        st.error(f"エクスポートフォルダの初期化に失敗しました: {e}")

# ============ Streamlit UI開始 ============
st.title("📚 SideBooks ZIPエクスポーター")

# ZIP一覧の読み込み
zip_paths = load_zip_file_list()

# ページネーション
page = st.sidebar.number_input("ページ", 1, (len(zip_paths)-1)//FILES_PER_PAGE + 1, 1)
start = (page - 1) * FILES_PER_PAGE
end = start + FILES_PER_PAGE

# 選択状態保持
if "selected_files" not in st.session_state:
    st.session_state.selected_files = []

def show_zip_file_list():
    st.markdown(f"<a name='top'></a>", unsafe_allow_html=True)
    for i in range(start, min(end, len(zip_paths))):
        fullpath = zip_paths[i]
        name = os.path.basename(fullpath)
        key = make_safe_key(name, fullpath)
        cols = st.columns([1, 5])
        thumb_path = get_thumbnail_path(name)
        if thumb_path and os.path.exists(thumb_path):
            cols[0].image(thumb_path, use_container_width=True, output_format="JPEG", caption="")
        else:
            cols[0].markdown("🖼️ No Thumb")
        checked = cols[1].checkbox(name, key=f"cb_{key}", value=(name in st.session_state.selected_files))
        if checked and name not in st.session_state.selected_files:
            st.session_state.selected_files.append(name)
        elif not checked and name in st.session_state.selected_files:
            st.session_state.selected_files.remove(name)

show_zip_file_list()

# ↑TOPボタン
st.markdown("[⬆ TOPに戻る](#top)", unsafe_allow_html=True)

# エクスポート処理
if st.session_state.selected_files:
    st.markdown("---")
    st.markdown(f"✅ 選択中: {len(st.session_state.selected_files)} ファイル")
    if st.button("📤 選択ZIPをエクスポート"):
        clear_export_folder()
        failed = []

        for name in st.session_state.selected_files:
            matches = [path for path in zip_paths if os.path.basename(path) == name]
            if not matches:
                close = difflib.get_close_matches(name, [os.path.basename(p) for p in zip_paths], n=1, cutoff=0.7)
                if close:
                    match_name = close[0]
                    match_path = next((p for p in zip_paths if os.path.basename(p) == match_name), None)
                else:
                    st.error(f"❌ {name} が見つかりませんでした。")
                    failed.append(name)
                    continue
            else:
                match_path = matches[0]

            src_path = match_path
            dest_path = f"{EXPORT_FOLDER}/{name}"
            try:
                dbx.files_copy_v2(src_path, dest_path, allow_shared_folder=True, autorename=True)
            except Exception as e:
                st.error(f"❌ コピー失敗: {name}: {e}")
                failed.append(name)

        save_export_log(st.session_state.selected_files)
        if failed:
            st.warning(f"⚠️ 一部ファイルに失敗: {len(failed)} 件")
        else:
            st.success("✅ エクスポート完了！")
