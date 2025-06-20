# app.py（最新版：ジャンプ改善＋日本語50音対応＋デバッグ付き）

import os
import re
import io
import datetime
import streamlit as st
import dropbox
import pandas as pd
from dotenv import load_dotenv
from pykakasi import kakasi

load_dotenv()
dbx = dropbox.Dropbox(
    app_key=os.getenv("DROPBOX_APP_KEY"),
    app_secret=os.getenv("DROPBOX_APP_SECRET"),
    oauth2_refresh_token=os.getenv("DROPBOX_REFRESH_TOKEN")
)

SOURCE_FOLDER = "/成年コミック"
THUMBNAIL_FOLDER = "/サムネイル"
EXPORT_FOLDER = "/SideBooksExport"
LOG_PATH = f"{SOURCE_FOLDER}/export_log.csv"

kks = kakasi()
kks.setMode("H", "a")
kks.setMode("K", "a")
kks.setMode("J", "a")
kks.setMode("r", "Hepburn")
conv = kks.getConverter()

jp_groups = {
    "あ行": "あいうえお",
    "か行": "かきくけこ",
    "さ行": "さしすせそ",
    "た行": "たちつてと",
    "な行": "なにぬねの",
    "は行": "はひふへほ",
    "ま行": "まみむめも",
    "や行": "やゆよ",
    "ら行": "らりるれろ",
    "わ行": "わをん"
}

alpha_groups = ["A〜E", "F〜J", "K〜O", "P〜T", "U〜Y", "Z"]

def get_group_label(name):
    hira = conv.do(name[0]).lower()
    if hira[0].isalpha():
        ascii = hira[0].upper()
        for group in alpha_groups:
            if ascii >= group[0] and ascii <= group[-1]:
                return group
        return "Z"
    for label, chars in jp_groups.items():
        if hira[0] in chars:
            return label
    return "その他"

def is_serialized(name):
    name = os.path.splitext(name)[0]
    return bool(re.search(r"(上|中|下|前|後|\b\d+\b|[IVX]{1,5}|\d+-\d+)$", name, re.IGNORECASE))

def clean_title(name):
    name = os.path.splitext(name)[0]
    return name.replace("(成年コミック)", "").strip()

def extract_author(name):
    match = re.match(r"\[([^\]]+)\]", name)
    return match.group(1) if match else ""

def get_thumbnails():
    try:
        res = dbx.files_list_folder(THUMBNAIL_FOLDER)
        return [entry.name for entry in res.entries if entry.name.endswith(".jpg")]
    except:
        return []

def map_zip_paths():
    zip_map = {}
    res = dbx.files_list_folder(SOURCE_FOLDER, recursive=True)
    entries = res.entries
    while res.has_more:
        res = dbx.files_list_folder_continue(res.cursor)
        entries.extend(res.entries)
    for entry in entries:
        if isinstance(entry, dropbox.files.FileMetadata) and entry.name.lower().endswith(".zip"):
            zip_map[entry.name] = entry.path_display
    return zip_map

def get_temporary_image_url(path):
    try:
        link = dbx.files_get_temporary_link(path)
        return link.link
    except:
        return None

def export_zip(zip_name, src_path):
    try:
        _, res = dbx.files_download(src_path)
        dbx.files_upload(res.content, f"{EXPORT_FOLDER}/{zip_name}", mode=dropbox.files.WriteMode.overwrite)
        return True
    except:
        return False

def write_export_log(log_data):
    df = pd.DataFrame(log_data, columns=["timestamp", "username", "filename"])
    with io.StringIO() as buffer:
        df.to_csv(buffer, index=False)
        dbx.files_upload(buffer.getvalue().encode("utf-8"), LOG_PATH, mode=dropbox.files.WriteMode.overwrite)

# UI
st.set_page_config(page_title="SideBooks ZIP共有", layout="wide")
st.title("📦 ZIP画像一覧ビューア（Dropbox共有フォルダ）")

try:
    user_name = dbx.users_get_current_account().name.display_name
except:
    user_name = "guest"

st.markdown(f"こんにちは、{user_name} さん")

sort_option = st.selectbox("並び順を選択してください", ["タイトル順", "作家順"])

thumbnails = get_thumbnails()
zip_paths = map_zip_paths()

st.info(f"🔍 サムネイル数: {len(thumbnails)} 件")
st.info(f"📦 ZIPファイル数: {len(zip_paths)} 件")

unique_titles = {}
for thumb in thumbnails:
    zip_name = thumb.replace(".jpg", ".zip")
    clean = clean_title(zip_name)
    if is_serialized(clean) or clean not in unique_titles:
        unique_titles[clean] = zip_name

st.info(f"🧠 表示対象数: {len(unique_titles)} 件")

if sort_option == "作家順":
    sorted_items = sorted(unique_titles.items(), key=lambda x: extract_author(x[1]))
else:
    sorted_items = sorted(unique_titles.items(), key=lambda x: x[0].lower())

grouped = {}
for clean, zip_name in sorted_items:
    group = get_group_label(clean)
    grouped.setdefault(group, []).append((clean, zip_name))

st.markdown("🔤 ジャンプ: " + " ".join([f"[{k}](#{k})" for k in list(jp_groups.keys()) + alpha_groups]))

selection = []
for group in list(jp_groups.keys()) + alpha_groups:
    if group in grouped:
        st.markdown(f"<h2 id='{group}'>===== {group} =====</h2>", unsafe_allow_html=True)
        for clean, zip_name in grouped[group]:
            col1, col2 = st.columns([1, 9])
            with col1:
                checked = st.checkbox("選択", key=zip_name)
            with col2:
                path = f"{THUMBNAIL_FOLDER}/{zip_name.replace('.zip', '.jpg')}"
                url = get_temporary_image_url(path)
                if url:
                    st.image(url, width=1200)
                st.caption(clean)
            if checked:
                selection.append(zip_name)

if selection:
    if st.button("📤 選択したZIPをエクスポート"):
        logs = []
        for zip_name in selection:
            if zip_name in zip_paths:
                if export_zip(zip_name, zip_paths[zip_name]):
                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    logs.append([now, user_name, zip_name])
        if logs:
            write_export_log(logs)
            st.success(f"{len(logs)} 件をエクスポート＆ログ記録しました！")
