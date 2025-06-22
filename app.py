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
import io
import pytz

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
    log_path = "/log/output_log.csv"  # 固定ファイル名
    device = st.session_state.get("user_agent", "Unknown Device")
    session_id = st.session_state.get("session_id", str(uuid.uuid4()))
    try:
        # 既存ファイルのチェック
        existing_content = []
        try:
            metadata, content = dbx.files_download(log_path)
            existing_content = content.content.decode("utf-8-sig").splitlines()
            if existing_content and not existing_content[0].startswith("DateTime"):
                existing_content.insert(0, "DateTime,FileName,Device")
        except dropbox.exceptions.ApiError:
            pass  # ファイルがない場合は新規作成

        # 新しいデータ準備
        rows = []
        for name in file_list:
            rows.append([
                datetime.now(pytz.timezone('Asia/Tokyo')).strftime("%Y-%m-%d %H:%M:%S JST"),
                name,
                f"{device} (Session: {session_id})"
            ])

        # ヘッダー追加（初回のみ）
        if not existing_content:
            rows.insert(0, ["DateTime", "FileName", "Device"])

        # 既存内容と新しい内容を結合
        all_rows = existing_content + [",".join(row) for row in rows]

        # 一時ファイルに書き込み
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", newline="", encoding="utf-8-sig", delete=False) as temp_file:
            writer = csv.writer(temp_file)
            for row in all_rows:
                writer.writerow(row.split(","))

        # 一時ファイルをDropboxにアップロード
        with open(temp_file.name, "rb") as f:
            dbx.files_upload(f.read(), log_path, mode=dropbox.files.WriteMode("overwrite"))
        
        os.unlink(temp_file.name)  # 一時ファイル削除
    except Exception as e:
        st.error(f"出力ログ保存失敗: {str(e)}")
        logger.error(f"出力ログ保存失敗: {log_path}, エラー: {str(e)}", exc_info=True)

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
        transform: scale(1.5);
        margin-right: 5px;
    }
    /* チェックボックスラベル */
    .stCheckbox > div > label {
        font-size: 1.2em;
        transition: color 0.3s;
    }
    /* チェック時文字色を赤に */
    .stCheckbox > div > label[data-baseweb="checkbox"] input:checked + span + span {
        color: red;
    }
    /* サムネイルなしのテキスト */
    .no-thumbnail {
        font-size: 1.2em;
    }
    /* スマホ（iPhone 15想定） */
    @media (max-width: 768px) {
        .item-container img {
            max-width: 120px;
        }
        .stCheckbox > div > label > input[type="checkbox"] {
            transform: scale(1.3);
        }
        .stCheckbox > div > label {
            font-size: 1.1em;
        }
        .no-thumbnail {
            font-size: 1.1em;
        }
    }
    /* ページ情報のスタイル */
    .page-info {
        font-size: 1.2em;
        font-weight: bold;
        margin-bottom: 10px;
    }
    /* 右側パネルのスタイル */
    .fixed-panel {
        position: fixed;
        right: 20px;
        top: 50%;
        transform: translateY(-50%);
        background-color: #f0f0f0;
        padding: 10px;
        border-radius: 5px;
        z-index: 100;
        box-shadow: 0 0 10px rgba(0,0,0,0.1);
    }
    .export-button {
        margin-top: 10px;
        background-color: #4CAF50;
        color: white;
        padding: 5px 10px;
        border: none;
        border-radius: 5px;
        cursor: pointer;
    }
    .export-button:hover {
        background-color: #45a049;
    }
    </style>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    """,
    unsafe_allow_html=True
)

# メイン表示処理
def show_zip_file_list(sorted_paths):
    page_size = 100  # 1ページ100アイテム
    total_pages = max(1, (len(sorted_paths) - 1) // page_size + 1)  # 括弧を正しく閉じる
    page = st.number_input("ページ番号", min_value=1, max_value=total_pages, step=1, key="page_input")
    
    # ページ情報「◯/◯」を表示
    st.write(f'<p class="page-info">ページ {page}/{total_pages}</p>', unsafe_allow_html=True)

    start = (page - 1) * page_size
    end = start + page_size
    page_files = sorted_paths[start:end]

    # 右側パネル（選択数とエクスポートボタン）
    selected_count = len(st.session_state.get("selected_files", []))
    if st.session_state.get("selected_files", []):
        panel_html = f"""
        <div class="fixed-panel">
            <p>選択中: <strong>{selected_count}</strong>件</p>
            <button class="export-button" onclick="document.getElementById('export_button').click()">📤 エクスポート</button>
        </div>
        """
        st.markdown(panel_html, unsafe_allow_html=True)

    # TOPボタンを左下に配置
    st.markdown(
        '<div style="position: fixed; bottom: 20px; left: 20px; z-index: 100;">'
        '<a href="#top" style="background-color:#444; color:white; padding:10px; text-decoration:none; border-radius:5px;">↑TOP</a>'
        '</div>',
        unsafe_allow_html=True
    )

    # 2列レイアウト
    for i in range(0, len(page_files),
