import os
import re
import dropbox
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime

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

# ユーザーエージェント（例外処理付き）
try:
    user_agent = st.request.headers.get("user-agent", "unknown")
except Exception:
    user_agent = "unknown"

# ページ設定
st.set_page_config(page_title="コミック一覧", layout="wide")
st.markdown('<a id="top"></a>', unsafe_allow_html=True)

# セッション状態
if "selected_files" not in st.session_state:
    st.session_state.selected_files = set()
if "page" not in st.session_state:
    st.session_state.page = 1

# ZIPとサムネイル一覧取得
def list_zip_files():
    zip_files = []
    result = dbx.files_list_folder(TARGET_FOLDER, recursive=True)
    zip_files.extend([e for e in result.entries if e.name.endswith(".zip")])
    while result.has_more:
        result = dbx.files_list_folder_continue(result.cursor)
        zip_files.extend([e for e in result.entries if e.name.endswith(".zip")])
    return zip_files

def list_thumbnails():
    thumbs = []
    result = dbx.files_list_folder(THUMBNAIL_FOLDER)
    thumbs.extend([e.name for e in result.entries if e.name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
    while result.has_more:
        result = dbx.files_list_folder_continue(result.cursor)
        thumbs.extend([e.name for e in result.entries if e.name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
    return thumbs

def get_temporary_image_url(path):
    try:
        res = dbx.files_get_temporary_link(path)
        return res.link
    except:
        return None

def save_export_log(entries):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = ["time,filename,user_agent\n"]
    for f in entries:
        lines.append(f'"{now}","{f}","{user_agent}"\n')
    content = "".join(lines).encode("utf-8")
    dbx.files_upload(content, LOG_PATH, mode=dropbox.files.WriteMode.overwrite)

# 表示対象
zip_files = list_zip_files()
zip_set = {e.name for e in zip_files}
thumbnails = list_thumbnails()

PER_PAGE = 200
max_pages = (len(thumbnails) + PER_PAGE - 1) // PER_PAGE
page = st.session_state.page
start, end = (page - 1) * PER_PAGE, page * PER_PAGE
visible_thumbs = sorted(thumbnails)[start:end]

# ページネーションUI
col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
with col1:
    if st.button("⬅ 前へ") and st.session_state.page > 1:
        st.session_state.page -= 1
with col2:
    st.markdown(f"**{st.session_state.page} / {max_pages}**")
with col3:
    if st.button("次へ ➡") and st.session_state.page < max_pages:
        st.session_state.page += 1
with col4:
    p = st.selectbox("ページ番号", list(range(1, max_pages + 1)), index=page - 1)
    st.session_state.page = p

# トップボタン
st.markdown("""
<a href="#top" class="top-button">↑ Top</a>
<style>
.top-button {
  position: fixed;
  bottom: 24px;
  left: 24px;
  background: #007bff;
  color: white;
  padding: 14px 20px;
  font-size: 20px;
  border-radius: 50px;
  text-decoration: none;
  z-index: 9999;
  box-shadow: 0 2px 6px rgba(0,0,0,0.2);
}
</style>
""", unsafe_allow_html=True)

# 表示・チェック
st.markdown("### 📚 コミック一覧")
st.markdown(f"<p>✅選択中: {len(st.session_state.selected_files)}</p>", unsafe_allow_html=True)

card_css = """
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
"""
st.markdown(card_css, unsafe_allow_html=True)
st.markdown('<div class="card-container">', unsafe_allow_html=True)

for name in visible_thumbs:
    zip_name = os.path.splitext(name)[0] + ".zip"
    image_path = f"{THUMBNAIL_FOLDER}/{name}"
    image_url = get_temporary_image_url(image_path)
    with st.container():
        st.markdown(f"""
        <div class="card">
            <img src="{image_url}" alt="{zip_name}" />
            <label><strong>{zip_name}</strong></label>
        </div>
        """, unsafe_allow_html=True)
        checked = st.checkbox("選択", value=zip_name in st.session_state.selected_files, key=zip_name)
        if checked:
            st.session_state.selected_files.add(zip_name)
        else:
            st.session_state.selected_files.discard(zip_name)

st.markdown("</div>", unsafe_allow_html=True)

# エクスポート処理
if st.session_state.selected_files:
    st.markdown("---")
    if st.button("📤 選択中のZIPをエクスポート"):
        failed = []
        for name in st.session_state.selected_files:
            try:
                src_path = f"{TARGET_FOLDER}/{name}"
                dest_path = f"{EXPORT_FOLDER}/{name}"
                dbx.files_copy_v2(src_path, dest_path, allow_shared_folder=True, autorename=True)
            except dropbox.exceptions.ApiError as e:
                st.error(f"❌ {name} のコピーに失敗: {e}")
                failed.append(name)
        save_export_log(st.session_state.selected_files)
        st.success("✅ エクスポートが完了しました。")
