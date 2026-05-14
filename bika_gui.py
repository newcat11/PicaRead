# -*- coding: utf-8 -*-
"""
PicaWeb 漫画阅读器 GUI
"""
import json, os, tempfile
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st
import img2pdf

from bika_api import BikaClient, ComicInfo, EpisodeInfo, PageInfo, AuthError

st.set_page_config(page_title="PicaRead 漫画阅读器", page_icon="📚", layout="wide",
                   initial_sidebar_state="expanded")

# ---- 持久化 ----
SESSION_FILE = Path.home() / ".bika_session.json"

def save_session(token: str, name: str):
    try:
        SESSION_FILE.write_text(json.dumps({"token": token, "name": name, "saved_at": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")
        SESSION_FILE.chmod(0o600)
    except: pass

def load_session() -> dict | None:
    try:
        if SESSION_FILE.exists():
            return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except: pass
    return None

def clear_session():
    try:
        if SESSION_FILE.exists(): SESSION_FILE.unlink()
    except: pass

# ---- 样式 ----
st.markdown("""
<style>
.comic-card { border: 1px solid #e0e0e0; border-radius: 8px; padding: 8px;
    cursor: pointer; transition: box-shadow 0.15s; text-align: center; }
.comic-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,0.15); }
.comic-title { font-weight: bold; font-size: 13px; margin: 6px 0 2px; }
.comic-sub { font-size: 11px; color: #888; }
/* 阅读器图片紧凑排列 */
.reader-img { margin: 0; padding: 0; }
.reader-img img { margin-bottom: 0; }
.reader-img + .reader-img { margin-top: -8px; }
div[data-testid="stImage"] { margin-bottom: 2px !important; }
div[data-testid="stVerticalBlock"] > div[data-testid="stImage"] { margin-bottom: 0 !important; }
</style>
""", unsafe_allow_html=True)

# ---- 状态初始化 ----
DEFAULTS = {
    "client": None, "logged_in": False, "token": None, "user_name": "",
    "page": "browse", "selected_comic_id": None, "selected_comic_data": None,
    "reader_comic_id": None, "reader_ep_order": 0, "reader_ep_title": "",
}
for k, v in DEFAULTS.items():
    if k not in st.session_state: st.session_state[k] = v

def get_client():
    if st.session_state.client: return st.session_state.client
    if st.session_state.token:
        c = BikaClient(); c.set_token(st.session_state.token)
        st.session_state.client = c; return c
    return None

def do_login(token: str, name: str, remember: bool = True):
    st.session_state.token = token
    st.session_state.user_name = name
    st.session_state.logged_in = True
    if remember: save_session(token, name)

def do_logout():
    clear_session()
    for k in list(st.session_state.keys()): del st.session_state[k]
    st.rerun()

# ---- 自动恢复 ----
if not st.session_state.logged_in and not st.session_state.token:
    saved = load_session()
    if saved and saved.get("token"):
        try:
            c = BikaClient(); c.set_token(saved["token"])
            st.session_state.client = c
            st.session_state.token = saved["token"]
            st.session_state.user_name = c.user.name or saved.get("name", "")
            st.session_state.logged_in = True
        except: clear_session()

# ============================================================
# 登录页
# ============================================================
def login_page():
    st.title("📚 PicaRead — 嗶咔漫画阅读器")
    tab1, tab2 = st.tabs(["账号登录", "Token 登录"])
    with tab1:
        email = st.text_input("邮箱/用户名")
        password = st.text_input("密码", type="password")
        remember = st.checkbox("记住登录", value=True)
        if st.button("登录", type="primary", use_container_width=True):
            if not email or not password:
                st.warning("请输入账号和密码"); return
            with st.spinner("登录中..."):
                try:
                    c = BikaClient()
                    r = c.login(email, password)
                    if r.get("code") == 200:
                        st.session_state.client = c
                        do_login(c.token, c.user.name, remember); st.rerun()
                    else: st.error(r.get("message", "登录失败"))
                except AuthError as e: st.error(str(e))
                except Exception as e: st.error(f"网络错误: {e}")
    with tab2:
        t = st.text_area("Token")
        if st.button("使用 Token", use_container_width=True):
            if t.strip():
                c = BikaClient(); c.set_token(t.strip())
                st.session_state.client = c
                do_login(t.strip(), c.user.name); st.rerun()

# ============================================================
# 侧边栏
# ============================================================
def sidebar():
    with st.sidebar:
        # 阅读器模式：由 reader_page 自行管理侧边栏
        if st.session_state.page == "reader":
            return

        st.markdown(f"### 📚 {st.session_state.user_name}")

        saved = load_session()
        if saved:
            since = saved.get("saved_at", "")[:10] if saved.get("saved_at") else ""
            st.caption(f"已记住登录 | {since}")

        st.divider()
        nav = st.radio("", ["🏠 分类浏览", "🔍 搜索", "📥 下载", "⚙️ 设置"],
                       index=["browse","search","downloads","settings"].index(st.session_state.page) if st.session_state.page in ["browse","search","downloads","settings"] else 0,
                       label_visibility="collapsed")
        st.session_state.page = {"🏠 分类浏览": "browse", "🔍 搜索": "search",
                                 "📥 下载": "downloads", "⚙️ 设置": "settings"}[nav]
        st.divider()
        if st.button("🚪 退出登录", use_container_width=True): do_logout()

# ============================================================
# 分类浏览
# ============================================================
def browse_page():
    client = get_client()
    if not client: return
    if st.session_state.selected_comic_id:
        detail_page(); return

    st.title("🏠 分类浏览")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        category = st.selectbox("分类", ["嗶咔漢化", "", "同人", "短篇", "長篇", "純愛", "全彩", "NTR", "妹妹系", "後宮閃光"])
    with c2:
        sort = st.selectbox("排序", ["dd", "ua", "ld", "vd"], format_func=lambda x: {"dd":"默认","ua":"最新","ld":"最多喜欢","vd":"最多浏览"}[x])
    with c3:
        page = st.number_input("页码", 1, 500, 1)

    with st.spinner("加载中..."):
        result = client.comics(category=category or None, sort=sort, page=page)
        d = result.get("data", {}).get("comics", {})
        total, total_pages, docs = d.get("total", 0), d.get("pages", 1), d.get("docs", [])

    st.caption(f"共 {total} 部 — 第 {page}/{total_pages} 页")

    cols = st.columns(5)
    for i, doc in enumerate(docs):
        comic = ComicInfo.from_api(doc)
        with cols[i % 5]:
            if comic.cover_url:
                try: st.image(comic.cover_url, use_container_width=True)
                except: pass
            st.markdown(f'<div class="comic-title">{comic.title[:40]}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="comic-sub">{comic.author} | ❤️{comic.total_likes}</div>', unsafe_allow_html=True)
            if st.button("📖 详情", key=f"det_{comic.id}", use_container_width=True):
                st.session_state.selected_comic_id = comic.id
                st.session_state.selected_comic_data = comic; st.rerun()

# ============================================================
# 搜索
# ============================================================
def search_page():
    client = get_client()
    if not client: return
    st.title("🔍 搜索")
    c1, c2 = st.columns([3, 1])
    with c1: kw = st.text_input("关键词", placeholder="漫画名称、作者...")
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        go = st.button("搜索", type="primary", use_container_width=True)

    if kw or go:
        with st.spinner("搜索中..."):
            result = client.search(keyword=kw, sort="mr", page=1)
            d = result.get("data", {}).get("comics", {})
            docs = d.get("docs", [])
        st.caption(f"找到 {d.get('total', 0)} 部")
        cols = st.columns(5)
        for i, doc in enumerate(docs[:50]):
            comic = ComicInfo.from_api(doc)
            with cols[i % 5]:
                if comic.cover_url:
                    try: st.image(comic.cover_url, use_container_width=True)
                    except: pass
                st.markdown(f'<div class="comic-title">{comic.title[:40]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="comic-sub">{comic.author}</div>', unsafe_allow_html=True)
                if st.button("📖 详情", key=f"sch_{comic.id}", use_container_width=True):
                    st.session_state.selected_comic_id = comic.id
                    st.session_state.selected_comic_data = comic; st.rerun()

# ============================================================
# 漫画详情
# ============================================================
def detail_page():
    client = get_client()
    comic = st.session_state.selected_comic_data
    if not client or not comic:
        st.session_state.selected_comic_id = None; st.rerun(); return

    if st.button("← 返回列表"):
        st.session_state.selected_comic_id = None
        st.session_state.selected_comic_data = None; st.rerun()

    st.title(comic.title)
    col1, col2 = st.columns([1, 3])
    with col1:
        if comic.cover_url:
            try: st.image(comic.cover_url, use_container_width=True)
            except: pass
    with col2:
        st.markdown(f"**作者:** {comic.author}")
        st.markdown(f"**分类:** {', '.join(comic.categories)}")
        if comic.tags: st.markdown(f"**标签:** {', '.join(comic.tags)}")
        st.markdown(f"**页数:** {comic.pages_count} | **章节:** {comic.eps_count} | {'已完结' if comic.finished else '连载中'}")
        st.markdown(f"**浏览:** {comic.total_views:,} | **喜欢:** {comic.total_likes:,}")

    st.divider()
    st.subheader("📖 章节")

    with st.spinner("加载章节..."):
        try: eps = client.episodes_iter(comic.id)
        except: eps = []

    if not eps:
        st.info("暂无章节"); return

    for ep in eps:
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1: st.markdown(f"**第{ep.order}话** — {ep.title}")
        with c2:
            if st.button("📖 阅读", key=f"rd_{comic.id}_{ep.order}", use_container_width=True):
                st.session_state.reader_comic_id = comic.id
                st.session_state.reader_ep_order = ep.order
                st.session_state.reader_ep_title = ep.title
                st.session_state.page = "reader"; st.rerun()
        with c3:
            if st.button("📥 下载", key=f"dl_{comic.id}_{ep.order}", use_container_width=True):
                download_episode(client, comic, ep)

# ============================================================
# 阅读器（图片在中央画布，控制在侧边栏）
# ============================================================
def reader_page():
    client = get_client()
    if not client: return

    comic_id = st.session_state.reader_comic_id
    ep_order = st.session_state.reader_ep_order
    ep_title = st.session_state.reader_ep_title

    if not comic_id:
        st.session_state.page = "browse"; st.rerun(); return

    # 获取章节列表
    try:
        eps = client.episodes_iter(comic_id)
    except:
        eps = []

    current_idx = next((i for i, e in enumerate(eps) if e.order == ep_order), -1)
    prev_ep = eps[current_idx - 1] if current_idx > 0 else None
    next_ep = eps[current_idx + 1] if current_idx >= 0 and current_idx < len(eps) - 1 else None

    # 加载页面
    with st.spinner("加载页面..."):
        all_pages = client.pages_iter(comic_id, ep_order)

    # ---- 侧边栏: 导航控制 ----
    with st.sidebar:
        st.markdown("### 📖 阅读器")

        if st.button("← 返回详情", use_container_width=True):
            st.session_state.page = "browse"
            st.session_state.reader_comic_id = None; st.rerun()

        st.divider()
        st.markdown(f"**第{ep_order}话**")
        st.caption(ep_title)
        st.caption(f"共 {len(all_pages)} 页 | 第 {current_idx + 1}/{len(eps)} 话")

        st.divider()

        if prev_ep:
            if st.button(f"◀ 第{prev_ep.order}话", key="sb_prev", use_container_width=True):
                st.session_state.reader_ep_order = prev_ep.order
                st.session_state.reader_ep_title = prev_ep.title; st.rerun()
        else:
            st.button("◀ 已是第一话", disabled=True, use_container_width=True)

        if next_ep:
            if st.button(f"第{next_ep.order}话 ▶", key="sb_next", use_container_width=True):
                st.session_state.reader_ep_order = next_ep.order
                st.session_state.reader_ep_title = next_ep.title; st.rerun()
        else:
            st.button("已是最后一话 ▶", disabled=True, use_container_width=True)

        st.divider()
        st.caption(f"第 {current_idx + 1} / {len(eps)} 话")

        if st.button("⬆ 回到顶部", use_container_width=True):
            st.markdown("<script>window.scrollTo(0,0)</script>", unsafe_allow_html=True)

        st.divider()
        # 跳页输入（加载下一页时用）
        page_count = max(1, (len(all_pages) + 19) // 20)
        st.caption(f"约 {page_count} 个分页请求")

        if st.button("📥 下载当前话", use_container_width=True):
            # 触发下载（使用详情页的下载逻辑）
            st.session_state._dl_comic_id = comic_id
            st.session_state._dl_ep_order = ep_order
            st.session_state._dl_ep_title = ep_title

    # ---- 主区域: 图片画布 ----
    st.markdown(f"### 第{ep_order}话 — {ep_title}")
    st.caption(f"共 {len(all_pages)} 页")

    if not all_pages:
        st.error("无法加载页面"); return

    # 图片居中显示，紧凑排列
    for i, page in enumerate(all_pages):
        if page.url:
            st.markdown(
                f'<div style="text-align:center; margin:0; padding:0; line-height:0;">'
                f'<img src="{page.url}" style="max-width:750px; width:100%; display:block; margin:0 auto;" alt="第{i+1}页">'
                f'</div>',
                unsafe_allow_html=True
            )

    st.divider()
    st.caption(f"— 第{ep_order}话 完 —")

    # 底部导航
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    with c1:
        if st.button("← 返回详情", key="bot_back"):
            st.session_state.page = "browse"
            st.session_state.reader_comic_id = None; st.rerun()
    with c2:
        if prev_ep:
            if st.button(f"◀ 第{prev_ep.order}话", key="bot_prev"):
                st.session_state.reader_ep_order = prev_ep.order
                st.session_state.reader_ep_title = prev_ep.title; st.rerun()
    with c3:
        if next_ep:
            if st.button(f"第{next_ep.order}话 ▶", key="bot_next"):
                st.session_state.reader_ep_order = next_ep.order
                st.session_state.reader_ep_title = next_ep.title; st.rerun()
    with c4:
        if st.button("⬆ 顶部", key="bot_top"):
            st.markdown("<script>window.scrollTo(0,0)</script>", unsafe_allow_html=True)

# ============================================================
# 下载 + PDF
# ============================================================
def download_episode(client, comic, ep):
    out = Path("downloads"); out.mkdir(exist_ok=True)
    pdf_path = out / f"{comic.id}_{ep.order}.pdf"
    title = comic.title[:30]

    bar = st.progress(0, text=f"下载: {title}")
    files, page_num = [], 1

    while True:
        result = client.pages(comic.id, ep.order, page=page_num)
        d = result.get("data", {}).get("pages", {})
        docs = d.get("docs", [])
        if not docs: break
        total = d.get("total", len(docs))
        for pg in docs:
            m = pg.get("media", {})
            url = f"{m.get('fileServer', '')}/static/{m.get('path', '')}" if m else ""
            try:
                resp = client._session.get(url, timeout=30)
                if resp.status_code == 200:
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                    tmp.write(resp.content); tmp.close(); files.append(tmp.name)
            except: pass
            bar.progress(min(len(files) / total, 1.0), text=f"下载: {title} ({len(files)}/{total})")
        if page_num >= d.get("pages", 1): break
        page_num += 1

    if not files:
        st.error("下载失败"); return

    try:
        with open(pdf_path, "wb") as f: f.write(img2pdf.convert(files))
        size = pdf_path.stat().st_size / 1024 / 1024
        for t in files:
            try: os.unlink(t)
            except: pass
        with open(pdf_path, "rb") as f:
            st.download_button(f"📥 下载 PDF ({size:.1f} MB)", f, file_name=pdf_path.name,
                               mime="application/pdf", key=f"dlbtn_{comic.id}_{ep.order}")
        st.success(f"完成! {len(files)} 页 → {size:.1f} MB")
    except Exception as e:
        st.error(f"PDF 生成失败: {e}")

# ============================================================
# 下载列表
# ============================================================
def downloads_page():
    st.title("📥 下载")
    out = Path("downloads")
    if out.exists():
        pdfs = sorted(out.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
        if pdfs:
            for pdf in pdfs:
                c1, c2, c3 = st.columns([3, 1, 1])
                with c1: st.markdown(f"**{pdf.name}** — {pdf.stat().st_size/1024/1024:.1f} MB")
                with c2:
                    with open(pdf, "rb") as f: st.download_button("📥", f, file_name=pdf.name, key=f"q_{pdf.name}")
                with c3:
                    if st.button("🗑️", key=f"del_{pdf.name}"): pdf.unlink(); st.rerun()
        else: st.info("暂无下载文件")
    else: st.info("暂无下载文件")

# ============================================================
# 设置
# ============================================================
def settings_page():
    st.title("⚙️ 设置")
    quality = st.select_slider("图片质量", ["low", "medium", "high", "original"], value="high")

    saved = load_session()
    st.markdown(f"**登录状态:** {'已记住' if saved else '未保存'}")
    if saved:
        st.caption(f"上次保存: {saved.get('saved_at', '')[:19]}")
        if st.button("清除登录缓存"):
            clear_session()
            st.success("已清除，下次打开需重新登录")
            st.rerun()

    if st.button("保存设置", type="primary"):
        if st.session_state.client: st.session_state.client._image_quality = quality
        st.success("已保存")

    st.divider()
    st.caption(f"PDF 目录: {Path('downloads').absolute()}")

# ============================================================
# 主入口
# ============================================================
def main():
    if not st.session_state.logged_in:
        login_page()
    else:
        sidebar()
        page = st.session_state.page
        if page == "browse": browse_page()
        elif page == "search": search_page()
        elif page == "reader": reader_page()
        elif page == "downloads": downloads_page()
        elif page == "settings": settings_page()

if __name__ == "__main__":
    main()
