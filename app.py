import streamlit as st
import dropbox
import difflib
import hashlib
import os

# ================== 認証・初期設定 ==================
APP_KEY = st.secrets["DROPBOX_APP_KEY"]
APP_SECRET = st.secrets["DROPBOX_APP_SECRET"]
REFRESH_TOKEN = st.secrets["DROPBOX_REFRESH_TOKEN"]
TARGET_FOLDER = st.secrets["TARGET_FOLDER"]  # 例: "/成年コミック"
EXPORT_FOLDER = st.secrets["EXPORT_FOLDER"]  # 例: "/SideBooksExport"
THUMBNAIL_FOLDER = st.secrets["THUMBNAIL_FOLDER"]  # 例: "/サムネイル"
ZIP_LIST_PATH = "zip_file_list.txt"

dbx = dropbox.Dropbox(
    app_key=APP_KEY,
    app_secret=APP_SECRET,
    oauth2_refresh_token=REFRESH_TOKEN,
)

# ================== ヘルパー関数 ==================
def make_safe_key(name):
    return hashlib.md5(name.encode()).hexdigest()

def get_thumbnail_path(zip_name):
    thumb_name = os.path.splitext(zip_name)[0] + ".jpg"
    return f"{THUMBNAIL_FOLDER}/{thumb_name}"

def save_export_log(exported_files):
    log_path = f"{TARGET_FOLDER}/export_log.csv"
    content = "\n".join(exported_files)
    dbx.files_upload(content.encode("utf-8"), log_path, mode=dropbox.files.WriteMode.overwrite)

def clear_export_folder():
    try:
        res = dbx.files_list_folder(EXPORT_FOLDER)
        for entry in res.entries:
            dbx.files_delete_v2(entry.path_lower)
    except Exception as e:
        st.error(f"❌ エクスポートフォルダの削除失敗: {e}")

def load_zip_list():
    with open(ZIP_LIST_PATH, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines()]

def find_closest_match(filename, zip_paths):
    matches = difflib.get_close_matches(filename, zip_paths, n=1, cutoff=0.7)
    return matches[0] if matches else None

# ================== UI表示 ==================
st.title("📚 SideBooks ZIP エクスポートアプリ")

if "selected_files" not in st.session_state:
    st.session_state.selected_files = []

zip_paths = load_zip_list()
zip_names = [os.path.basename(p) for p in zip_paths]

# ======= エクスポートボタン先に =======
if st.session_state.selected_files:
    st.markdown("### ✅ 選択中のZIPファイル")
    for file in st.session_state.selected_files:
        st.markdown(f"- {file}")

    if st.button("📤 エクスポート実行"):
        clear_export_folder()  # ← ここでフォルダを空に
        failed = []
        for name in st.session_state.selected_files:
            match_path = find_closest_match(f"{TARGET_FOLDER}/{name}", zip_paths)
            if match_path:
                try:
                    dest_path = f"{EXPORT_FOLDER}/{name}"
                    dbx.files_copy_v2(match_path, dest_path, allow_shared_folder=True, autorename=True)
                except Exception as e:
                    st.error(f"❌ {name} のコピーに失敗: {e}")
                    failed.append(name)
            else:
                st.error(f"❌ {name} に近いファイルが見つかりませんでした")
                failed.append(name)
        if not failed:
            st.success("✅ エクスポート完了しました")
        else:
            st.warning(f"⚠️ 一部ファイルのエクスポートに失敗しました")
        save_export_log(st.session_state.selected_files)

# ======= ZIPリスト表示 =======
st.markdown("---")
st.subheader("📦 ZIPファイル一覧")

def show_zip_file_list():
    for name in zip_names:
        key = make_safe_key(name)
        checked = st.checkbox(name, key=f"cb_{key}", value=name in st.session_state.selected_files)
        if checked and name not in st.session_state.selected_files:
            st.session_state.selected_files.append(name)
        elif not checked and name in st.session_state.selected_files:
            st.session_state.selected_files.remove(name)

        thumb_path = get_thumbnail_path(name)
        try:
            metadata, res = dbx.files_download(thumb_path)
            st.image(res.content, caption=name, use_container_width=True)
        except:
            st.info(f"サムネイルなし: {name}")

show_zip_file_list()
