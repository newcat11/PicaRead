# -*- coding: utf-8 -*-
"""
PicaWeb API 客户端 — 公共接口。
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

from curl_cffi import requests

from bika_crypto import build_headers, parse_jwt

DEFAULT_DOMAIN = "go2778.com"


# ============================================================
# 数据模型
# ============================================================

@dataclass
class ComicInfo:
    id: str = ""
    title: str = ""
    author: str = ""
    description: str = ""
    cover_url: str = ""
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    pages_count: int = 0
    eps_count: int = 0
    finished: bool = False
    total_views: int = 0
    total_likes: int = 0
    updated_at: str = ""
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict) -> "ComicInfo":
        comic = data.get("comic") or data
        thumb = comic.get("thumb", {})
        cover = f"{thumb.get('fileServer', '')}/static/{thumb.get('path', '')}" if thumb else ""
        return cls(
            id=data.get("_id", comic.get("_id", "")),
            title=comic.get("title", ""),
            author=comic.get("author", ""),
            description=comic.get("description", ""),
            cover_url=cover,
            categories=comic.get("categories", []),
            tags=comic.get("tags", []),
            pages_count=comic.get("pagesCount", 0),
            eps_count=comic.get("epsCount", 0),
            finished=comic.get("finished", False),
            total_views=comic.get("totalViews", 0),
            total_likes=comic.get("totalLikes", 0),
            updated_at=comic.get("updated_at", ""),
            raw=data,
        )


@dataclass
class EpisodeInfo:
    id: str = ""
    title: str = ""
    order: int = 0
    updated_at: str = ""
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict) -> "EpisodeInfo":
        return cls(
            id=data.get("_id", ""), title=data.get("title", ""),
            order=data.get("order", 0), updated_at=data.get("updated_at", ""), raw=data,
        )


@dataclass
class PageInfo:
    url: str = ""
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict) -> "PageInfo":
        m = data.get("media", {})
        return cls(
            url=f"{m.get('fileServer', '')}/static/{m.get('path', '')}" if m else "",
            raw=data,
        )


@dataclass
class UserInfo:
    id: str = ""
    name: str = ""
    email: str = ""
    role: str = ""
    raw: dict = field(default_factory=dict)


# ============================================================
# 客户端
# ============================================================

class BikaClient:
    def __init__(self, domain: str | None = None, proxy: str | None = None,
                 image_quality: str = "medium", timeout: float = 30.0,
                 impersonate: str = "chrome120"):
        self._domain = domain or os.environ.get("BIKA_DOMAIN", DEFAULT_DOMAIN)
        self._image_quality = image_quality
        self._token: str | None = None
        self._user: UserInfo | None = None
        self._base = f"https://picaapi.{self._domain}"
        self._timeout = timeout
        self._impersonate = impersonate

        self._session = requests.Session()
        if proxy:
            self._session.proxies = {"http": proxy, "https": proxy}

    # ---- 内部 ----

    _FALLBACK_DOMAINS = ["go2778.com", "picacomic.com", "acbbb.com"]

    def _req(self, path: str, method: str = "GET",
             params: dict | None = None, body: dict | None = None) -> dict:
        if params:
            qs = urlencode(params, doseq=True)
            sign_path = f"{path}?{qs}"
            url_path = f"{path}?{qs}"
        else:
            sign_path = path
            url_path = path

        last_error = None
        domains = [self._domain] + [d for d in self._FALLBACK_DOMAINS if d != self._domain]

        for attempt in range(3):
            for domain in domains:
                try:
                    base = f"https://picaapi.{domain}"
                    url = f"{base}/{url_path}"
                    headers = build_headers(sign_path, method, self._token, self._image_quality)
                    resp = self._session.request(method=method, url=url, headers=headers, json=body,
                                                 timeout=self._timeout, impersonate=self._impersonate)
                    data = resp.json()
                    if data.get("code") == 401:
                        raise AuthError(data.get("message", "登录已过期"))
                    return data
                except AuthError:
                    raise
                except Exception as e:
                    last_error = e
                    continue  # try next domain

            # All domains failed, wait and retry
            if attempt < 2:
                time.sleep((attempt + 1) * 2)

        raise ConnectionError(f"API 不可达 (已尝试 {len(domains)} 个域名, 3 次重试): {last_error}")

    def _get(self, path: str, params: dict | None = None) -> dict:
        return self._req(path, "GET", params=params)

    def _post(self, path: str, body: dict | None = None, params: dict | None = None) -> dict:
        return self._req(path, "POST", params=params, body=body)

    # ---- 认证 ----

    def login(self, email: str, password: str) -> dict:
        result = self._post("auth/sign-in", body={"email": email, "password": password})
        if result.get("code") == 200 and (t := result.get("data", {}).get("token")):
            self._token = t
            jwt = parse_jwt(t)
            self._user = UserInfo(id=jwt.get("_id", ""), name=jwt.get("name", ""),
                                  email=jwt.get("email", ""), role=jwt.get("role", ""), raw=jwt)
        return result

    def set_token(self, token: str) -> None:
        self._token = token
        jwt = parse_jwt(token)
        self._user = UserInfo(id=jwt.get("_id", ""), name=jwt.get("name", ""),
                              email=jwt.get("email", ""), role=jwt.get("role", ""), raw=jwt)

    @property
    def token(self) -> str | None: return self._token
    @property
    def user(self) -> UserInfo | None: return self._user
    @property
    def is_logged_in(self) -> bool: return self._token is not None
    @property
    def session(self): return self._session

    # ---- 漫画 ----

    def comics(self, category: str | None = None, tag: str | None = None,
               author: str | None = None, sort: str = "dd", page: int = 1) -> dict:
        params: dict[str, Any] = {"page": str(page), "s": sort}
        if category: params["c"] = category
        if tag:      params["t"] = tag
        if author:   params["a"] = author
        return self._get("comics", params=params)

    def search(self, keyword: str = "", category: str = "", sort: str = "mr",
               page: int = 1) -> dict:
        body: dict[str, Any] = {"keyword": keyword, "sort": sort}
        if category: body["category"] = category
        return self._post("comics/advanced-search", body=body, params={"page": str(page)})

    def episodes(self, comic_id: str, page: int = 1) -> dict:
        return self._get(f"comics/{comic_id}/eps", params={"page": str(page)})

    def pages(self, comic_id: str, order: int, page: int = 1) -> dict:
        return self._get(f"comics/{comic_id}/order/{order}/pages", params={"page": str(page)})

    def random_comic(self) -> dict:
        return self._get("comics/random")

    # ---- 迭代器 ----

    def search_iter(self, keyword: str = "", sort: str = "mr",
                    max_pages: int = 50) -> list[ComicInfo]:
        results = []
        for p in range(1, max_pages + 1):
            data = self.search(keyword=keyword, sort=sort, page=p)
            d = data.get("data", {}).get("comics", {})
            docs = d.get("docs", [])
            if not docs: break
            results.extend(ComicInfo.from_api(x) for x in docs)
            if p >= d.get("pages", 1): break
        return results

    def comics_iter(self, category: str = "", sort: str = "dd",
                    max_pages: int = 50) -> list[ComicInfo]:
        results = []
        for p in range(1, max_pages + 1):
            data = self.comics(category=category or None, sort=sort, page=p)
            d = data.get("data", {}).get("comics", {})
            docs = d.get("docs", [])
            if not docs: break
            results.extend(ComicInfo.from_api(x) for x in docs)
            if p >= d.get("pages", 1): break
        return results

    def episodes_iter(self, comic_id: str) -> list[EpisodeInfo]:
        results = []
        for p in range(1, 100):
            data = self.episodes(comic_id, page=p)
            d = data.get("data", {}).get("eps", {})
            docs = d.get("docs", [])
            if not docs: break
            results.extend(EpisodeInfo.from_api(x) for x in docs)
            if p >= d.get("pages", 1): break
        return results

    def pages_iter(self, comic_id: str, order: int) -> list[PageInfo]:
        results = []
        for p in range(1, 100):
            data = self.pages(comic_id, order, page=p)
            d = data.get("data", {}).get("pages", {})
            docs = d.get("docs", [])
            if not docs: break
            results.extend(PageInfo.from_api(x) for x in docs)
            if p >= d.get("pages", 1): break
        return results

    # ---- 排行榜 / 分类 / 标签 ----

    def leaderboard(self, timeframe: str = "H24", category: str = "VC", page: int = 1) -> dict:
        return self._get(f"comics/leaderboard/{timeframe}/{category}", params={"page": str(page)})

    def categories(self) -> dict:
        return self._get("categories")

    def keywords(self) -> dict:
        return self._get("keywords")

    # ---- 互动 ----

    def like_comic(self, comic_id: str) -> dict:
        return self._post(f"comics/{comic_id}/like")

    def favourite_comic(self, comic_id: str) -> dict:
        return self._post(f"comics/{comic_id}/favourite")

    def comments(self, comic_id: str, page: int = 1) -> dict:
        return self._get(f"comics/{comic_id}/comments", params={"page": str(page)})

    # ---- 用户 ----

    def profile(self) -> dict:
        return self._get("users/profile")

    def punch_in(self) -> dict:
        return self._post("users/punch-in")

    def my_favourites(self, page: int = 1) -> dict:
        return self._get("users/favourite", params={"page": str(page)})

    def my_comments(self, page: int = 1) -> dict:
        return self._get("users/my-comments", params={"page": str(page)})

    # ---- 其他 ----

    def games(self, page: int = 1) -> dict:
        return self._get("games", params={"page": str(page)})

    def announcements(self, page: int = 1) -> dict:
        return self._get("announcements", params={"page": str(page)})

    def close(self) -> None:
        self._session.close()

    def __enter__(self): return self
    def __exit__(self, *args): self.close()


class AuthError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


# ---- 快捷函数 ----

def quick_login(email: str, password: str, domain: str = DEFAULT_DOMAIN) -> BikaClient:
    client = BikaClient(domain=domain)
    result = client.login(email, password)
    if result.get("code") != 200:
        raise AuthError(result.get("message", "登录失败"))
    return client
