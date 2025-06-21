import os
import re
import dropbox
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from uuid import uuid4
try:
    from user_agents import parse
except ImportError:
    def parse(user_agent): return None  # フォールバック
import locale

# 日本語ロケールを設定（50音順ソート用）
try:
    locale.setlocale(locale.LC_ALL, 'ja_JP.UTF-8')
except locale.Error:
    pass  # ロケール設定に失敗しても処理を継続

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
ZIP_SRC_FOLDER = "/成年コミック"
ZIP_DEST_FOLDER = "/SideBooksExport"
THUMBNAIL_FOLDER = "/サムネイル"
LOG_FOLDER = f"{THUMBNAIL_FOLDER}/ログ"

# Streamlitページ設定
st.set_page_config(page_title="コミック一覧", layout="wide")

# アンカー用トークンをページトップに設置
st.markdown('<a id="top"></a>', unsafe_allow_html=True)

# 初期状態
if "selected_files" not in st.session_state:
    st.session_state.selected_files = set()
if "page" not in st.session_state:
    st.session_state.page = 1
ITEMS_PER_PAGE = 100  # サムネイル表示数

# サムネイル名加工関数
def clean_filename(filename):
    return re.sub(r'^（成年コミック）', '', filename)

# サムネイル取得
def list_all_thumbnail_files():
    thumbnails = []
    excluded_files = []
    try:
        result = dbx.files_list_folder(THUMBNAIL_FOLDER, recursive=False)
        entries = result.entries
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            entries.extend(result.entries)
        for entry in entries:
            if isinstance(entry, dropbox.files.FileMetadata):
                name = entry.name
                try:
                    name = name.encode('utf-8').decode('utf-8')
                except UnicodeEncodeError:
                    excluded_files.append((name, "エンコーディングエラー"))
                    continue
                if (name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.JPG', '.JPEG', '.PNG', '.WEBP')) and
                    entry.size > 0):
                    thumbnails.append(name)
                else:
                    excluded_files.append((name, f"拡張子不正({name.split('.')[-1]})またはサイズ0({entry.size})"))
            else:
                excluded_files.append((entry.name, "ファイルでない"))
        # デバッグ用: 必要時コメント解除
        # st.write(f"サムネイルフォルダの全ファイル ({len(entries)} 件):", [entry.name for entry in entries])
        # st.write(f"フィルタ後のサムネイル ({len(thumbnails)} 件):", thumbnails)
        # st.write(f"除外されたファイル ({len(excluded_files)} 件):", excluded_files)
        thumbnails = sorted(thumbnails, key=lambda x: locale.strxfrm(x))
    except dropbox.exceptions.ApiError as e:
        st.error(f"サムネイル取得エラー: {str(e)}")
        return []
    return thumbnails

# 一時リンク取得
def get_temporary_image_url(path):
    try:
        dbx.files_get_metadata(path)  # ファイル存在確認
        return dbx.files_get_temporary_link(path).link
    except dropbox.exceptions.ApiError as e:
        st.warning(f"画像取得失敗: {path} ({str(e)})")
        return None

# ZIPファイル一覧取得
def get_zip_files():
    zip_files = []
    try:
        result = dbx.files_list_folder(ZIP_SRC_FOLDER, recursive=False)
        entries = result.entries
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            entries.extend(result.entries)
        zip_files = [entry.name for entry in entries if isinstance(entry, dropbox.files.FileMetadata)]
    except dropbox.exceptions.ApiError as e:
        st.error(f"ZIP元フォルダのファイル一覧取得に失敗: {str(e)}")
        return []
    return zip_files

