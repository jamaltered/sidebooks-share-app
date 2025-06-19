import os
import io
import csv
import base64
from datetime import datetime
from PIL import Image
import streamlit as st
import dropbox
import pandas as pd

# 🔐 Dropbox認証（.envではなく、Secretsから取得）
APP_KEY = os.environ.get("DROPBOX_APP_KEY")
APP_SECRET = os.environ.get("DROPBOX_APP_SECRET")
REFRESH_TOKEN = os.environ.get("DROPBOX_REFRESH_TOKEN")

if not (APP_KEY and APP_SECRET and REFRESH_TOKEN):
    st.error("Dropboxの認証情報が不足しています")
    st.stop()

dbx = dropbox.Dropbox(
    app_key=APP_KEY,
    app_secret=APP_SECRET,
    oauth2_refresh_token=REFRESH_TOKEN
)

user_name = dbx.users_get_current_account().name.display_name

# 📁 パス設定
ZIP_FOLDER = "/成年コミック"
THUMBNAIL_FOLDER = "/サムネイル"
EXPORT_FOLDER = "/SideBooksExport"  # Dropbox共有フォルダ
LOG_FILE = "export_log.csv"

st.set_page_config(page_title="サムネイルからSideBooks出力", layout="wide")
st.title("🖼 サムネイル選択でSideBooksへエクスポート")
st.caption(f"こんにちは、{user_name} さん")

# サムネイル一覧取得
@st.cache_data
def list_thumbnails():
    try:
        entries = dbx.files_list_folder(THUMBNAIL_FOLDER).entries
        return sorted([e.name for e in entries if e.name.lower().endswith((".jpg", ".jpeg", ".png"))])
    except Exception as e:
        st.error(f"サムネイル一覧取得エラー: {e}")
        return []

# サムネイル画像取得
@st.cache_data
def get_thumbnail_image(name):
    try:
        metadata, res = dbx.files_download(f"{THUMBNAIL_FOLDER}/{name}")
        return Image.open(io.BytesIO(res.content))
    except Exception as e:
        st.warning(f"{name} 読み込み失敗: {e}")
        return None

# ZIPファイルコピー（SideBooksExportへ）
def copy_zip_file(zip_name):
    try:
        from_path = f"{ZIP_FOLDER}/{zip_name}"
        to_path = f"{EXPORT_FOLDER}/{zip_name}"
        dbx.files_copy_v2(from_path, to_path, allow_shared_folder=True, autorename=True)
        return to_path
    except dropbox.exceptions.ApiError:
        # fallback: download/upload方式
        try:
            _, res = dbx.files_download(from_path)
            dbx.files_upload(res.content, to_path, mode=dropbox.files.WriteMode.overwrite)
            return to_path
        except Exception as e:
            st.error(f"コピー失敗: {e}")
            return None

# ログ記録
def log_export(user, filename):
    write_header = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["ユーザー名", "ファイル名", "日時"])
        writer.writerow([user, filename, datetime.now().isoformat()])

# ✅ 選択状態保持
if "selected_thumbnails" not in st.session_state:
    st.session_state.selected_thumbnails = set()

# 📌 選択されたZIPを表示・エクスポート
st.subheader("📌 選択中")
if st.session_state.selected_thumbnails:
    for thumb in st.session_state.selected_thumbnails:
        zip_candidate = thumb.replace(".jpg", ".zip").replace(".jpeg", ".zip").replace(".png", ".zip")
        display_name = zip_candidate.replace("(成年コミック)", "").strip()
        st.markdown(f"✅ `{display_name}`")
    if st.button("📤 選択中のZIPをSideBooksExportにエクスポート"):
        for thumb in st.session_state.selected_thumbnails:
            zip_name = thumb.replace(".jpg", ".zip").replace(".jpeg", ".zip").replace(".png", ".zip")
            result = copy_zip_file(zip_name)
            if result:
                st.success(f"{zip_name} をSideBooksExportに保存しました")
                log_export(user_name, zip_name)
else:
    st.info("サムネイルを選択してください")

# 🖼 サムネイルグリッド表示＋チェックボックス
thumbs = list_thumbnails()
for i in range(0, len(thumbs), 5):
    row = st.columns(5)
    for j in range(5):
        if i + j < len(thumbs):
            thumb_name = thumbs[i + j]
            img = get_thumbnail_image(thumb_name)
            with row[j]:
                if img:
                    st.image(img, width=150)
                label = thumb_name.replace(".jpg", "").replace(".jpeg", "").replace(".png", "")
                checked = st.checkbox(label, value=(thumb_name in st.session_state.selected_thumbnails), key=thumb_name)
                if checked:
                    st.session_state.selected_thumbnails.add(thumb_name)
                else:
                    st.session_state.selected_thumbnails.discard(thumb_name)

# 📄 エクスポートログ
st.markdown("---")
st.subheader("📄 エクスポートログ")
if os.path.exists(LOG_FILE):
    df = pd.read_csv(LOG_FILE)
    st.dataframe(df, use_container_width=True)
    st.download_button("📥 ログをCSVでダウンロード", df.to_csv(index=False), file_name="export_log.csv", mime="text/csv")
else:
    st.info("まだログがありません。")

