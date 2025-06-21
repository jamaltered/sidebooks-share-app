import streamlit as st
import dropbox
import hashlib
import os
from difflib import get_close_matches

# Dropbox接続（リフレッシュトークン方式）
dbx = dropbox.Dropbox(
    app_key=st.secrets["DROPBOX_APP_KEY"],
    app_secret=st.secrets["DROPBOX_APP_SECRET"],
    oauth2_refresh_token=st.secrets["DROPBOX_REFRESH_TOKEN"]
)

TARGET_FOLDER = st.secrets["TARGET_FOLDER"]
EXPORT_FOLDER = st.secrets["EXPORT_FOLDER"]
THUMBNAIL_FOLDER = st.secrets["THUMBNAIL_FOLDER"]
ZIP_LIST_PATH = "zip_file_list.txt"

# セッション状態の初期化
if "selected_files" not in st.session_state:
    st.session_state.selected_files = []

# セーフキー生成（重複回避）
def make_safe_key(name, fullpath):
    hash_digest = hashlib.md5(fullpath.encode("utf-8")).hexdigest()
    return f"{hash_digest}"

# サムネイルの取得
def get_thumbnail_path(zip_path):
    base_name = os.path.basename(zip_path)
    thumb_path = f"{THUMBNAIL_FOLDER}/{base_name}.jpg"
    return thumb_path

# ZIPファイル一覧の読み込み
def load_zip_list():
    with open(ZIP_LIST_PATH, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip().endswith(".zip")]

# エクスポートログの保存
def save_export_log(file_list):
    log_path = f"{TARGET_FOLDER}/export_log.csv"
    content = "\n".join(file_list)
    dbx.files_upload(content.encode("utf-8"), log_path, mode=dropbox.files.WriteMode.overwrite)

# エクスポート先フォルダの初期化
def clear_export_folder():
    try:
        res = dbx.files_list_folder(EXPORT_FOLDER)
        for entry in res.entries:
            dbx.files_delete_v2(entry.path_lower)
    except Exception as e:
        st.warning(f"エクスポートフォルダの初期化に失敗: {e}")

# ZIP一覧の表示
def show_zip_file_list(zip_paths):
    cols = st.columns(2)
    for idx, fullpath in enumerate(zip_paths):
        filename = os.path.basename(fullpath)
        key = make_safe_key(filename, fullpath)
        col = cols[idx % 2]
        with col:
            thumb_path = get_thumbnail_path(fullpath)
            try:
                metadata, res = dbx.files_download(thumb_path)
                col.image(res.content, use_container_width=True)
            except:
                col.write("（サムネイルなし）")

            col.write(f"{filename}")
            checked = st.checkbox("選択", key=f"cb_{key}", value=(filename in st.session_state.selected_files))
            if checked and filename not in st.session_state.selected_files:
                st.session_state.selected_files.append(filename)
            elif not checked and filename in st.session_state.selected_files:
                st.session_state.selected_files.remove(filename)

# 題名表示とエクスポートUI
st.title("📚 コミック一覧")

st.markdown(f"✅選択中: {len(st.session_state.selected_files)}")
if st.session_state.selected_files:
    if st.button("📤 選択中のZIPをエクスポート", type="primary"):
        failed = []
        clear_export_folder()
        for name in st.session_state.selected_files:
            matched = [path for path in zip_paths if os.path.basename(path) == name]
            src_path = matched[0] if matched else None
            if not src_path:
                close = get_close_matches(name, zip_paths, n=1, cutoff=0.7)
                if close:
                    src_path = close[0]
            if not src_path:
                st.error(f"❌ {name} のコピー元が見つかりませんでした。")
                failed.append(name)
                continue
            dest_path = f"{EXPORT_FOLDER}/{name}"
            try:
                dbx.files_copy_v2(src_path, dest_path, allow_shared_folder=True, autorename=True)
            except Exception as e:
                st.error(f"❌ {name} のコピーに失敗: {e}")
                failed.append(name)
        if failed:
            st.warning(f"{len(failed)}件のエクスポートに失敗しました。")
        else:
            st.success("✅ エクスポートが完了しました。")
        save_export_log(st.session_state.selected_files)

# ZIPファイルリストをロードして表示
try:
    zip_paths = load_zip_list()
    show_zip_file_list(zip_paths)
except Exception as e:
    st.error(f"ZIP一覧の読み込みに失敗しました: {e}")