# エクスポート処理
def export_files():
    try:
        # SideBooksExportフォルダをリセット
        try:
            dbx.files_delete_v2(ZIP_DEST_FOLDER)
        except dropbox.exceptions.ApiError:
            pass
        dbx.files_create_folder_v2(ZIP_DEST_FOLDER)

        # ログフォルダを作成
        try:
            dbx.files_create_folder_v2(LOG_FOLDER)
        except dropbox.exceptions.ApiError:
            pass

        # 選択されたファイルをコピー
        exported_files = []
        for zip_name in st.session_state.selected_files:
            original_zip_name = f"（成年コミック）{zip_name}" if not zip_name.startswith("（成年コミック）") else zip_name
            src_path = f"{ZIP_SRC_FOLDER}/{original_zip_name}"
            dest_path = f"{ZIP_DEST_FOLDER}/{zip_name}"
            try:
                dbx.files_get_metadata(src_path)
                dbx.files_copy_v2(src_path, dest_path, allow_shared_folder=True, autorename=True)
                exported_files.append(zip_name)
            except dropbox.exceptions.ApiError as e:
                st.error(f"❌ コピー失敗: {zip_name} (エラー: {str(e)})")
                continue

        # ログ記録
        if exported_files:
            user_agent = st.context.headers.get("User-Agent", "unknown")
            ua = parse(user_agent)
            device_info = f"iPhone_Safari_iOS_18.0" if ua else "unknown"
            log_path = f"{LOG_FOLDER}/export_log_{datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m')}.csv"
            log_entry = {
                "timestamp": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S"),
                "user": device_info,
                "files": ", ".join(exported_files)
            }
            try:
                try:
                    log_file = dbx.files_download(log_path)[1].content
                    log_df = pd.read_csv(log_file)
                except dropbox.exceptions.ApiError:
                    log_df = pd.DataFrame(columns=["timestamp", "user", "files"])
                log_df = pd.concat([log_df, pd.DataFrame([log_entry])], ignore_index=True)
                log_csv = log_df.to_csv(index=False).encode('utf-8')
                dbx.files_upload(log_csv, log_path, mode=dropbox.files.WriteMode.overwrite)
                st.success(f"✅ エクスポート完了: {len(exported_files)} 件成功")
            except dropbox.exceptions.ApiError as e:
                st.error(f"⚠️ ログ保存失敗: {str(e)}")
            st.session_state.selected_files.clear()
            st.rerun()
    except Exception as e:
        st.error(f"エクスポート処理中にエラーが発生しました: {str(e)}")

# サムネイルとZIPファイルの取得
all_thumbs = list_all_thumbnail_files()
zip_files_in_source = get_zip_files()

# サムネイルとZIPの一致フィルタ
filtered_thumbs = []
image_base_names = set(os.path.splitext(name)[0] for name in all_thumbs)
zip_base_names = set(os.path.splitext(name)[0] for name in zip_files_in_source)
for thumb in all_thumbs:
    zip_name = os.path.splitext(thumb)[0] + ".zip"
    original_zip_name = f"（成年コミック）{zip_name}" if not zip_name.startswith("（成年コミック）") else zip_name
    if original_zip_name in zip_files_in_source:
        filtered_thumbs.append(thumb)

# ページネーション
total_pages = (len(filtered_thumbs) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
start_idx = (st.session_state.page - 1) * ITEMS_PER_PAGE
end_idx = min(start_idx + ITEMS_PER_PAGE, len(filtered_thumbs))
visible_thumbs = filtered_thumbs[start_idx:end_idx]

# サムネイル表示
st.markdown(f"### 📚 コミック一覧 <span style='font-size: 14px; color: #666;'>（全 {len(filtered_thumbs)} 件）</span>", unsafe_allow_html=True)

# ページネーションUIとボタン
col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 2, 2])
with col1:
    if total_pages > 1 and st.session_state.page > 1:
        if st.button("⬅ 前へ", key="prev_button"):
            st.session_state.page -= 1
            st.rerun()
with col2:
    if total_pages > 1:
        st.markdown(f"**{st.session_state.page} / {total_pages}**")
