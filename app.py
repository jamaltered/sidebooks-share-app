# app.py 全体構成（最新版）
# --- すべての機能を統合した完成版 ---

import streamlit as st
import dropbox
import hashlib
import difflib
import requests
import os
import logging
import re
import csv
from datetime import datetime
import uuid
import pytz
import tempfile

# --- ログ設定 ---
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

# Dropbox 接続
dbx = dropbox.Dropbox(app_key=APP_KEY, app_secret=APP_SECRET, oauth2_refresh_token=REFRESH_TOKEN)

# --- 初期化 ---
st.set_page_config(layout="wide")
st.markdown('<div id="top"></div>', unsafe_allow_html=True)
st.title("📚 SideBooks ZIP共有アプリ")
if "selected_files" not in st.session_state:
    st.session_state.selected_files = []

# --- ユーティリティ関数 ---
def make_safe_key(name):
    return hashlib.md5(name.encode()).hexdigest()

def normalize_filename(zip_name):
    match = re.match(r"^\(.*?\)\s*\[(.+?)\]\s*(.+?)\.zip$", zip_name)
    if match:
        author, title = match.groups()
        return f"[{author}] {title}".strip()
    else:
        return os.path.splitext(zip_name)[0]

def format_display_name(name):
    if "] " in name:
        try:
            author = name.split("]")[0].split("[")[-1]
            title = "] ".join(name.split("] ")[1:])
            return f"[{author}] {title}"
        except:
            return name
    return name

def get_thumbnail_path(name):
    thumb_name = normalize_filename(os.path.basename(name))
    thumb_path = f"{THUMBNAIL_FOLDER}/{thumb_name}.jpg"
    try:
        link = dbx.files_get_temporary_link(thumb_path).link
        return link
    except:
        return None

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
    else:
        return paths

def find_similar_path(filename, zip_paths):
    candidates = difflib.get_close_matches(filename, zip_paths, n=1, cutoff=0.7)
    return candidates[0] if candidates else None

def load_zip_file_list():
    try:
        response = requests.get(ZIP_LIST_URL)
        response.raise_for_status()
        return [line.strip() for line in response.text.splitlines() if line.strip()]
    except Exception as e:
        st.error(f"zip_file_list.txt の取得に失敗しました: {e}")
        return []

def deduplicate_zip_paths(paths):
    seen = {}
    for path in paths:
        name = os.path.basename(path)
        norm_name = normalize_filename(name)

        series_pattern = r"(上|中|下|前編|後編|Ⅰ|Ⅱ|Ⅲ|Ⅳ|Ⅴ|Ⅵ|Ⅶ|Ⅷ|Ⅸ|Ⅹ)"
        is_series = re.search(series_pattern, norm_name)

        key = re.sub(r"\s*\[DL版\]|\s*\(DL版\)", "", norm_name).strip()
        if is_series:
            key += "_series"

        if key in seen:
            if "[DL版]" in normalize_filename(seen[key]):
                continue
            if "[DL版]" in norm_name:
                seen[key] = path
        else:
            seen[key] = path
    return list(seen.values())

# --- ZIPファイル表示処理 ---
def show_zip_file_list(zip_paths):
    per_page = 20
    total_pages = (len(zip_paths) + per_page - 1) // per_page
    current_page = st.number_input("ページ選択", 1, total_pages, 1)

    start = (current_page - 1) * per_page
    end = start + per_page
    current_files = zip_paths[start:end]

    for path in current_files:
        name = os.path.basename(path)
        display_name = format_display_name(normalize_filename(name))
        key = make_safe_key(name)

        cols = st.columns([1, 5])
        with cols[0]:
            thumb = get_thumbnail_path(name)
            if thumb:
                st.image(thumb, use_container_width=True)
            else:
                st.markdown("🖼️ サムネなし")

        with cols[1]:
            checked = st.checkbox(display_name, key=f"cb_{key}", value=key in st.session_state.selected_files)
            if checked:
                if key not in st.session_state.selected_files:
                    st.session_state.selected_files.append(key)
            else:
                if key in st.session_state.selected_files:
                    st.session_state.selected_files.remove(key)

# --- エクスポート処理 ---
def export_selected_files(zip_paths):
    zip_path_dict = {make_safe_key(os.path.basename(p)): p for p in zip_paths}
    export_list = [zip_path_dict[k] for k in st.session_state.selected_files if k in zip_path_dict]

    if not export_list:
        st.warning("エクスポート対象が選択されていません。")
        return

    with st.spinner("エクスポート中..."):
        try:
            dbx.files_delete_v2(EXPORT_FOLDER)
        except:
            pass
        dbx.files_create_folder_v2(EXPORT_FOLDER)

        for path in export_list:
            dest = f"{EXPORT_FOLDER}/{os.path.basename(path)}"
            try:
                dbx.files_copy_v2(path, dest)
            except dropbox.exceptions.ApiError:
                sim_path = find_similar_path(path, zip_paths)
                if sim_path:
                    try:
                        dbx.files_copy_v2(sim_path, dest)
                    except Exception as e:
                        logger.warning(f"コピー失敗: {sim_path} -> {dest}: {e}")
                else:
                    logger.warning(f"近似ファイル見つからず: {path}")

        log_path = f"{TARGET_FOLDER}/export_log.csv"
        log_data = [[datetime.now(pytz.timezone("Asia/Tokyo")).isoformat(), os.path.basename(p)] for p in export_list]

        with tempfile.NamedTemporaryFile("w", delete=False, newline="", encoding="utf-8") as tmp:
            writer = csv.writer(tmp)
            writer.writerow(["timestamp", "filename"])
            writer.writerows(log_data)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as f:
            dbx.files_upload(f.read(), log_path, mode=dropbox.files.WriteMode("overwrite"))

        st.success("エクスポートが完了しました！")

        st.session_state.selected_files = []
        for key in list(st.session_state.keys()):
            if key.startswith("cb_"):
                st.session_state[key] = False

# --- メイン実行部 ---
zip_paths = deduplicate_zip_paths(load_zip_file_list())
sort_option = st.selectbox("並び順", ["名前順", "作家順"])
sorted_zip_paths = sort_zip_paths(zip_paths, sort_option)

st.markdown('<a href="#top">↑ TOPに戻る</a>', unsafe_allow_html=True)

show_zip_file_list(sorted_zip_paths)

if st.session_state.selected_files:
    st.markdown("---")
    if st.button("📤 選択したZIPをエクスポート"):
        export_selected_files(zip_paths)

st.markdown('<a href="#top">↑ TOPに戻る</a>', unsafe_allow_html=True)
