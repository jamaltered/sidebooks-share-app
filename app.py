import streamlit as st
import dropbox
import os
import difflib
import io
import zipfile
from PIL import Image
import pandas as pd

# Dropbox 接続（リフレッシュトークン方式）
dbx = dropbox.Dropbox(
    app_key=st.secrets["DROPBOX_APP_KEY"],
    app_secret=st.secrets["DROPBOX_APP_SECRET"],
    oauth2_refresh_token=st.secrets["DROPBOX_REFRESH_TOKEN"]
)

TARGET_FOLDER = st.secrets["TARGET_FOLDER"]
EXPORT_FOLDER = st.secrets["EXPORT_FOLDER"]

# ZIPファイル一覧（事前生成済みリスト）
ZIP_LIST_PATH = "zip_file_list.txt"
with open(ZIP_LIST_PATH, "r", encoding="utf-8") as f:
    all_zip_paths = [line.strip() for line in f.readlines()]

# Streamlit レイアウト
st.set_page_config(layout="wide")
st.title("📚 成年コミック エクスポート")

# セッション初期化
if "selected_files" not in st.session_state:
    st.session_state.selected_files = []

# ZIPファイル表示（簡易版）
def show_zip_file_list():
    for path in all_zip_paths:
        name = os.path.basename(path)
        col1, col2 = st.columns([0.05, 0.95])
        with col1:
            checked = st.checkbox("", key=f"cb_{name}", value=name in st.session_state.selected_files)
            if checked and name not in st.session_state.selected_files:
                st.session_state.selected_files.append(name)
            elif not checked and name in st.session_state.selected_files:
                st.session_state.selected_files.remove(name)
        with col2:
            st.text(name)

show_zip_file_list()

# 選択カウント + エクスポートボタン
st.markdown("---")
st.markdown(f"✅ **選択中：{len(st.session_state.selected_files)}件**")

# エクスポート処理
if st.session_state.selected_files:
    if st.button("📤 選択中のZIPをエクスポート"):
        failed = []
        for name in st.session_state.selected_files:
            try:
                # 近似一致でフルパス検索
                match = difflib.get_close_matches(name, all_zip_paths, n=1, cutoff=0.7)
                if match:
                    src_path = match[0]
                    dest_path = f"{EXPORT_FOLDER}/{name}"
                    dbx.files_copy_v2(src_path, dest_path, allow_shared_folder=True, autorename=True)
                else:
                    st.error(f"❌ {name} のコピー元ファイルが見つかりませんでした。")
                    failed.append(name)
            except dropbox.exceptions.ApiError as e:
                st.error(f"❌ {name} のコピーに失敗: {e}")
                failed.append(name)

        # ログ保存
        log_path = os.path.join(os.path.dirname(ZIP_LIST_PATH), "export_log.csv")
        df = pd.DataFrame({"filename": st.session_state.selected_files})
        df.to_csv(log_path, index=False, encoding="utf-8-sig")
        st.success("✅ エクスポートが完了しました。")

