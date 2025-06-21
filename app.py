import os
import dropbox
import streamlit as st
from dotenv import load_dotenv
import locale
from datetime import datetime
import socket

# 言語ロケール設定
locale.setlocale(locale.LC_ALL, '')
load_dotenv()

APP_KEY = os.getenv("DROPBOX_APP_KEY")
APP_SECRET = os.getenv("DROPBOX_APP_SECRET")
REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN")

ZIP_SRC_FOLDER = "/ZIP元フォルダ"
ZIP_DEST_FOLDER = "/ZIP出力先"
LOG_PATH = "/log/export_log.csv"

dbx = dropbox.Dropbox(
    app_key=APP_KEY,
    app_secret=APP_SECRET,
    oauth2_refresh_token=REFRESH_TOKEN
)

THUMBNAIL_FOLDER = "/サムネイル"
st.set_page_config(page_title="コミック一覧", layout="wide")
st.markdown('<a id="top"></a>', unsafe_allow_html=True)

if "selected_files" not in st.session_state:
    st.session_state.selected_files = set()
if "page" not in st.session_state:
    st.session_state.page = 1

def list_all_thumbnail_files():
    thumbnails = []
    try:
        result = dbx.files_list_folder(THUMBNAIL_FOLDER, recursive=False)
        entries = result.entries
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            entries.extend(result.entries)
        for entry in entries:
            if isinstance(entry, dropbox.files.FileMetadata):
                name = entry.name
                if name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')) and entry.size > 0:
                    thumbnails.append(name)
        thumbnails = sorted(thumbnails, key=lambda x: locale.strxfrm(x))
    except Exception as e:
        st.error(f"サムネイル取得エラー: {str(e)}")
    return thumbnails

def get_temporary_image_url(path):
    try:
        return dbx.files_get_temporary_link(path).link
    except:
        return None

PER_PAGE = 200
all_thumbs = list_all_thumbnail_files()
max_pages = (len(all_thumbs) + PER_PAGE - 1) // PER_PAGE
page = st.session_state.page

col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
with col1:
    if st.button("⬅ 前へ") and page > 1:
        st.session_state.page -= 1
with col2:
    st.markdown(f"**{page} / {max_pages}**")
with col3:
    if st.button("次へ ➔") and page < max_pages:
        st.session_state.page += 1
with col4:
    selection = st.selectbox("ページ番号", list(range(1, max_pages + 1)), index=page - 1)
    st.session_state.page = selection

start = (page - 1) * PER_PAGE
end = start + PER_PAGE
visible_thumbs = all_thumbs[start:end]

st.markdown("""
<a href="#top" class="top-button">↑ Top</a>
<style>
.top-button {
  position: fixed;
  bottom: 24px;
  left: 24px;
  background: #007bff;
  color: white !important;
  padding: 14px 20px;
  font-size: 20px;
  border-radius: 50px;
  text-decoration: none;
  z-index: 9999;
  box-shadow: 0 2px 6px rgba(0,0,0,0.2);
}
</style>
""", unsafe_allow_html=True)

st.markdown("### 📚 コミック一覧")
st.markdown(f"<p>✅選択中: {len(st.session_state.selected_files)}</p>", unsafe_allow_html=True)

# ボタンを上に移動
export_disabled = not st.session_state.selected_files
if st.button("📤 選択中のZIPをエクスポート", disabled=export_disabled):
    success_count = 0
    fail_count = 0
    log_lines = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    device = socket.gethostname()

    try:
        result = dbx.files_list_folder(ZIP_DEST_FOLDER)
        for entry in result.entries:
            if isinstance(entry, dropbox.files.FileMetadata) and entry.name.lower().endswith(".zip"):
                dbx.files_delete_v2(entry.path_lower)
    except dropbox.exceptions.ApiError as e:
        st.warning(f"⚠️ 既存ファイルの削除に失敗: {e}")

    for zip_name in st.session_state.selected_files:
        src_path = f"{ZIP_SRC_FOLDER}/{zip_name}"
        dest_path = f"{ZIP_DEST_FOLDER}/{zip_name}"
        try:
            dbx.files_copy_v2(src_path, dest_path, allow_shared_folder=True, autorename=True)
            log_lines.append(f"{timestamp},{device},{zip_name}")
            success_count += 1
        except dropbox.exceptions.ApiError as e:
            st.error(f"❌ {zip_name} のコピーに失敗: {e}")
            fail_count += 1

    try:
        existing_log = ""
        try:
            _, res = dbx.files_download(LOG_PATH)
            existing_log = res.content.decode("utf-8")
        except dropbox.exceptions.ApiError:
            existing_log = "timestamp,device,file\n"

        new_log = existing_log + "\n".join(log_lines) + "\n"
        dbx.files_upload(
            new_log.encode("utf-8"),
            LOG_PATH,
            mode=dropbox.files.WriteMode.overwrite
        )
    except Exception as e:
        st.error(f"⚠️ ログファイルの更新に失敗しました: {e}")

    st.success(f"✅ エクスポート完了: {success_count} 件成功、{fail_count} 件失敗")

st.markdown("""
<style>
.card-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 20px;
}
.card {
    background: white;
    padding: 12px;
    border-radius: 12px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
.card img {
    height: 200px;
    object-fit: contain;
    margin-bottom: 10px;
}
.card label {
    font-size: 14px;
    display: block;
    margin-bottom: 8px;
    word-wrap: break-word;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="card-container">', unsafe_allow_html=True)
for thumb in visible_thumbs:
    zip_name = os.path.splitext(thumb)[0] + ".zip"
    image_path = f"{THUMBNAIL_FOLDER}/{thumb}"
    image_url = get_temporary_image_url(image_path)
    cb_key = f"cb_{zip_name}_{thumb}"
    is_checked = zip_name in st.session_state.selected_files

    with st.container():
        st.markdown(f"""
        <div class="card">
            <img src="{image_url}" alt="{zip_name}" />
            <label><strong>{zip_name}</strong></label>
        </div>
        """, unsafe_allow_html=True)
        checked = st.checkbox("選択", value=is_checked, key=cb_key)
        if checked:
            st.session_state.selected_files.add(zip_name)
        else:
            st.session_state.selected_files.discard(zip_name)
st.markdown("</div>", unsafe_allow_html=True)

# デバッグ表示
st.markdown("---")
st.write("🧪 デバッグ出力")
st.write("選択されたZIP:", list(st.session_state.selected_files))
