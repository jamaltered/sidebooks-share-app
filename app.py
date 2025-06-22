import streamlit as st
import dropbox
import hashlib
import difflib
import requests
import pandas as pd
import os
import logging
import re

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
        # フォールバック
        return os.path.splitext(zip_name)[0]

# サムネイルパスを生成
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
    else:
        return paths

# エクスポートログ保存
def save_export_log(file_list):
    df = pd.DataFrame(file_list, columns=["ExportedFile"])
    try:
        dbx.files_upload(df.to_csv(index=False).encode("utf-8"), f"{TARGET_FOLDER}/export_log.csv", mode=dropbox.files.WriteMode.overwrite)
    except Exception as e:
        st.error(f"エクスポートログ保存失敗: {e}")

# 近似検索で元ファイルパスを特定
def find_similar_path(filename, zip_paths):
    candidates = difflib.get_close_matches(filename, zip_paths, n=1, cutoff=0.7)
    return candidates[0] if candidates else None

# カスタムCSSで2列グリッド、チェックボックス、フォントサイズを調整
st.markdown(
    """
    <style>
    /* グリッドコンテナ */
    .grid-container {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        padding: 10px;
    }
    /* 各グリッドアイテム */
    .grid-item {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    /* サムネイル */
    .grid-item img {
        max-width: 150px;
        width: 100%;
    }
    /* チェックボックスとラベル */
    .stCheckbox > div {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .stCheckbox > div > label {
        font-size: 1.2em !important;
    }
    /* サムネイルなしのテキスト */
    .no-thumbnail {
        font-size: 1.2em !important;
    }
    /* スマホでも2列を維持 */
    @media (max-width: 600px) {
        .grid-container {
            grid-template-columns: 1fr 1fr;
            gap: 5px;
        }
        .grid-item img {
            max-width: 120px;
        }
        .stCheckbox > div > label {
            font-size: 1.1em !important;
        }
        .no-thumbnail {
            font-size: 1.1em !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)

# メイン表示処理
def show_zip_file_list(sorted_paths):
    page_size = 100  # 1ページ100アイテム
    total_pages = max(1, (len(sorted_paths) - 1) // page_size + 1)
    page = st.number_input("ページ番号", min_value=1, max_value=total_pages, step=1, key="page_input")
    
    # ページ情報「◯/◯」を表示
    st.markdown(f"**ページ {page}/{total_pages}**")

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

    # グリッドコンテナ
    with st.container():
        st.markdown('<div class="grid-container">', unsafe_allow_html=True)
        for path in page_files:
            name = os.path.basename(path)
            display_name = format_display_name(name)
            key = make_safe_key(name)

            # グリッドアイテム
            st.markdown('<div class="grid-item">', unsafe_allow_html=True)
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

            checked = st.checkbox(
                display_name,
                key=f"cb_{key}",
                value=(name in st.session_state.selected_files),
                label_visibility="visible"
            )
            if checked:
                if name not in st.session_state.selected_files:
                    st.session_state.selected_files.append(name)
            else:
                if name in st.session_state.selected_files:
                    st.session_state.selected_files.remove(name)
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

# ---------------------- アプリ開始 ------------------------

st.set_page_config(layout="wide")
st.markdown('<div id="top"></div>', unsafe_allow_html=True)
st.title("📚 SideBooks ZIP共有アプリ")

# 初期化
if "selected_files" not in st.session_state:
    st.session_state.selected_files = []

# 並び順セレクト
sort_option = st.selectbox("表示順", ["名前順", "作家順"])
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
        save_export_log(st.session_state.selected_files)
        if failed:
            st.warning(f"{len(failed)} 件のファイルがコピーできませんでした。")
        else:
            st.success("✅ エクスポートが完了しました！")

# ZIP一覧表示
show_zip_file_list(sorted_zip_paths)
