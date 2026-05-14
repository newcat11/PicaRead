# PicaRead — 嗶咔漫画阅读器

基于 [PicaWeb](https://alpha.bikawebapp.com)（哔咔漫画网页版）API 的第三方漫画客户端，支持分类浏览、搜索、在线阅读和 PDF 下载。

## 功能

| 功能 | 说明 |
|------|------|
| 📖 在线浏览 | 分类浏览漫画，网格展示封面和基本信息 |
| 🔍 搜索 | 关键词搜索漫画 |
| 📚 在线阅读 | 全页图片自上而下流畅阅读，侧边栏快速切换章节 |
| 📥 PDF 下载 | 一键下载章节图片，自动打包生成 PDF 文件 |
| 🔐 登录持久化 | 记住登录状态，关闭浏览器后再次打开无需重新登录 |

## 使用方式

### 方式一：一键启动（推荐）

**仅首次需要运行 `setup_and_run.bat`**，之后可直接运行 `启动阅读器.bat`。

1. 双击 `setup_and_run.bat`
2. 等待自动安装依赖（约 1-3 分钟，仅首次）
3. 浏览器自动打开，开始使用

> **注意**：需要先安装 Python 3.10+，安装时勾选「Add Python to PATH」。
> 下载地址：https://www.python.org/downloads/

### 方式二：命令行启动

```bash
# 1. 创建虚拟环境（仅首次）
python -m venv venv

# 2. 激活并安装依赖（仅首次）
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt

# 3. 启动
streamlit run bika_gui.py
```

浏览器打开 [http://localhost:8501](http://localhost:8501)

### 方式三：Python API 调用

```python
from bika_api import quick_login, ComicInfo

# 登录
client = quick_login("your_email", "your_password")
print(f"欢迎, {client.user.name}")

# 浏览漫画
result = client.comics(category="嗶咔漢化", page=1)
for doc in result["data"]["comics"]["docs"]:
    comic = ComicInfo.from_api(doc)
    print(f"{comic.title} — {comic.author}")

# 下载并生成 PDF
import img2pdf, tempfile, os
files = []
for p in client.pages_iter("comic_id", order=1):
    if p.url:
        resp = client.session.get(p.url, timeout=30)
        if resp.status_code == 200:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            tmp.write(resp.content); tmp.close()
            files.append(tmp.name)
with open("output.pdf", "wb") as f:
    f.write(img2pdf.convert(files))
for t in files: os.unlink(t)
```

更多 API 示例见 [examples.py](examples.py)。

## 常见问题

**Q: 提示「未检测到 Python」？**
A: 需要先安装 Python 3.10+，下载 https://www.python.org/downloads/ ，安装时务必勾选「Add Python to PATH」。

**Q: 打开后一直加载或报网络错误？**
A: 需要 VPN 才能访问 PicaWeb API 服务器。请开启 VPN 后重试。

**Q: 如何注册账号？**
A: 打开 https://alpha.bikawebapp.com 注册。

**Q: 下载的 PDF 保存在哪里？**
A: 保存在程序目录下的 `downloads/` 文件夹中。

## 依赖

- Python 3.10+
- `curl_cffi` — 网络请求
- `streamlit` — 可视化界面
- `img2pdf` — PDF 生成

## 免责声明

本项目仅用于学习和研究目的。用户应遵守相关服务条款，不得将本项目用于任何违法用途。使用者需自行承担所有风险。

## License

MIT
