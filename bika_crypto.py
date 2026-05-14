# -*- coding: utf-8 -*-
"""
内部模块 — 签名算法和密钥管理。
不直接暴露给用户。
"""
import base64
import hashlib
import hmac
import secrets
import time


# ============================================================
# 解密工具
# ============================================================

def _ge(data: str, key: str) -> str:
    n = len(data)
    indices = list(range(n))
    seed = sum(ord(c) for c in key)
    for r in range(n - 1, 0, -1):
        seed = (9301 * seed + 49297) % 233280
        e = seed % (r + 1)
        indices[r], indices[e] = indices[e], indices[r]
    result = [''] * n
    for i in range(n):
        result[i] = data[indices[i]]
    return ''.join(result)


def _pe(encoded: str) -> str:
    try:
        a = base64.b64decode(encoded).decode('latin-1')
        a = _ge(a, "PicaWeb2025")
        o = ''.join(chr(ord(c) ^ 42) for c in a)
        return base64.b64decode(o).decode('utf-8')
    except Exception:
        return ""


# 预解密密钥
_KEY_A = _pe("b397e2wXZHtgb2RvUBh7bnB+bnt8bEEfZ2xSQUFtY0F4G3h4bWhzeA==")
_KEY_B = _pe("aGh+G0dwfHpGUGRmYGxrGUFsZmRyGUMZa19kfUxfRxMfXGAaGxNBbmBhZRpMQUFma20Bbn58YElIYGQTbGdsQkxrfEd8X3xueBocH1JQf2RpSG9B")

# ============================================================
# 公共接口
# ============================================================

def generate_nonce() -> str:
    return secrets.token_hex(16)


def build_signature(path: str, timestamp: str, nonce: str, method: str = "GET") -> str:
    sign_string = (path + timestamp + nonce + method + _KEY_A).lower()
    return hmac.new(_KEY_B.encode('utf-8'), sign_string.encode('utf-8'), hashlib.sha256).hexdigest()


def build_headers(path: str, method: str, token: str | None, image_quality: str) -> dict:
    ts = str(int(time.time()))
    nonce = generate_nonce()
    sig = build_signature(path, ts, nonce, method)
    h = {
        "app-channel": "1",
        "app-uuid": "webUUIDv2",
        "app-version": "20251017",
        "accept": "application/vnd.picacomic.com.v1+json",
        "app-platform": "android",
        "Content-Type": "application/json; charset=UTF-8",
        "time": ts,
        "nonce": nonce,
        "image-quality": image_quality,
        "signature": sig,
    }
    if token:
        h["authorization"] = token
    return h


def parse_jwt(token: str) -> dict:
    import json
    try:
        payload = token.split(".")[1]
        payload += "=" * (4 - len(payload) % 4)
        return json.loads(base64.b64decode(payload))
    except Exception:
        return {}
