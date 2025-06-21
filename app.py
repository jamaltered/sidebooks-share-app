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
st.markdown('<a id="top"></a>', unsafe_allow_html=True)

# 初期状態
if "selected_files" not in st.session_state:
    st.session_state.selected_files = set()
if "page" not in st.session_state:
    st.session_state.page = 1

# サムネイル取得
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
    page_selection = st.selectbox("ページ番号", list(range(1, max_pages + 1)), index=st.session_state.page - 1)
    st.session_state.page = page_selection

page = st.session_state.page
start_idx = (page - 1) * PER_PAGE
end_idx = start_idx + PER_PAGE
visible_thumbs = sorted(thumbnails)[start_idx:end_idx]

# コミック一覧
st.markdown("### 📚 コミック一覧")
selected_count = len(st.session_state.selected_files)
st.markdown(f"<p>✅選択中: {selected_count}</p>", unsafe_allow_html=True)

# CSS
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

# サムネイル表示
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

        if f"cb_{zip_name}" not in st.session_state:
            st.session_state[f"cb_{zip_name}"] = zip_name in st.session_state.selected_files

        checked = st.checkbox("選択", key=f"cb_{zip_name}", value=st.session_state[f"cb_{zip_name}"])
        if checked:
            st.session_state.selected_files.add(zip_name)
            st.session_state[f"cb_{zip_name}"] = True
        else:
            st.session_state.selected_files.discard(zip_name)
            st.session_state[f"cb_{zip_name}"] = False
st.markdown("</div>", unsafe_allow_html=True)

# 「全選択解除」ボタン
if st.session_state.selected_files:
    if st.button("❌ 選択解除"):
        for zip_name in list(st.session_state.selected_files):
            st.session_state[f"cb_{zip_name}"] = False
        st.session_state.selected_files.clear()
        st.experimental_rerun()

# エクスポートボタン
if st.session_state.selected_files:
    st.markdown("---")
    if st.button("📤 選択中のZIPをエクスポート"):
        st.success("エクスポート処理をここに実装")

# TOPボタン（文字色白）
st.markdown("""
<a href="#top" class="top-button">↑ Top</a>
<style>
.top-button {
  position: fixed;
  bottom: 24px;
  left: 24px;
  background: #007bff;
  color: #ffffff !important;
  padding: 14px 20px;
  font-size: 20px;
  border-radius: 50px;
  text-decoration: none;
  z-index: 9999;
  box-shadow: 0 2px 6px rgba(0,0,0,0.2);
}
</style>
""", unsafe_allow_html=True)
