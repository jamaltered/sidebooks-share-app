import streamlit as st
import dropbox
import difflib
import hashlib
import os

# Dropbox 認証
dbx = dropbox.Dropbox(
    app_key=st.secrets["DROPBOX_APP_KEY"],
    app_secret=st.secrets["DROPBOX_APP_SECRET"],
    oauth2_refresh_token=st.secrets["DROPBOX_REFRESH_TOKEN"]
)

# 設定
TARGET_FOLDER = st.secrets["TARGET_FOLDER"]  # 例: "/成年コミック"
EXPORT_FOLDER = st.secrets["EXPORT_FOLDER"]  # 例: "/SideBooksExport"
ZIP_LIST_PATH = "zip_file_list.txt"

# MD5ハッシュでユニークなkeyを生成
def make_safe_key(name: str) -> str:
    return hashlib.md5(name.encode("utf-8")).hexdigest()

# 近似ファイルをリストから探す
def find_similar_file(name, path_list, cutoff=0.7):
    matches = difflib.get_close_matches(name, path_list, n=1, cutoff=cutoff)
    return matches[0] if matches else None

# zip_file_list.txt 読み込み
@st.cache_data
def load_zip_list():
    if not os.path.exists(ZIP_LIST_PATH):
        st.error("⚠️ zip_file_list.txt が見つかりません。アップロードしてください。")
        return []
    with open(ZIP_LIST_PATH, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines()]

# 選択UIと一覧表示
def show_zip_file_list(zip_paths):
    st.session_state.selected_files = st.session_state.get("selected_files", [])
    for full_path in zip_paths:
        name = os.path.basename(full_path)
        key = make_safe_key(name)
        checked = st.checkbox(name, key=f"cb_{key}", value=(name in st.session_state.selected_files))
        if checked and name not in st.session_state.selected_files:
            st.session_state.selected_files.append(name)
        elif not checked and name in st.session_state.selected_files:
            st.session_state.selected_files.remove(name)

# エクスポート処理
def export_selected(zip_paths):
    failed = []
    for name in st.session_state.selected_files:
        original_path = f"{TARGET_FOLDER}/{name}"
        try:
            dbx.files_copy_v2(original_path, f"{EXPORT_FOLDER}/{name}", allow_shared_folder=True, autorename=True)
        except dropbox.exceptions.ApiError:
            match_path = find_similar_file(original_path, zip_paths)
            if match_path:
                try:
                    dbx.files_copy_v2(match_path, f"{EXPORT_FOLDER}/{name}", allow_shared_folder=True, autorename=True)
                except Exception as e:
                    failed.append(f"{name}（近似マッチコピー失敗: {str(e)}）")
            else:
                failed.append(f"{name}（見つからず）")
    return failed

# メイン処理
st.title("📚 SideBooks共有 ZIPエクスポート")

zip_paths = load_zip_list()

if zip_paths:
    st.markdown("### 🔽 ZIP一覧（チェックしてエクスポート）")
    show_zip_file_list(zip_paths)

    if st.session_state.get("selected_files"):
        st.markdown("---")
        st.markdown(f"✅ 選択中：{len(st.session_state.selected_files)} 件")
        if st.button("📤 選択中のZIPをエクスポート"):
            failures = export_selected(zip_paths)
            if failures:
                st.error("一部のファイルでエクスポートに失敗しました：\n" + "\n".join(failures))
            else:
                st.success("✅ エクスポート完了！")
else:
    st.warning("ZIPリストが読み込まれていません。")
