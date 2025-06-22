import streamlit as st
import dropbox
import hashlib
import difflib
import requests
import pandas as pd
import os
import logging
import re
import csv
from datetime import datetime
import uuid

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Secretsから設定取得 ---
APP_KEY = st.secrets["DROPBOX_APP_KEY"]
APP_SECRET = st.secrets["DROPBOX_APP_SECRET"]
REFRESH_TOKEN = st.secrets["DROPBOX_REFRESH_TOKEN"]
TARGET_FOLDER = st.secrets["TARGET_FOLDER"]
EXPORT_FOLDER = st.secrets["EXPORT_FOLDER"]
THUMBNAIL_FOLDER = st.secrets["THUMBNAIL_FOLDER"]
ZIP_LIST_URL = st.secrets["ZIP_LIST_URL"]

# Dropbox接続
dbx = dropbox.Dropbox(
    app_key=APP_KEY,
    app_secret=APP_SECRET,
    oauth2_refresh_token=REFRESH_TOKEN
)

# ファイル一覧読み込み（zip_file_list.txt）
@st.cache_data
def load_zip_file_list():
    try:
        response = requests.get(ZIP_LIST_URL)
        response.raise_for_status()
        lines = response.text.splitlines()
        return [line.strip() for line in lines if line.strip()]
    except Exception as e:
        st.error(f"zip_file_list.txt の取得に失敗しました: {e}")
        return []

zip_paths = load_zip_file_list()

# 形式統一: ファイル名を [作者] 作品名 に変換（generate_thumbnails.pyと一致）
def normalize_filename(zip_name):
    match = re.match(r"^\(.*?\)\s*\[(.+?)\]\s*(.+?)\.zip$", zip_name)
    if match:
        author, title = match.groups()
        return f"[{author}] {title}".strip()
    else:
        return os.path.splitext(zip_name)[0]

# サムネイルパスを生成（キャッシュ強化）
@st.cache_data
def get_thumbnail_path(name):
    thumb_name = normalize_filename(os.path.basename(name))
    thumb_path = f"{THUMBNAIL_FOLDER}/{thumb_name}.jpg"
    try:
        link = dbx.files_get_temporary_link(thumb_path).link
        return link
    except dropbox.exceptions.ApiError as e:
        logger.error(f"サムネイル取得失敗: {thumb_path}, エラー: {e}")
        return None
    except Exception as e:
        logger.error(f"サムネイル取得で予期しないエラー: {thumb_path}, エラー: {e}")
        return None

# セーフキー（チェックボックスのキー用）
def make_safe_key(name):
    return hashlib.md5(name.encode()).hexdigest()

# ファイル名の整形表示
def format_display_name(path):
    name = os.path.basename(path)
    if "] " in name:
        try:
            author = name.split("]")[0].split("[")[-1]
            title = "] ".join(name.split("] ")[1:])
            return f"[{author}] {title}"
        except:
            return name
    return name

# 並び順ソート
def sort_zip_paths(paths, sort_type="名前順"):
    def get_author(name):
        if "] " in name:
            try:
                return name.split("]")[0].split("[")[-1]
            except:
                return ""
        return ""

    if sort_type == "名前順":
        return sorted(paths, key=lambda x: os.path.basename(x).lower())
    elif sort_type == "作家順":
        return sorted(paths, key=lambda x: get_author(os.path.basename(x)).lower())
    else:  # "元の順序"
        return paths  # ソートなしで元の順序を維持

# 近似検索で元ファイルパスを特定
def find_similar_path(filename, zip_paths):
    candidates = difflib.get_close_matches(filename, zip_paths, n=1, cutoff=0.7)
    return candidates[0] if candidates else None

