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
LOG_PATH = f"{THUMBNAIL_FOLDER}/export_log.csv"

st.set_page_config(page_title="コミック一覧", layout="wide")

# セッション初期化
if "selected_files" not in st.session_state:
    st.session_state.selected_files = set()
if "page" not in st.session_state:
    st.session_state.page = 1

selected_count = len(st.session_state.selected_files)

# サムネイル取得・ページ処理
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

def get_temporary_image_url(path):
    try:
        res = dbx.files_get_temporary_link(path)
        return res.link
    except:
        return None

zip_files = list_zip_files()
thumbnails = list_thumbnails()
zip_set = {entry.name for entry in zip_files}

# ページネーション
PER_PAGE = 200
max_pages = (len(thumbnails) + PER_PAGE - 1) // PER_PAGE
current_page = st.session_state.page

col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if st.button("⬅ 前へ") and current_page > 1:
        st.session_state.page = current_page - 1
with col2:
    selected = st.selectbox("ページ番号", options=list(range(1, max_pages + 1)), index=current_page - 1)
    st.session_state.page = selected
with col3:
    if st.button("次へ ➡") and current_page < max_pages:
        st.session_state.page = current_page + 1

page = st.session_state.page
start_idx = (page - 1) * PER_PAGE
end_idx = start_idx + PER_PAGE
visible_thumbs = sorted(thumbnails)[start_idx:end_idx]

# トップリンク
st.markdown("<div id='top'></div>", unsafe_allow_html=True)

# User情報取得
try:
    user_name = dbx.users_get_current_account().name.display_name
except Exception:
    st.warning("Dropboxの認証情報が不足しています")
    st.stop()

user_agent = "unknown"  # Streamlit Cloudでは取得不可のため仮

# トグル処理
def toggle_selection(zip_name):
    if zip_name in st.session_state and st.session_state[zip_name]:
        st.session_state.selected_files.add(zip_name)
    else:
        st.session_state.selected_files.discard(zip_name)

# ヘッダー表示
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

# 選択されたファイル表示とエクスポート
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
                write_export_log(selected_names)

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

            def write_export_log(selected_names):
                from datetime import datetime
                from pytz import timezone
                import io
                import csv
                now = datetime.now(timezone("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S")
                log_data = io.StringIO()
                writer = csv.writer(log_data)
                writer.writerow(["timestamp", "user", "device", "filename"])
                for name in selected_names:
                    writer.writerow([now, user_name, user_agent, name])
                log_content = log_data.getvalue()

                try:
                    _, res = dbx.files_download(LOG_PATH)
                    existing = res.content.decode("utf-8")
                except:
                    existing = ""
                combined = existing.strip() + "\n" + log_content.strip() + "\n"

                try:
                    dbx.files_upload(combined.encode("utf-8"), LOG_PATH, mode=dropbox.files.WriteMode.overwrite)
                except Exception as e:
                    st.error(f"ログ書き込み失敗: {e}")

            export_selected_files(st.session_state.selected_files)
            st.success("SideBooksExport に保存しました！")

st.markdown("</div>", unsafe_allow_html=True)

# スマホ対応レスポンシブCSS + サムネイル表示
st.markdown("""
<style>
.thumb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 16px;
  margin-top: 1rem;
}
.thumb-card {
  background-color: #fff;
  padding: 10px;
  border-radius: 8px;
  box-shadow: 0 0 6px rgba(0,0,0,0.1);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.thumb-card img {
  width: 100%;
  height: auto;
  border-radius: 6px;
}
.thumb-title {
  font-size: 0.85rem;
  font-weight: bold;
  margin-top: 8px;
  color: #111;
  text-align: center;
}
.top-button {
  position: fixed;
  bottom: 24px;
  left: 24px;
  background: #007bff;
  color: white;
  padding: 12px 16px;
  font-size: 18px;
  border-radius: 50px;
  text-decoration: none;
  z-index: 9999;
  box-shadow: 0 2px 6px rgba(0,0,0,0.2);
}
</style>
<div class="thumb-grid">
""", unsafe_allow_html=True)

for thumb in visible_thumbs:
    zip_name = thumb.rsplit('.', 1)[0] + ".zip"
    if zip_name not in zip_set:
        continue

    title_display = re.sub(r"^\\(成年コミック\\)\\s*", "", zip_name.replace(".zip", ""))
    url = get_temporary_image_url(f"{THUMBNAIL_FOLDER}/{thumb}")
    if not url:
        continue

    st.markdown(f"""
    <div class="thumb-card">
      <img src="{url}" />
      <div class="thumb-title">{title_display}</div>
    </div>
    """, unsafe_allow_html=True)

    st.checkbox("選択", value=zip_name in st.session_state.selected_files,
                key=zip_name, on_change=toggle_selection, args=(zip_name,))

st.markdown("</div>", unsafe_allow_html=True)

# ページ最上部に戻るボタン
st.markdown("""
<a href="#top" class="top-button">↑ Top</a>
""", unsafe_allow_html=True)

