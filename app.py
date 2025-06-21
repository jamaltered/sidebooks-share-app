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

# アンカー用トークンをページトップに設置
st.markdown('<a id="top"></a>', unsafe_allow_html=True)

# 初期状態
if "selected_files" not in st.session_state:
    st.session_state.selected_files = set()
if "page" not in st.session_state:
    st.session_state.page = 1
selected_count = len(st.session_state.selected_files)

# サムネイル表示
st.markdown("### 📚 コミック一覧")

# 選択数カウント（この時点でsession_state.selected_filesは正確に更新済み）
selected_count = len(st.session_state.selected_files)
st.markdown(f"<p>✅選択中: {selected_count}</p>", unsafe_allow_html=True)

# サムネイル表示レイアウトCSS
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

        # 初期化：チェック状態保持
        if f"cb_{zip_name}" not in st.session_state:
            st.session_state[f"cb_{zip_name}"] = zip_name in st.session_state.selected_files

        # チェックボックス
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

# ページトップリンク（左下）スタイル修正：文字を白に
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
