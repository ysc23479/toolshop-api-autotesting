# utils/totp_util.py
import base64
import hashlib
import hmac
import struct
import time


def totp_now(secret: str, period: int = 30, digits: int = 6) -> str:
    """根据 base32 secret 计算当前 TOTP 验证码（RFC 6238 标准实现）。

    标准 TOTP 流程：
      1. secret 是 base32 编码的字符串，需补齐 padding 再解码
      2. counter = 当前时间戳 // period
      3. HMAC-SHA1(secret, counter 8字节大端) 
      4. 动态截断（RFC 4226 §5.3）取 31 位
      5. 取后 6 位即验证码

    不依赖 pyotp，避免新增依赖。
    """
    # 补齐 base32 padding（长度必须是 8 的倍数）
    padded = secret.upper() + "=" * ((8 - len(secret) % 8) % 8)
    secret_bytes = base64.b32decode(padded)

    counter = int(time.time()) // period
    msg = struct.pack(">Q", counter)
    h = hmac.new(secret_bytes, msg, hashlib.sha1).digest()

    offset = h[-1] & 0x0F
    code = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)