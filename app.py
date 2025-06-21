import os
import re
import dropbox
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
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
TARGET_FOLDER = "/成年コミック"
THUMBNAIL_FOLDER = "/サムネイル"
EXPORT_FOLDER = "/SideBooksExport"
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
ITEMS_PER_PAGE = 20

# サムネイル名加工関数
def clean_filename(filename):
    # 「（成年コミック）」を削除
    return re.sub(r'^（成年コミック）', '', filename)

# サムネイル取得
try:
    visible_thumbs = [
        entry.name for entry in dbx.files_list_folder(THUMBNAIL_FOLDER).entries
        if entry.name.lower().endswith(('.jpg', '.jpeg', '.png'))
    ]
    # アルファベット優先、50音順でソート
    visible_thumbs = sorted(visible_thumbs, key=lambda x: locale.strxfrm(x))
except dropbox.exceptions.ApiError as e:
    visible_thumbs = []
    st.error(f"サムネイルフォルダの読み込みに失敗しました: {str(e)}")

# ページネーション
total_items = len(visible_thumbs)
total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
start_idx = (st.session_state.page - 1) * ITEMS_PER_PAGE
end_idx = min(start_idx + ITEMS_PER_PAGE, total_items)
current_thumbs = visible_thumbs[start_idx:end_idx]

# サムネイル表示
st.markdown(f"### 📚 コミック一覧 <span style='font-size: 14px; color: #666;'>（全 {total_items} 件）</span>", unsafe_allow_html=True)

# ボタンとページ表示
col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 2, 2])
with col1:
    if total_pages > 1 and st.session_state.page > 1:
        if st.button("前へ", key="prev_button"):
            st.session_state.page -= 1
            st.rerun()
with col2:
    if total_pages > 1:
        st.write(f"ページ {st.session_state.page} / {total_pages}")
with col3:
    if total_pages > 1 and st.session_state.page < total_pages:
        if st.button("次へ", key="next_button"):
            st.session_state.page += 1
            st.rerun()
with col4:
    if st.session_state.selected_files:
        if st.button("❌ 選択解除", key="clear_button"):
            st.session_state.selected_files.clear()
            st.rerun()
with col5:
    if st.session_state.selected_files:
        if st.button("📤 選択中のZIPをエクスポート", key="export_button"):
            export_files()

# 選択数カウント
selected_count = len(st.session_state.selected_files)
st.markdown(f"<p>✅選択中: {selected_count}</p>", unsafe_allow_html=True)

# 区切り線
st.markdown("---")

# サムネイル表示レイアウトCSS
card_css = """
<style>
.card-container {
    display: grid;
    grid-template-columns: repeat(2, 1fr); /* 横に2枚 */
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
button[kind="primary"] {
    background-color: #000000 !important;
    color: #FFFFFF !important;
    /* 提案: フォントサイズを18pxに */
    /* font-size: 18px !important; */
    /* 提案: 角の丸みを8pxに */
    /* border-radius: 8px !important; */
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

# エクスポート処理
def export_files():
    try:
        # SideBooksExportフォルダをリセット
        try:
            dbx.files_delete_v2(EXPORT_FOLDER)
        except dropbox.exceptions.ApiError:
            pass  # フォルダが存在しない場合は無視
        dbx.files_create_folder_v2(EXPORT_FOLDER)

        # ログフォルダを作成
        try:
            dbx.files_create_folder_v2(LOG_FOLDER)
        except dropbox.exceptions.ApiError:
            pass  # フォルダが存在する場合は無視

        # 選択されたファイルをコピー
        exported_files = []
        for zip_name in st.session_state.selected_files:
            # 元のファイル名に戻す（「（成年コミック）」を付加）
            original_zip_name = f"（成年コミック）{zip_name}" if not zip_name.startswith("（成年コミック）") else zip_name
            src_path = f"{TARGET_FOLDER}/{original_zip_name}"
            dst_path = f"{EXPORT_FOLDER}/{zip_name}"  # コピー先は加工済み名
            try:
                dbx.files_copy_v2(src_path, dst_path)
                exported_files.append(zip_name)
            except dropbox.exceptions.ApiError as e:
                st.warning(f"ファイル {zip_name} のコピーに失敗しました: {str(e)}")

        # ログ記録
        if exported_files:
            # User-Agentからデバイス情報を取得
            user_agent = st.context.headers.get("User-Agent", "unknown")
            ua = parse(user_agent)
            if ua:
                device_info = f"{ua.device.family}_{ua.browser.family}_{ua.os.family}_{ua.os.version_string}".replace(" ", "_")
                device_info = device_info if device_info != "Other_Unknown_Unknown_" else "unknown"
            else:
                device_info = "unknown"
            # 月ごとのログファイルパス
            log_path = f"{LOG_FOLDER}/export_log_{datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m')}.csv"
            log_entry = {
                "timestamp": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S"),  # JST
                "user": device_info,
                "files": ", ".join(exported_files)
            }
            try:
                # 既存ログを読み込み（存在する場合）
                try:
                    log_file = dbx.files_download(log_path)[1].content
                    log_df = pd.read_csv(log_file)
                except dropbox.exceptions.ApiError:
                    log_df = pd.DataFrame(columns=["timestamp", "user", "files"])
                
                # 新しいログを追加
                log_df = pd.concat([log_df, pd.DataFrame([log_entry])], ignore_index=True)
                
                # CSVとして保存
                log_csv = log_df.to_csv(index=False).encode('utf-8')
                dbx.files_upload(log_csv, log_path, mode=dropbox.files.WriteMode.overwrite)
                
                st.success(f"以下のファイルをエクスポートしました: {', '.join(exported_files)}")
            except dropbox.exceptions.ApiError as e:
                st.error(f"ログの保存に失敗しました: {str(e)}")
            
            # 選択状態をリセット
            st.session_state.selected_files.clear()
            st.rerun()
    except Exception as e:
        st.error(f"エクスポート処理中にエラーが発生しました: {str(e)}")

# サムネイル表示
st.markdown('<div class="card-container">', unsafe_allow_html=True)
for name in current_thumbs:
    # サムネイル名から「（成年コミック）」を削除
    clean_name = clean_filename(name)
    zip_name = clean_filename(os.path.splitext(name)[0]) + ".zip"
    display_zip_name = clean_filename(os.path.splitext(name)[0])
    image_path = f"{THUMBNAIL_FOLDER}/{name}"
    try:
        image_url = dbx.files_get_temporary_link(image_path).link
    except dropbox.exceptions.ApiError as e:
        image_url = ""
        st.warning(f"画像 {name} の取得に失敗しました: {str(e)}")

    with st.container():
        st.markdown(f"""
        <div class="card">
            <img src="{image_url}" alt="{display_zip_name}" />
            <label><strong>{display_zip_name}</strong></label>
        </div>
        """, unsafe_allow_html=True)

        # チェックボックス
        checkbox_key = f"cb_{zip_name}_{start_idx}_{name}"
        checked = st.checkbox(
            "選択",
            key=checkbox_key,
            value=zip_name in st.session_state.selected_files
        )
        if checked:
            st.session_state.selected_files.add(zip_name)
        else:
            st.session_state.selected_files.discard(zip_name)

st.markdown("</div>", unsafe_allow_html=True)

# ページトップリンク
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
    /* 提案: フォントサイズを18pxに */
    /* font-size: 18px !important; */
    /* 提案: 角の丸みを8pxに */
    /* border-radius: 8px !important; */
}
.top-button:hover {
    background: #333333;
    color: white !important;
}
</style>
""", unsafe_allow_html=True)