# 出力ログをCSVに保存
def save_export_log(file_list):
    log_path = "/log/output_log.csv"
    device = st.session_state.get("user_agent", "Unknown Device")
    session_id = st.session_state.get("session_id", str(uuid.uuid4()))
    try:
        # 既存ファイルのチェック
        try:
            dbx.files_get_metadata(log_path)
            mode = dropbox.files.WriteMode("append", None)
            header_written = True
        except dropbox.exceptions.ApiError:
            mode = dropbox.files.WriteMode("overwrite")
            header_written = False

        # CSVデータ準備
        rows = []
        for name in file_list:
            rows.append([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S JST"),
                name,
                f"{device} (Session: {session_id})"
            ])
        
        # ヘッダー書き込み（初回のみ）
        if not header_written:
            rows.insert(0, ["DateTime", "FileName", "Device"])

        # 一時ファイルに書き込み
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", newline="", encoding="utf-8-sig", delete=False) as temp_file:
            writer = csv.writer(temp_file)
            writer.writerows(rows)

        # 一時ファイルをDropboxにアップロード
        with open(temp_file.name, "rb") as f:
            dbx.files_upload(f.read(), log_path, mode=mode)
        
        os.unlink(temp_file.name)  # 一時ファイル削除
    except Exception as e:
        st.error(f"出力ログ保存失敗: {e}")
        logger.error(f"出力ログ保存失敗: {log_path}, エラー: {e}")

# ユーザーエージェントを取得（デバイス情報）
def set_user_agent():
    if "user_agent" not in st.session_state:
        try:
            user_agent = requests.get("https://httpbin.org/user-agent").json()["user-agent"]
            st.session_state["user_agent"] = user_agent
        except Exception:
            st.session_state["user_agent"] = "Unknown Device"
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())

# カスタムCSSでレイアウトとチェックボックスを調整
st.markdown(
    """
    <style>
    /* ビューポート設定 */
    @viewport {
        width: device-width;
        initial-scale: 1.0;
    }
    /* 各アイテムのスタイル */
    .item-container {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 5px;
    }
    .item-container img {
        max-width: 140px;
        width: 100%;
        height: auto;
    }
    /* チェックボックスを大きく */
    .stCheckbox > div > label > input[type="checkbox"] {
        transform: scale(1.5) !important;
        margin-right: 5px;
    }
    /* チェックボックスラベル */
    .stCheckbox > div > label {
        font-size: 1.2em !important;
        transition: color 0.3s;
    }
    /* チェック時文字色を赤に */
    .stCheckbox > div > label[data-baseweb="checkbox"] input:checked + span + span {
        color: red !important;
    }
    /* サムネイルなしのテキスト */
    .no-thumbnail {
        font-size: 1.2em !important;
    }
    /* スマホ（iPhone 15想定） */
    @media (max-width: 768px) {
        .item-container img {
            max-width: 120px;
        }
        .stCheckbox > div > label > input[type="checkbox"] {
            transform: scale(1.3) !important;
        }
        .stCheckbox > div > label {
            font-size: 1.1em !important;
        }
        .no-thumbnail {
            font-size: 1.1em !important;
        }
    }
    /* ページ情報のスタイル */
    .page-info {
        font-size: 1.2em;
        font-weight: bold;
        margin-bottom: 10px;
    }
    </style>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    """,
    unsafe_allow_html=True
)

