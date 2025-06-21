import os
import dropbox
import streamlit as st
from dotenv import load_dotenv
import locale

# 言語ロケール設定
locale.setlocale(locale.LC_ALL, '')
load_dotenv()

APP_KEY = os.getenv("DROPBOX_APP_KEY")
APP_SECRET = os.getenv("DROPBOX_APP_SECRET")
REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN")

dbx = dropbox.Dropbox(
    app_key=APP_KEY,
    app_secret=APP_SECRET,
    oauth2_refresh_token=REFRESH_TOKEN
)

# フォルダパス
THUMBNAIL_FOLDER = "/サムネイル"
st.set_page_config(page_title="コミック一覧", layout="wide")
st.markdown('<a id="top"></a>', unsafe_allow_html=True)

# セッション状態初期化
if "selected_files" not in st.session_state:
    st.session_state.selected_files = set()
if "page" not in st.session_state:
    st.session_state.page = 1

# サムネイル取得（media_infoではなく拡張子＋サイズで判定）
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

# 一時的な画像URL取得
def get_temporary_image_url(path):
    try:
        return dbx.files_get_temporary_link(path).link
    except:
        return None

# 1ページに表示する件数
PER_PAGE = 200
all_thumbs = list_all_thumbnail_files()
max_pages = (len(all_thumbs) + PER_PAGE - 1) // PER_PAGE
page = st.session_state.page

# ページ切り替えUI
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
    selection = st.selectbox("ページ番号", list(range(1, max_pages + 1)), index=page - 1)
    st.session_state.page = selection

start = (page - 1) * PER_PAGE
end = start + PER_PAGE
visible_thumbs = all_thumbs[start:end]

# TOPに戻るボタン
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

# 選択数表示
st.markdown("### 📚 コミック一覧")
st.markdown(f"<p>✅選択中: {len(st.session_state.selected_files)}</p>", unsafe_allow_html=True)

# CSSでカード表示形式を整える
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

# カード表示（画像＋ZIP名＋チェックボックス）
st.markdown('<div class="card-container">', unsafe_allow_html=True)
for thumb in visible_thumbs:
    zip_name = os.path.splitext(thumb)[0] + ".zip"
    image_path = f"{THUMBNAIL_FOLDER}/{thumb}"
    image_url = get_temporary_image_url(image_path)
    cb_key = f"cb_{zip_name}"
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

# エクスポート処理UI
if st.session_state.selected_files:
    st.markdown("---")
    if st.button("📤 選択中のZIPをエクスポート"):
        st.success("✅ エクスポート処理がここに実装されます（仮）")
