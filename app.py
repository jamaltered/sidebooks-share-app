import os
import hashlib
import difflib
import streamlit as st
import dropbox

# Dropbox認証（Streamlit Secrets使用）
dbx = dropbox.Dropbox(
    app_key=st.secrets["DROPBOX_APP_KEY"],
    app_secret=st.secrets["DROPBOX_APP_SECRET"],
    oauth2_refresh_token=st.secrets["DROPBOX_REFRESH_TOKEN"]
)

# パス設定
TARGET_FOLDER = st.secrets["TARGET_FOLDER"]  # 例: "/成年コミック"
THUMBNAIL_FOLDER = st.secrets["THUMBNAIL_FOLDER"]  # 例: "/サムネイル"
EXPORT_FOLDER = st.secrets["EXPORT_FOLDER"]  # 例: "/SideBooksExport"
ZIP_LIST_PATH = "https://raw.githubusercontent.com/＜あなたのユーザー名＞/＜リポジトリ名＞/main/zip_file_list.txt"

# UI設定
st.set_page_config(page_title="SideBooksエクスポート", layout="wide")
st.markdown('<a id="top"></a>', unsafe_allow_html=True)

# ステート初期化
if "selected_files" not in st.session_state:
    st.session_state.selected_files = set()
if "page" not in st.session_state:
    st.session_state.page = 1

# zip_file_list.txt の読み込み
@st.cache_data
def load_zip_file_list():
    try:
        import requests
        res = requests.get(ZIP_LIST_PATH)
        res.raise_for_status()
        return res.text.strip().splitlines()
    except Exception:
        st.error("zip_file_list.txt の取得に失敗しました。")
        return []

# ユニークなキーを生成
def make_safe_key(name, fullpath):
    return hashlib.md5(f"{name}_{fullpath}".encode("utf-8")).hexdigest()

# サムネイルの一時リンクを取得
def get_thumbnail_link(filename):
    try:
        path = f"{THUMBNAIL_FOLDER}/{filename}"
        link = dbx.files_get_temporary_link(path).link
        return link
    except:
        return None

# Dropbox内のエクスポートフォルダを空にする
def clear_export_folder():
    try:
        entries = dbx.files_list_folder(EXPORT_FOLDER).entries
        for entry in entries:
            dbx.files_delete_v2(entry.path_display)
    except Exception as e:
        st.warning(f"エクスポートフォルダの初期化に失敗: {e}")

# エクスポート処理（近似検索付き）
def export_selected_files(zip_paths):
    failed = []
    clear_export_folder()
    for selected in st.session_state.selected_files:
        found = [z for z in zip_paths if z.endswith(f"/{selected}")]
        if found:
            src_path = found[0]
        else:
            candidates = difflib.get_close_matches(
                selected, [os.path.basename(z) for z in zip_paths], n=1, cutoff=0.7
            )
            if candidates:
                matched = candidates[0]
                matched_path = next((z for z in zip_paths if os.path.basename(z) == matched), None)
                if matched_path:
                    src_path = matched_path
                else:
                    failed.append(selected)
                    continue
            else:
                failed.append(selected)
                continue
        try:
            dest_path = f"{EXPORT_FOLDER}/{selected}"
            dbx.files_copy_v2(src_path, dest_path, allow_shared_folder=True, autorename=True)
        except Exception as e:
            st.error(f"❌ {selected} のコピーに失敗: {e}")
            failed.append(selected)
    return failed

# ZIPファイル一覧を表示
def show_zip_file_list(zip_paths):
    page_size = 200
    max_page = max((len(zip_paths) - 1) // page_size + 1, 1)
    page = st.number_input("ページ番号", min_value=1, max_value=max_page, step=1, value=st.session_state.page)
    st.session_state.page = page

    start = (page - 1) * page_size
    end = start + page_size
    entries = zip_paths[start:end]

    st.markdown("### 📚 コミック一覧")
    st.markdown(f"✅ 選択中: {len(st.session_state.selected_files)}")

    if st.session_state.selected_files:
        if st.button("📤 選択中のZIPをエクスポート", type="primary"):
            with st.spinner("エクスポート中..."):
                failed = export_selected_files(zip_paths)
                if failed:
                    st.warning(f"⚠ 一部失敗: {failed}")
                else:
                    st.success("✅ エクスポート完了！")

    for full_path in entries:
        name = os.path.basename(full_path)
        thumb_candidates = [
            name.replace(".zip", ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]
        ]
        image_url = None
        for thumb in thumb_candidates:
            link = get_thumbnail_link(thumb)
            if link:
                image_url = link
                break
        col1, col2 = st.columns([1, 4])
        with col1:
            if image_url:
                st.image(image_url, caption=name, use_container_width=True)
            else:
                st.write("🔲 No thumbnail")
        with col2:
            key = make_safe_key(name, full_path)
            checked = st.checkbox(name, key=f"cb_{key}", value=(name in st.session_state.selected_files))
            if checked:
                st.session_state.selected_files.add(name)
            else:
                st.session_state.selected_files.discard(name)

    # TOPボタン
    st.markdown("""
    <a href="#top" class="top-button">↑ Top</a>
    <style>
    .top-button {
      position: fixed;
      bottom: 24px;
      left: 24px;
      background: #007bff;
      color: white;
      padding: 12px 20px;
      font-size: 18px;
      border-radius: 50px;
      text-decoration: none;
      z-index: 9999;
      box-shadow: 0 2px 6px rgba(0,0,0,0.2);
    }
    </style>
    """, unsafe_allow_html=True)

# アプリ本体
zip_paths = load_zip_file_list()
if zip_paths:
    show_zip_file_list(zip_paths)
else:
    st.stop()
