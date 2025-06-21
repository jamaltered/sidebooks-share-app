
import os
import re
import difflib
import dropbox
import streamlit as st
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()
APP_KEY = os.getenv("DROPBOX_APP_KEY")
APP_SECRET = os.getenv("DROPBOX_APP_SECRET")
REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN")

dbx = dropbox.Dropbox(app_key=APP_KEY, app_secret=APP_SECRET, oauth2_refresh_token=REFRESH_TOKEN)

TARGET_FOLDER = "/成年コミック"
THUMBNAIL_FOLDER = "/サムネイル"
EXPORT_FOLDER = "/SideBooksExport"
LOG_PATH = f"{TARGET_FOLDER}/export_log.csv"
ZIP_LIST_PATH = os.path.join("zip_file_list.txt")

st.set_page_config(page_title="コミック一覧", layout="wide")

# 初期状態
if "selected_files" not in st.session_state:
    st.session_state.selected_files = set()

# サムネイル一覧
def list_thumbnails():
    try:
        result = dbx.files_list_folder(THUMBNAIL_FOLDER)
        thumbs = [entry.name for entry in result.entries if entry.name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            thumbs.extend([entry.name for entry in result.entries if entry.name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
        return thumbs
    except Exception as e:
        st.error(f"サムネイルの取得に失敗: {e}")
        return []

# 一時リンク取得
def get_temporary_image_url(path):
    try:
        res = dbx.files_get_temporary_link(path)
        return res.link
    except:
        return None

# エクスポートログ保存
def save_export_log(filenames):
    try:
        import pandas as pd
        from io import StringIO
        csv_content = StringIO()
        df = pd.DataFrame({"filename": list(filenames)})
        df.to_csv(csv_content, index=False)
        dbx.files_upload(csv_content.getvalue().encode(), LOG_PATH, mode=dropbox.files.WriteMode.overwrite)
    except Exception as e:
        st.error(f"ログ保存失敗: {e}")

# zip_file_list.txt 読み込み
def load_zip_file_list():
    try:
        with open(ZIP_LIST_PATH, "r", encoding="utf-8") as f:
            return [line.strip().split("/")[-1] for line in f.readlines()]
    except:
        return []

zip_file_list = load_zip_file_list()
thumbnails = list_thumbnails()
visible_thumbs = sorted(thumbnails)

st.markdown("### 📚 コミック一覧")
st.markdown(f"✅選択中: {len(st.session_state.selected_files)}")

if st.session_state.selected_files:
    if st.button("📤 選択中のZIPをエクスポート", type="primary"):
        failed = []
        for name in st.session_state.selected_files:
            try:
                src_path = f"{TARGET_FOLDER}/{name}"
                dest_path = f"{EXPORT_FOLDER}/{name}"
                dbx.files_copy_v2(src_path, dest_path, allow_shared_folder=True, autorename=True)
            except dropbox.exceptions.ApiError:
                # 近似検索
                candidates = difflib.get_close_matches(name, zip_file_list, n=1, cutoff=0.7)
                if candidates:
                    try:
                        src_alt = f"{TARGET_FOLDER}/{candidates[0]}"
                        dest_alt = f"{EXPORT_FOLDER}/{name}"
                        dbx.files_copy_v2(src_alt, dest_alt, allow_shared_folder=True, autorename=True)
                        st.warning(f"⚠️ {name} の代わりに {candidates[0]} をコピーしました。")
                    except Exception as e:
                        st.error(f"❌ {name} のコピーに失敗: {e}")
                        failed.append(name)
                else:
                    st.error(f"❌ {name} のコピー元が見つかりませんでした。")
                    failed.append(name)
        save_export_log(st.session_state.selected_files)
        if failed:
            st.warning(f"{len(failed)} 件のエクスポートに失敗しました。")
        else:
            st.success("✅ エクスポート完了しました。")

# サムネイル表示
for name in visible_thumbs:
    zip_name = os.path.splitext(name)[0] + ".zip"
    image_path = f"{THUMBNAIL_FOLDER}/{name}"
    image_url = get_temporary_image_url(image_path)
    col1, col2 = st.columns([1, 5])
    with col1:
        checked = st.checkbox("選択", key=zip_name, value=zip_name in st.session_state.selected_files)
        if checked:
            st.session_state.selected_files.add(zip_name)
        else:
            st.session_state.selected_files.discard(zip_name)
    with col2:
        if image_url:
            st.image(image_url, caption=zip_name, use_column_width=True)
