import streamlit as st
import hashlib
import dropbox
import difflib
import requests
from dropbox.files import FileMetadata
from datetime import datetime

# ========================
# 設定・初期化
# ========================
st.set_page_config(layout="wide")
DROPBOX_REFRESH_TOKEN = st.secrets["DROPBOX_REFRESH_TOKEN"]
APP_KEY = st.secrets["DROPBOX_APP_KEY"]
APP_SECRET = st.secrets["DROPBOX_APP_SECRET"]
ZIP_LIST_URL = st.secrets["ZIP_LIST_URL"]

# ========================
# セッション初期化
# ========================
if "access_token" not in st.session_state:
    auth_flow = dropbox.DropboxOAuth2FlowNoRedirect(APP_KEY, APP_SECRET)
    dbx = dropbox.Dropbox(oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
                          app_key=APP_KEY, app_secret=APP_SECRET)
    st.session_state["access_token"] = dbx._oauth2_access_token
else:
    dbx = dropbox.Dropbox(oauth2_access_token=st.session_state["access_token"])

# ========================
# ユーティリティ関数
# ========================
def make_safe_key(name, path):
    return hashlib.md5((name + path).encode()).hexdigest()

def extract_author(display_name):
    if display_name.startswith('['):
        end = display_name.find(']')
        if end != -1:
            return display_name[1:end]
    return ""

@st.cache_data(ttl=600)
def load_zip_file_list(url):
    try:
        res = requests.get(url)
        res.raise_for_status()
        lines = res.text.strip().splitlines()
        return [line.strip() for line in lines if line.strip()]
    except Exception as e:
        st.error("zip_file_list.txt の取得に失敗しました。")
        st.stop()

@st.cache_data(show_spinner="Dropboxの更新日時を取得中...", ttl=600)
def fetch_zip_metadata(dbx, zip_paths):
    metadata = {}
    for path in zip_paths:
        try:
            res = dbx.files_get_metadata(path)
            if isinstance(res, FileMetadata):
                metadata[path] = res.server_modified
        except Exception:
            continue
    return metadata

def get_thumbnail_url(dbx, zip_path):
    thumb_path = "/サムネイル/" + zip_path.split("/")[-1].replace(".zip", ".jpg")
    try:
        link = dbx.files_get_temporary_link(thumb_path)
        return link.link
    except:
        return None

# ========================
# データ読み込み
# ========================
zip_paths = load_zip_file_list(ZIP_LIST_URL)
zip_files = []
for path in zip_paths:
    name = path.split("/")[-1]
    display_name = name.replace(".zip", "")
    zip_files.append({
        "name": name,
        "path": path,
        "display_name": display_name,
    })

# 並び順選択
sort_order = st.selectbox("並び順を選択", ["タイトル順", "作家順", "新着順"])

# 並び替え
if sort_order == "タイトル順":
    zip_files.sort(key=lambda x: x["display_name"].lower())
elif sort_order == "作家順":
    zip_files.sort(key=lambda x: extract_author(x["display_name"]).lower())
elif sort_order == "新着順":
    metadata = fetch_zip_metadata(dbx, [z["path"] for z in zip_files])
    zip_files.sort(key=lambda x: metadata.get(x["path"], datetime.min), reverse=True)

# ========================
# ページネーション
# ========================
PER_PAGE = 20
max_page = len(zip_files) // PER_PAGE
page = st.number_input("ページ", min_value=0, max_value=max_page, step=1)

start = page * PER_PAGE
end = start + PER_PAGE
current_page_files = zip_files[start:end]

# ========================
# ZIP一覧 + チェックボックス
# ========================
st.write("### ファイル一覧")

selected_keys = []
for zip_file in current_page_files:
    key = make_safe_key(zip_file["name"], zip_file["path"])
    if key not in st.session_state:
        st.session_state[key] = False
    cols = st.columns([1, 5])
    with cols[0]:
        checked = st.checkbox("", value=st.session_state[key], key=key)
        st.session_state[key] = checked
    with cols[1]:
        thumb_url = get_thumbnail_url(dbx, zip_file["path"])
        if thumb_url:
            st.image(thumb_url, use_column_width=True)
        st.caption(zip_file["display_name"])
    if st.session_state[key]:
        selected_keys.append(key)

# ========================
# 選択されたファイル一覧
# ========================
selected_files = [
    z for z in zip_files if st.session_state.get(make_safe_key(z["name"], z["path"]), False)
]

if selected_files:
    st.markdown("### ✅ 選択中のZIPファイル")
    for z in selected_files:
        st.write(z["display_name"])

    if st.button("📤 エクスポート"):
        # SideBooksExport フォルダをクリアして再コピー
        try:
            export_folder = "/SideBooksExport"
            dbx.files_delete_v2(export_folder)
        except:
            pass
        dbx.files_create_folder_v2(export_folder)
        exported = []
        for z in selected_files:
            src = z["path"]
            dst = f"{export_folder}/{z['name']}"
            try:
                dbx.files_copy_v2(src, dst)
                exported.append(z["name"])
            except Exception as e:
                st.error(f"エクスポート失敗: {z['name']}")
        st.success(f"{len(exported)} 件をエクスポートしました。")

# ========================
# TOPボタン（画面追従）
# ========================
st.markdown("""
<style>
.fixed-top-button {
    position: fixed;
    bottom: 20px;
    left: 20px;
    z-index: 9999;
}
</style>
<a href="#top" class="fixed-top-button">
    <button>↑ TOP</button>
</a>
""", unsafe_allow_html=True)
