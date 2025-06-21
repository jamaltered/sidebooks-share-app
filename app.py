[コード本体は長いため別ファイルとして分割する必要があります]

以下のようにサムネイルのレスポンシブ表示部分を改良します：

```python
# CSS + HTML グリッドスタイル
st.markdown("""
<style>
.thumb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 16px;
  margin-top: 1rem;
}
.thumb-card {
  background-color: #fff;
  padding: 10px;
  border-radius: 8px;
  box-shadow: 0 0 6px rgba(0,0,0,0.1);
}
.thumb-card img {
  width: 100%;
  height: auto;
  border-radius: 6px;
}
.thumb-title {
  font-size: 0.85rem;
  font-weight: bold;
  margin-top: 8px;
  color: #111;
  text-align: center;
}
</style>
<div class="thumb-grid">
""", unsafe_allow_html=True)

# サムネイル表示エリア
for thumb in visible_thumbs:
    zip_name = thumb.rsplit('.', 1)[0] + ".zip"
    if zip_name not in zip_set:
        continue

    title_display = re.sub(r"^\(成年コミック\)\s*", "", zip_name.replace(".zip", ""))
    thumb_path = f"{THUMBNAIL_FOLDER}/{thumb}"
    url = get_temporary_image_url(thumb_path)

    if url:
        st.markdown(f"""
        <div class="thumb-card">
            <img src="{url}" />
            <div class="thumb-title">{title_display}</div>
        </div>
        """, unsafe_allow_html=True)
        st.checkbox("選択", value=zip_name in st.session_state.selected_files,
                    key=zip_name, on_change=toggle_selection, args=(zip_name,))

st.markdown("</div>", unsafe_allow_html=True)
```

---

このレスポンシブ対応済みの `app.py` 全体コードを生成・保存しますか？それとも上記を手動で組み込みますか？
