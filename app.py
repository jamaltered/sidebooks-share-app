import os
import dropbox
import streamlit as st
from dotenv import load_dotenv
import locale

locale.setlocale(locale.LC_ALL, '')

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

# アンカー
st.markdown('<a id="top"></a>', unsafe_allow_html=True)

# 初期化
if "selected_files" not in st.session_state:
    st.session_state.selected_files = set()
if "page" not in st.session_state:
    st.session_state.page = 1

# ✅ Dropboxサムネイル一覧の取得（すべて）
def list_all_thumbnail_files():
    thumbnails = []
    try:
        result = dbx.files_list_folder(THUMBNAIL_FOLDER, recursive=False)
        entries = result.entries
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            entries.extend(result.entries)
        thumbnails = [
            entry.name for entry in entries
            if isinstance(entry, dropbox.files.FileMetadata)
            and entry.name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
        ]
        thumbnails = sorted(thumbnails, key=lambda x: locale.strxfrm(x))
    except dropbox.exceptions.ApiError as e:
        st.error(f"サムネイルの取得に失敗しました: {str(e)}")
    return thumbnails

def get_temporary_image_url(path):
    try:
        return dbx.files_get_temporary_link(path).link
    except:
        return None

# 🔄 サムネイル一覧取得
all_thumbnails = list_all_thumbnail_files()
PER_PAGE = 200
max_pages = (len(all_thumbnails) + PER_PAGE - 1) // PER_PAGE
page = st.session_state.page

# ページネーションUI
col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
with col1:
    if st.button("⬅ 前へ") and page > 1:
        st.session_state.page -= 1
with col2:
    st.markdown(f"**{page} / {max_pages}**")
with col3:
    if st.button("次へ ➡") and page < max_pages:
        st.session_state.page += 1
with col4:
    page_selection = st.selectbox("ページ番号", list(range(1, max_pages + 1)), index=page - 1)
    st.session_state.page = page_selection

start_idx = (page - 1) * PER_PAGE
end_idx = start_idx + PER_PAGE
visible_thumbs = all_thumbnails[start_idx:end_idx]

# TOPボタン（白文字）
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

# サムネイル表示UI
st.markdown("### 📚 コミック一覧")
st.markdown(f"<p>✅選択中: {len(st.session_state.selected_files)}</p>", unsafe_allow_html=True)

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

# 表示ループ
st.markdown('<div class="card-container">', unsafe_allow_html=True)
for name in visible_thumbs:
    zip_name = os.path.splitext(name)[0] + ".zip"
    image_path = f"{THUMBNAIL_FOLDER}/{name}"
    image_url = get_temporary_image_url(image_path)
    checkbox_key = f"cb_{zip_name}"
    is_checked = zip_name in st.session_state.selected_files

    with st.container():
        st.markdown(f"""
        <div class="card">
            <img src="{image_url}" alt="{zip_name}" />
            <label><strong>{zip_name}</strong></label>
        </div>
        """, unsafe_allow_html=True)
        checked = st.checkbox("選択", value=is_checked, key=checkbox_key)
        if checked:
            st.session_state.selected_files.add(zip_name)
        else:
            st.session_state.selected_files.discard(zip_name)
st.markdown("</div>", unsafe_allow_html=True)

# エクスポートボタン
if st.session_state.selected_files:
    st.markdown("---")
    if st.button("📤 選択中のZIPをエクスポート"):
        st.success("エクスポート処理をここに実装")
