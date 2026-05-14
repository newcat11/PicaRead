"""
PicaWeb API 使用示例

运行前请替换 YOUR_EMAIL 和 YOUR_PASSWORD 为你的账号信息。
"""

from bika_api import BikaClient, ComicInfo, EpisodeInfo, PageInfo, quick_login, AuthError


# ================================================================
# 方式一：匿名浏览（无需登录）
# ================================================================

def example_anonymous():
    """匿名搜索漫画"""
    with BikaClient() as client:
        result = client.search(keyword="", page=1)
        comics_data = result["data"]["comics"]
        print(f"共 {comics_data['total']} 部漫画")

        for doc in comics_data["docs"][:5]:
            comic = ComicInfo.from_api(doc)
            print(f"  [{comic.id}] {comic.title} — {comic.author}")

        # 按分类浏览
        result = client.comics(category="嗶咔漢化", page=1)
        print(f"\n嗶咔漢化 分类共: {result['data']['comics']['total']} 部")


# ================================================================
# 方式二：账号密码登录
# ================================================================

def example_login():
    """登录后使用完整功能"""
    client = BikaClient()

    result = client.login("YOUR_EMAIL", "YOUR_PASSWORD")
    if result.get("code") != 200:
        print(f"登录失败: {result.get('message')}")
        return

    print(f"登录成功! 用户: {client.user.name}")

    # 每日签到
    punch = client.punch_in()
    print(f"签到: {punch['data']['res']}")

    # 获取漫画列表
    result = client.comics(category="嗶咔漢化", page=1)
    docs = result["data"]["comics"]["docs"]
    if docs:
        first = ComicInfo.from_api(docs[0])
        print(f"\n第一部: {first.title} ({first.pages_count}页 / {first.eps_count}话)")

        # 获取章节
        eps = client.episodes(first.id)
        ep = eps["data"]["eps"]["docs"][0]
        print(f"第{ep['order']}话: {ep['title']}")

        # 获取页面
        pages = client.pages(first.id, ep["order"])
        pg_docs = pages["data"]["pages"]["docs"]
        print(f"共 {len(pg_docs)} 页")
        for pg in pg_docs[:3]:
            p = PageInfo.from_api(pg)
            print(f"  p{pg.get('index', 0)}: {p.url[:80]}...")

        # 收藏和点赞
        client.favourite_comic(first.id)
        client.like_comic(first.id)
        print("已收藏 + 点赞!")

    client.close()


# ================================================================
# 方式三：快捷登录函数
# ================================================================

def example_quick_login():
    """使用 quick_login 快捷登录"""
    try:
        client = quick_login("YOUR_EMAIL", "YOUR_PASSWORD")
        print(f"登录: {client.user.name}")

        # 迭代获取漫画
        comics = client.comics_iter(category="嗶咔漢化", max_pages=3)
        print(f"获取到 {len(comics)} 部漫画")
        for c in comics[:10]:
            print(f"  {c.title} — {c.author}")

        client.close()
    except AuthError as e:
        print(f"登录失败: {e}")


# ================================================================
# 方式四：使用已保存的 Token
# ================================================================

def example_with_token():
    """使用 token 跳过登录"""
    client = BikaClient()
    client.set_token("YOUR_JWT_TOKEN_HERE")

    print(f"用户: {client.user.name} ({client.user.email})")

    result = client.search(keyword="", page=1)
    print(f"漫画总量: {result['data']['comics']['total']}")

    client.close()


# ================================================================
# 方式五：使用代理
# ================================================================

def example_with_proxy():
    """通过代理访问"""
    with BikaClient(
        domain="picacomic.com",
        proxy="http://127.0.0.1:7890",
        image_quality="high",
    ) as client:
        result = client.search(keyword="", page=1)
        print(f"获取到 {result['data']['comics']['total']} 部漫画")


# ================================================================
# 方式六：批量下载生成 PDF
# ================================================================

def example_download_pdf():
    """下载漫画章节并生成 PDF"""
    import img2pdf, tempfile, os
    from pathlib import Path

    client = quick_login("YOUR_EMAIL", "YOUR_PASSWORD")

    # 获取第一部漫画
    result = client.comics(category="嗶咔漢化", page=1)
    first = ComicInfo.from_api(result["data"]["comics"]["docs"][0])

    # 获取第一章
    eps = client.episodes_iter(first.id)
    if not eps:
        print("无章节"); return
    ep = eps[0]

    # 下载所有页面
    files = []
    for pg in client.pages_iter(first.id, ep.order):
        if pg.url:
            resp = client.session.get(pg.url, timeout=30)
            if resp.status_code == 200:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                tmp.write(resp.content); tmp.close()
                files.append(tmp.name)

    print(f"已下载 {len(files)} 页")

    # 生成 PDF
    Path("downloads").mkdir(exist_ok=True)
    pdf_path = f"downloads/{first.title[:20]}_第{ep.order}话.pdf"
    with open(pdf_path, "wb") as f:
        f.write(img2pdf.convert(files))
    print(f"PDF: {pdf_path} ({os.path.getsize(pdf_path)/1024/1024:.1f} MB)")

    for t in files: os.unlink(t)
    client.close()


if __name__ == "__main__":
    example_anonymous()