# メイン表示処理
def show_zip_file_list(sorted_paths):
    page_size = 100  # 1ページ100アイテム
    total_pages = max(1, (len(sorted_paths) - 1) // page_size + 1)
    page = st.number_input("ページ番号", min_value=1, max_value=total_pages, step=1, key="page_input")
    
    # ページ情報「◯/◯」を表示
    st.write(f'<p class="page-info">ページ {page}/{total_pages}</p>', unsafe_allow_html=True)

    start = (page - 1) * page_size
    end = start + page_size
    page_files = sorted_paths[start:end]

    # TOPボタンを左下に配置
    st.markdown(
        '<div style="position: fixed; bottom: 20px; left: 20px; z-index: 100;">'
        '<a href="#top" style="background-color:#444; color:white; padding:10px; text-decoration:none; border-radius:5px;">↑TOP</a>'
        '</div>',
        unsafe_allow_html=True
    )

    # 2列レイアウト
    for i in range(0, len(page_files), 2):
        cols = st.columns([1, 1])  # 2列
        for j in range(2):
            if i + j < len(page_files):
                path = page_files[i + j]
                name = os.path.basename(path)
                display_name = format_display_name(name)
                key = make_safe_key(name)

                with cols[j]:
                    # アイテムコンテナ
                    st.markdown('<div class="item-container">', unsafe_allow_html=True)
                    thumb = get_thumbnail_path(name)
                    if thumb:
                        st.markdown(
                            f'<img src="{thumb}" alt="{display_name}">',
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f'<p class="no-thumbnail">🖼️ サムネイルなし</p>',
                            unsafe_allow_html=True
                        )

                    # チェックボックスの状態を即時管理
                    if f"cb_{key}" not in st.session_state:
                        st.session_state[f"cb_{key}"] = name in st.session_state.get("selected_files", [])
                    checked = st.checkbox(
                        display_name,
                        key=f"cb_{key}",
                        value=st.session_state[f"cb_{key}"],
                        label_visibility="visible",
                        on_change=lambda x, n=name, k=key: update_selected_files(n, k)
                    )
                    st.markdown('</div>', unsafe_allow_html=True)

def update_selected_files(name, key):
    if st.session_state[f"cb_{key}"]:
        if name not in st.session_state.get("selected_files", []):
            if "selected_files" not in st.session_state:
                st.session_state["selected_files"] = []
            st.session_state.selected_files.append(name)
    else:
        if name in st.session_state.get("selected_files", []):
            st.session_state.selected_files.remove(name)

# ---------------------- アプリ開始 ------------------------

st.set_page_config(layout="wide")
st.markdown('<div id="top"></div>', unsafe_allow_html=True)
st.title("📚 SideBooks ZIP共有アプリ")

# 初期化
if "selected_files" not in st.session_state:
    st.session_state.selected_files = []

set_user_agent()  # デバイス情報を設定

# 並び順セレクト（「元の順序」追加）
sort_option = st.selectbox("表示順", ["名前順", "作家順", "元の順序"])
sorted_zip_paths = sort_zip_paths(zip_paths, sort_option)

# エクスポートボタン（先頭に固定）
if st.session_state.selected_files:
    st.markdown("### 選択中:")
    st.write(st.session_state.selected_files)

    if st.button("📤 選択中のZIPをエクスポート（SideBooks用）"):
        try:
            # SideBooksExportフォルダを空にする
            for entry in dbx.files_list_folder(EXPORT_FOLDER).entries:
                dbx.files_delete_v2(f"{EXPORT_FOLDER}/{entry.name}")
        except Exception:
            pass  # フォルダが無い場合など

        failed = []
        for name in st.session_state.selected_files:
            src_path = f"{TARGET_FOLDER}/{name}"
            dest_path = f"{EXPORT_FOLDER}/{name}"
            try:
                dbx.files_copy_v2(src_path, dest_path, allow_shared_folder=True, autorename=True)
            except dropbox.exceptions.ApiError:
                match = find_similar_path(f"{TARGET_FOLDER}/{name}", zip_paths)
                if match:
                    try:
                        dbx.files_copy_v2(match, dest_path, allow_shared_folder=True, autorename=True)
                    except Exception as e:
                        st.error(f"❌ {name} の代替コピーにも失敗: {e}")
                        failed.append(name)
                else:
                    st.error(f"❌ {name} のコピーに失敗（候補なし）")
                    failed.append(name)
        
        # 出力ログを保存
        save_export_log(st.session_state.selected_files)
        
        if failed:
            st.warning(f"{len(failed)} 件のファイルがコピーできませんでした。")
        else:
            st.success("✅ エクスポートが完了しました！")

# ZIP一覧表示
show_zip_file_list(sorted_zip_paths)
