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
        return paths

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
        existing_content = []
        try:
            metadata, content = dbx.files_download(log_path)
            existing_content = content.content.decode("utf-8-sig").splitlines()
            if existing_content and not existing_content[0].startswith("DateTime"):
                existing_content.insert(0, "DateTime,FileName,Device")
        except dropbox.exceptions.ApiError:
            pass

        rows = []
        for name in file_list:
            rows.append([
                datetime.now(pytz.timezone('Asia/Tokyo')).strftime("%Y-%m-%d %H:%M:%S JST"),
                name,
                f"{device} (Session: {session_id})"
            ])

        if not existing_content:
            rows.insert(0, ["DateTime", "FileName", "Device"])

        all_rows = existing_content + ["...".join(row) for row in rows]

        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", newline="", encoding="utf-8-sig", delete=False) as temp_file:
            writer = csv.writer(temp_file)
            for row in all_rows:
                writer.writerow(row.split(","))

        with open(temp_file.name, "rb") as f:
            dbx.files_upload(f.read(), log_path, mode=dropbox.files.WriteMode("overwrite"))
        os.unlink(temp_file.name)
    except Exception as e:
        st.error(f"出力ログ保存失敗: {str(e)}")
        logger.error(f"出力ログ保存失敗: {log_path}, エラー: {str(e)}", exc_info=True)

# ユーザー情報
# ...

# エクスポート処理
if st.session_state.selected_files:
    st.markdown("### 選択中:")
    st.write(st.session_state.selected_files)

    if st.button("📤 選択中のzipをエクスポート"):
        with st.spinner("📦 エクスポート中..."):
            try:
                for entry in dbx.files_list_folder(EXPORT_FOLDER).entries:
                    dbx.files_delete_v2(f"{EXPORT_FOLDER}/{entry.name}")
            except Exception:
                pass

            failed = []
            for idx, name in enumerate(st.session_state.selected_files, start=1):
                st.write(f"→ {idx}. {name} をエクスポート中...")
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

            save_export_log(st.session_state.selected_files)

        if failed:
            st.warning(f"{len(failed)} 件のファイルがコピーできませんでした")
        else:
            st.success("✅ エクスポートが完了しました")

        for name in st.session_state.selected_files:
            key = make_safe_key(name)
            st.session_state[f"cb_{key}"] = False
        st.session_state.selected_files = []
