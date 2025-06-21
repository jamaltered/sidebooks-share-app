import streamlit as st
import dropbox
import os
import difflib
import pandas as pd

# Dropbox API設定
ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN")  # .envで設定
dbx = dropbox.Dropbox(ACCESS_TOKEN)

TARGET_FOLDER = "/成年コミック"
EXPORT_FOLDER = "/SideBooksExport"
THUMBNAIL_FOLDER = "/サムネイル"
EXPORT_LOG_PATH = "/成年コミック/export_log.csv"
ZIP_LIST_PATH = "zip_file_list.txt"  # ローカル

# --- zip_file_list.txt の読み込み ---
with open(ZIP_LIST_PATH, "r", encoding="utf-8") as f:
    all_zip_paths = [line.strip() for line in f.readlines()]

# --- 近似一致で実パスを取得する ---
def find_closest_path(zip_name):
    matches = difflib.get_close_matches(zip_name, all_zip_paths, n=1, cutoff=0.7)
    return matches[0] if matches else None

# --- export_log の保存 ---
def save_export_log(selected_files):
    df = pd.DataFrame({"filename": selected_files})
    df.to_csv(EXPORT_LOG_PATH, index=False)

# --- UI表示 ---
st.set_page_config(layout="wide")
st.markdown("<style>button[kind='primary'] {color: white !important;}</style>", unsafe_allow_html=True)

if "selected_files" not in st.session_state:
    st.session_state.selected_files = []

# --- エクスポートボタン（常に上に表示） ---
st.markdown("### 📤 選択中のZIPをエクスポート")
if st.button("エクスポート実行"):
    failed = []
    for name in st.session_state.selected_files:
        dest_path = f"{EXPORT_FOLDER}/{name}"
        try:
            src_path = f"{TARGET_FOLDER}/{name}"
            dbx.files_copy_v2(src_path, dest_path, allow_shared_folder=True, autorename=True)
        except dropbox.exceptions.ApiError:
            # エラー時に近似ファイル検索
            matched_path = find_closest_path(name)
            if matched_path:
                try:
                    dbx.files_copy_v2(matched_path, dest_path, allow_shared_folder=True, autorename=True)
                    continue
                except Exception as e:
                    st.error(f"❌ {name} のコピーに失敗: {e}")
            else:
                st.error(f"❌ {name} のコピーに失敗（候補なし）")
            failed.append(name)
    if failed:
        st.warning("一部ファイルのコピーに失敗しました。")
    else:
        save_export_log(st.session_state.selected_files)
        st.success("✅ エクスポートが完了しました。")

# --- ファイル表示（ページごと） ---
per_page = 40
all_files = [os.path.basename(path) for path in all_zip_paths]
total_pages = (len(all_files) - 1) // per_page + 1

if "page" not in st.session_state:
    st.session_state.page = 0

col1, col2, col3, col4 = st.columns([1, 2, 1, 3])
with col1:
    if st.button("← 前へ") and st.session_state.page > 0:
        st.session_state.page -= 1
with col2:
    st.markdown(f"**{st.session_state.page + 1} / {total_pages} ページ**")
with col3:
    if st.button("次へ →") and st.session_state.page < total_pages - 1:
        st.session_state.page += 1
with col4:
    selected_page = st.selectbox("ページジャンプ", list(range(1, total_pages + 1)), index=st.session_state.page)
    st.session_state.page = selected_page - 1

# --- チェック状態表示 ---
st.markdown(f"🗂️ 選択中：{len(st.session_state.selected_files)} 件")

# --- 現在のページのファイル表示 ---
start = st.session_state.page * per_page
end = start + per_page
page_files = all_files[start:end]

cols = st.columns(2)
for idx, zip_name in enumerate(page_files):
    col = cols[idx % 2]
    with col:
        thumbnail_path = f"{THUMBNAIL_FOLDER}/{zip_name.replace('.zip', '.jpg')}"
        try:
            # Dropbox からの画像リンクを取得して表示
            metadata = dbx.files_get_temporary_link(thumbnail_path)
            st.image(metadata.link, use_container_width=True)
        except:
            st.text("[サムネイルなし]")

        # チェックボックス
        checked = st.checkbox(f"{zip_name}", key=zip_name)
        if checked and zip_name not in st.session_state.selected_files:
            st.session_state.selected_files.append(zip_name)
        elif not checked and zip_name in st.session_state.selected_files:
            st.session_state.selected_files.remove(zip_name)

# --- TOPボタン ---
st.markdown("""
    <style>
    .top-button {
        position: fixed;
        bottom: 80px;
        right: 30px;
        background-color: #555;
        color: white;
        padding: 10px 16px;
        border-radius: 8px;
        text-align: center;
        z-index: 100;
        cursor: pointer;
    }
    </style>
    <div class="top-button" onclick="window.scrollTo(0, 0)">TOP</div>
""", unsafe_allow_html=True)