with col3:
    if total_pages > 1 and st.session_state.page < total_pages:
        if st.button("次へ ➡", key="next_button"):
            st.session_state.page += 1
            st.rerun()
with col4:
    if total_pages > 1:
        selection = st.selectbox("ページ番号", list(range(1, total_pages + 1)), index=st.session_state.page - 1, key="page_select")
        if selection != st.session_state.page:
            st.session_state.page = selection
            st.rerun()
with col5:
    if st.session_state.selected_files:
        if st.button("❌ 選択解除", key="clear_button"):
            st.session_state.selected_files.clear()
            st.rerun()
        if st.button("📤 選択中のZIPをエクスポート", key="export_button"):
            export_files()

# 選択数
st.markdown(f"<p>✅選択中: {len(st.session_state.selected_files)}</p>", unsafe_allow_html=True)

# 不一致ファイル表示
unmatched_images = [name for name in image_base_names if name not in zip_base_names]
unmatched_zips = [name for name in zip_base_names if name not in image_base_names]
if unmatched_images:
    st.markdown("### ❌ 画像はあるけどZIPがないファイル:")
    for name in unmatched_images:
        st.write("- ", name + ".jpg")
if unmatched_zips:
    st.markdown("### ❌ ZIPはあるけど画像がないファイル:")
    for name in unmatched_zips:
        st.write("- ", name + ".zip")

# サムネイル表示レイアウトCSS
card_css = """
<style>
.card-container {
    display: grid;
    grid-template-columns: repeat(2, 1fr); /* 横2列 */
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
.stCheckbox {
    z-index: 10;
    position: relative;
    margin-top: 8px;
}
button[kind="primary"] {
    background-color: #000000 !important;
    color: #FFFFFF !important;
}
button[kind="primary"]:hover {
    background-color: #333333 !important;
    color: #FFFFFF !important;
}
@media (max-width: 320px) {
    .card-container {
        grid-template-columns: 1fr; /* 極小画面では1列 */
    }
}
</style>
"""
st.markdown(card_css, unsafe_allow_html=True)

# サムネイル表示
st.markdown('<div class="card-container">', unsafe_allow_html=True)
for thumb in visible_thumbs:
    clean_name = clean_filename(thumb)
    zip_name = clean_filename(os.path.splitext(thumb)[0]) + ".zip"
    display_zip_name = clean_filename(os.path.splitext(thumb)[0])
    image_path = f"{THUMBNAIL_FOLDER}/{thumb}"
    image_url = get_temporary_image_url(image_path)
    
    with st.container():
        st.markdown(f"""
        <div class="card">
            <img src="{image_url or 'https://via.placeholder.com/200x200?text=Image+Not+Found'}" alt="{display_zip_name}" />
            <label><strong>{display_zip_name}</strong></label>
        </div>
        """, unsafe_allow_html=True)
        checkbox_key = f"cb_{zip_name}_{st.session_state.page}_{thumb}_{uuid4()}"
        checked = st.checkbox("選択", key=checkbox_key, value=zip_name in st.session_state.selected_files)
        if checked:
            st.session_state.selected_files.add(zip_name)
        else:
            st.session_state.selected_files.discard(zip_name)

st.markdown("</div>", unsafe_allow_html=True)

# ページトップボタン
st.markdown("""
<a href="#top" class="top-button">↑ Top</a>
<style>
.top-button {
    position: fixed;
    bottom: 24px;
    left: 24px;
    background: #000000;
    color: white !important;
    padding: 14px 20px;
    font-size: 20px;
    border-radius: 50px;
    text-decoration: none;
    z-index: 9999;
    box-shadow: 0 2px 6px rgba(0,0,0,0.2);
}
.top-button:hover {
    background: #333333;
    color: white !important;
}
</style>
""", unsafe_allow_html=True)

# デバッグ出力
st.markdown("---")
st.write("🧪 デバッグ出力")
st.write("選択されたZIP:", list(st.session_state.selected_files))
