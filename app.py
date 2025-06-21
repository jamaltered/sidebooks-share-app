import streamlit as st
import dropbox
import hashlib
import os
import difflib

# --- Dropbox認証 ---
dbx = dropbox.Dropbox(
    app_key=st.secrets["DROPBOX_APP_KEY"],
    app_secret=st.secrets["DROPBOX_APP_SECRET"],
    oauth2_refresh_token=st.secrets["DROPBOX_REFRESH_TOKEN"]
)

TARGET_FOLDER = st.secrets["TARGET_FOLDER"]
EXPORT_FOLDER = st.secrets["EXPORT_FOLDER"]
THUMBNAIL_FOLDER = st.secrets["THUMBNAIL_FOLDER"]
ZIP_LIST_PATH = "zip_file_list.txt"  # GitHub上に配置した想定

# --- セッション初期化 ---
if "selected_files" not in st.session_state:
    st.session_state.selected_files = []

# --- 安全なキー生成 ---
def make_safe_key(name, fullpath):
    return hashlib.md5(f"{name}_{fullpath}".encode()).hexdigest()

# --- サムネイルパス取得 ---
def get_thumbnail_path(name):
    base = os.path.splitext(name)[0]
    safe_name = base.replace("/", "_").replace("\\", "_")
    return f"{THUMBNAIL_FOLDER}/{safe_name}.jpg"

# --- zip_file_list.txtの読み込み ---
def load_zip_file_list():
    try:
        with open(ZIP_LIST_PATH, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    except Exception:
        st.error("zip_file_list.txt の取得に失敗しました。")
        st.stop()

# --- エクスポートログ保存 ---
def save_export_log(exported_list):
    try:
        log_path = os.path.join(TARGET_FOLDER, "export_log.csv")
        log_text = "\n".join(exported_list)
        dbx.files_upload(log_text.encode("utf-8"), log_path, mode=dropbox.files.WriteMode("overwrite"))
    except Exception as e:
        st.warning(f"エクスポートログの保存に失敗しました: {e}")

# --- 近似ファイル検索 ---
def find_similar_path(name, full_list):
    matches = difflib.get_close_matches(name, full_list, n=1, cutoff=0.7)
    return matches[0] if matches else None

# --- エクスポート実行 ---
def export_selected_files(selected, zip_paths):
    # エクスポート先を毎回クリア
    try:
        for entry in dbx.files_list_folder(EXPORT_FOLDER).entries:
            dbx.files_delete_v2(f"{EXPORT_FOLDER}/{entry.name}")
    except Exception as e:
        st.warning(f"エクスポートフォルダの初期化に失敗: {e}")

    failed = []
    for name in selected:
        match = find_similar_path(f"{TARGET_FOLDER}/{name}", zip_paths)
        if match:
            try:
                dbx.files_copy_v2(match, f"{EXPORT_FOLDER}/{name}", allow_shared_folder=True, autorename=True)
            except Exception as e:
                st.error(f"❌ {name} のコピーに失敗: {e}")
                failed.append(name)
        else:
            st.error(f"❌ {name} のコピー元が見つかりませんでした。")
            failed.append(name)

    if failed:
        st.warning(f"{len(failed)} 件のエクスポートに失敗しました。")
    else:
        st.success("✅ エクスポートが完了しました。")

    save_export_log(selected)

# --- 一覧表示 ---
def show_zip_file_list(zip_paths):
    page_size = 30
    total_pages = max(1, (len(zip_paths) - 1) // page_size + 1)

    st.markdown("---")
    page = st.number_input("ページ番号", min_value=1, max_value=total_pages, step=1)
    start = (page - 1) * page_size
    end = min(start + page_size, len(zip_paths))

    for fullpath in zip_paths[start:end]:
        name = os.path.basename(fullpath)
        key = make_safe_key(name, fullpath)
        cols = st.columns([1, 6])
        with cols[0]:
            checked = st.checkbox("選択", key=f"cb_{key}", value=(name in st.session_state.selected_files))
            if checked and name not in st.session_state.selected_files:
                st.session_state.selected_files.append(name)
            elif not checked and name in st.session_state.selected_files:
                st.session_state.selected_files.remove(name)
        with cols[1]:
            thumbnail_path = get_thumbnail_path(name)
            st.image(thumbnail_path, caption=name, use_container_width=True)

    st.markdown('<a href="#top">↑Top</a>', unsafe_allow_html=True)

# --- アプリ本体 ---
st.set_page_config(page_title="SideBooks共有", layout="wide")
st.markdown('<h1 id="top">📚 コミック一覧</h1>', unsafe_allow_html=True)

zip_paths = load_zip_file_list()

# エクスポートボタン（常時表示）
st.markdown("### ✅選択中: " + str(len(st.session_state.selected_files)))
if st.button("📤 選択中のZIPをエクスポート"):
    export_selected_files(st.session_state.selected_files, zip_paths)

# ZIPリスト表示
show_zip_file_list(zip_paths)
