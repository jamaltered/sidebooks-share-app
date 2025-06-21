import streamlit as st
import os
import dropbox
import difflib
from PIL import Image
from io import BytesIO
import pandas as pd

# --- 設定 ---
TARGET_FOLDER = "/成年コミック"
EXPORT_FOLDER = "/SideBooksExport"
THUMBNAIL_FOLDER = "/サムネイル"
ZIP_LIST_PATH = "zip_file_list.txt"

# --- Dropbox 認証（Secrets 使用） ---
ACCESS_TOKEN = st.secrets["DROPBOX_ACCESS_TOKEN"]
dbx = dropbox.Dropbox(ACCESS_TOKEN)

# --- 事前読み込み：ファイル一覧（zip_file_list.txt から） ---
@st.cache_data
def load_zip_file_list():
    try:
        with open(ZIP_LIST_PATH, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines()]
    except FileNotFoundError:
        return []

zip_full_path_list = load_zip_file_list()

# --- タイトル抽出用ユーティリティ ---
def extract_display_title(file_path):
    base = os.path.basename(file_path)
    if base.startswith("("):
        return base
    # "[author] title" を "[author] title" に整える（必要に応じてここを調整）
    return base

# --- サムネイル取得 ---
def get_thumbnail(zip_name):
    thumb_path = f"{THUMBNAIL_FOLDER}/{zip_name.replace('.zip', '.jpg')}"
    try:
        md, res = dbx.files_download(thumb_path)
        return Image.open(BytesIO(res.content))
    except:
        return None

# --- エクスポートログ保存 ---
def save_export_log(selected_files):
    df = pd.DataFrame({"filename": selected_files})
    dbx.files_upload(df.to_csv(index=False).encode("utf-8"),
                     f"{TARGET_FOLDER}/export_log.csv",
                     mode=dropbox.files.WriteMode("overwrite"))

# --- エクスポート処理（近似検索付き） ---
def export_files(selected_files):
    failed = []
    for filename in selected_files:
        matched_path = difflib.get_close_matches(f"{TARGET_FOLDER}/{filename}", zip_full_path_list, n=1, cutoff=0.7)
        if matched_path:
            src_path = matched_path[0]
            dest_path = f"{EXPORT_FOLDER}/{filename}"
            try:
                dbx.files_copy_v2(src_path, dest_path, allow_shared_folder=True, autorename=True)
            except Exception as e:
                st.error(f"❌ {filename} のコピーに失敗: {e}")
                failed.append(filename)
        else:
            st.error(f"❌ {filename} の類似ファイルが見つかりませんでした。")
            failed.append(filename)

    save_export_log(selected_files)
    return failed

# --- UI ---
st.set_page_config(layout="wide")
st.title("📚 成年コミック共有")

# --- ファイル一覧の取得 ---
@st.cache_data
def list_zip_files():
    try:
        result = dbx.files_list_folder(TARGET_FOLDER, recursive=True)
        return [entry.path_display for entry in result.entries if entry.name.endswith(".zip")]
    except Exception as e:
        st.error(f"フォルダ取得エラー: {e}")
        return []

all_files = list_zip_files()
filtered_files = sorted(set(os.path.basename(path) for path in all_files))

# --- セッション状態 ---
if "selected_files" not in st.session_state:
    st.session_state.selected_files = []

# --- チェックボックス表示 + サムネイル ---
cols = st.columns(2)
for i, file_name in enumerate(filtered_files):
    col = cols[i % 2]
    with col:
        checked = st.checkbox(file_name, key=file_name)
        if checked:
            if file_name not in st.session_state.selected_files:
                st.session_state.selected_files.append(file_name)
        else:
            if file_name in st.session_state.selected_files:
                st.session_state.selected_files.remove(file_name)

        thumb = get_thumbnail(file_name)
        if thumb:
            st.image(thumb, caption=file_name, use_container_width=True)

# --- エクスポートボタン ---
st.markdown("### 📤 選択中のZIPをエクスポート")
if st.button("✅ エクスポート開始"):
    if st.session_state.selected_files:
        with st.spinner("エクスポート中..."):
            failed = export_files(st.session_state.selected_files)
            if failed:
                st.error(f"{len(failed)} 件のファイルのエクスポートに失敗しました。")
            else:
                st.success("✅ エクスポート完了！")
    else:
        st.warning("ファイルが選択されていません。")
