import os
import re
import dropbox
import streamlit as st
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()
APP_KEY = os.getenv("DROPBOX_APP_KEY")
APP_SECRET = os.getenv("DROPBOX_APP_SECRET")
REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN")

# Dropboxクライアントの初期化
dbx = dropbox.Dropbox(
    app_key=APP_KEY,
    app_secret=APP_SECRET,
    oauth2_refresh_token=REFRESH_TOKEN
)

# フォルダ設定
TARGET_FOLDER = "/成年コミック"
THUMBNAIL_FOLDER = "/サムネイル"
EXPORT_FOLDER = "/SideBooksExport"

st.set_page_config(page_title="コミック一覧", layout="wide")

# 初期状態
if "selected_files" not in st.session_state:
    st.session_state.selected_files = set()

selected_count = len(st.session_state.selected_files)

# ユーザー名取得
try:
    user_name = dbx.users_get_current_account().name.display_name
except Exception:
    st.warning("Dropboxの認証情報が不足しています")
    st.stop()

# ヘッダー + エクスポートボタン（追従ヘッダー）
st.markdown(f"""
<style>
.sticky-header {{
  position: sticky;
  top: 0;
  z-index: 999;
  background-color: white;
  padding: 0.5rem;
  border-bottom: 1px solid #ddd;
}}
.sticky-header strong {{
  color: #007bff;
}}
</style>
<div class='sticky-header'>
  <h2 style='margin: 0; font-size: 1.2rem;'>📚 コミック一覧</h2>
  <div style='margin-top: 4px;'>
    <strong style='color:#444;'>✅ 選択中: {selected_count}</strong>
  </div>
""", unsafe_allow_html=True)

# 選択済み表示・エクスポートボタン（ヘッダーの下に移動）
if st.session_state.selected_files:
    with st.container():
        st.markdown("### ✅ 選択されたZIPファイル：")
        for f in sorted(st.session_state.selected_files):
            st.write(f)
        if st.button("📤 SideBooksExport にエクスポート"):
            def export_selected_files(selected_names):
                clear_export_folder()
                for name in selected_names:
                    src_path = f"{TARGET_FOLDER}/{name}"
                    dst_path = f"{EXPORT_FOLDER}/{name}"
                    try:
                        dbx.files_copy_v2(src_path, dst_path, allow_shared_folder=True, autorename=True)
                    except Exception as e:
                        st.error(f"{name} のコピーに失敗しました: {e}")

            def clear_export_folder():
                try:
                    result = dbx.files_list_folder(EXPORT_FOLDER)
                    for entry in result.entries:
                        dbx.files_delete_v2(entry.path_lower)
                    while result.has_more:
                        result = dbx.files_list_folder_continue(result.cursor)
                        for entry in result.entries:
                            dbx.files_delete_v2(entry.path_lower)
                except Exception as e:
                    st.error(f"エクスポートフォルダの削除に失敗しました: {e}")

            export_selected_files(st.session_state.selected_files)
            st.success("SideBooksExport に保存しました！")

st.markdown("</div>", unsafe_allow_html=True)

# ZIPファイル一覧の取得
def list_zip_files():
    zip_files = []
    try:
        result = dbx.files_list_folder(TARGET_FOLDER, recursive=True)
        zip_files.extend([entry for entry in result.entries if entry.name.endswith(".zip")])
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            zip_files.extend([entry for entry in result.entries if entry.name.endswith(".zip")])
    except Exception as e:
        st.error(f"ZIPファイルの取得に失敗: {e}")
    return zip_files

# サムネイル一覧の取得
def list_thumbnails():
    thumbnails = []
    try:
        result = dbx.files_list_folder(THUMBNAIL_FOLDER)
        thumbnails.extend([entry.name for entry in result.entries if entry.name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            thumbnails.extend([entry.name for entry in result.entries if entry.name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
    except Exception as e:
        st.error(f"サムネイルの取得に失敗: {e}")
    return thumbnails

# 一時リンク取得
def get_temporary_image_url(path):
    try:
        res = dbx.files_get_temporary_link(path)
        return res.link
    except:
        return None

# ZIPとサムネイル一覧取得
zip_files = list_zip_files()
thumbnails = list_thumbnails()
zip_set = {entry.name for entry in zip_files}

# グリッド表示（5列）
cols_per_row = 5
columns = st.columns(cols_per_row)
i = 0

for thumb in sorted(thumbnails):
    zip_name = thumb.rsplit('.', 1)[0] + ".zip"
    if zip_name not in zip_set:
        continue

    title_display = re.sub(r"^\(成年コミック\)\s*", "", zip_name.replace(".zip", ""))
    thumb_path = f"{THUMBNAIL_FOLDER}/{thumb}"
    url = get_temporary_image_url(thumb_path)

    if url:
        col = columns[i % cols_per_row]
        with col:
            st.markdown("""
                <div style='border:1px solid #ddd; border-radius:10px; padding:10px; margin:8px; background-color:#ffffff; text-align:center;'>
            """, unsafe_allow_html=True)

            st.image(url, use_container_width=True)
            st.markdown(f"<div style='font-size: 0.85rem; margin: 6px 0;'>{title_display}</div>", unsafe_allow_html=True)

            checked = zip_name in st.session_state.selected_files
            if st.checkbox("選択", value=checked, key=zip_name):
                st.session_state.selected_files.add(zip_name)
            else:
                st.session_state.selected_files.discard(zip_name)

            st.markdown("""</div>""", unsafe_allow_html=True)
        i += 1
