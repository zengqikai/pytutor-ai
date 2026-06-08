"""
密码哈希模块
============

负责密码的安全存储和验证。

直接使用 bcrypt 库（而非 passlib），因为 passlib 1.7.4 不兼容 bcrypt 5.x。

为什么不能用明文存储密码？
- 数据库泄露后，攻击者可以直接看到所有用户的密码
- 用户通常会在多个网站使用相同密码，一个泄露会导致连锁反应

bcrypt 算法的工作原理：
1. 自动生成随机盐（salt），混入密码中
2. 进行多轮哈希计算（默认 12 轮，每轮翻倍计算量）
3. 输出包含算法标识、盐值和哈希结果的字符串

bcrypt 的密码限制：
- 最大 72 字节（不是字符数！UTF-8 编码的中文字符占 3 字节）
- 如果密码可能超过 72 字节，需要先做一次 SHA256 预哈希
"""

import bcrypt


def hash_password(password: str) -> str:
    """
    将明文密码哈希化。

    参数:
        password: 用户输入的明文密码

    返回:
        str: bcrypt 哈希后的字符串（可直接存入数据库）

    用法:
        hashed = hash_password("my_password123")
        user.password_hash = hashed
    """
    # 将密码转为 bytes（UTF-8 编码）
    password_bytes = password.encode("utf-8")

    # bcrypt 限制密码最大 72 字节
    # 如果超过 72 字节，先做 SHA256 预哈希（罕见情况，但安全起见处理一下）
    if len(password_bytes) > 72:
        import hashlib
        password_bytes = hashlib.sha256(password_bytes).digest()

    # 生成盐并哈希
    # gensalt() 默认使用 12 轮计算（2^12 = 4096 次迭代）
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)

    # 返回字符串形式（方便存数据库）
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码是否匹配。

    参数:
        plain_password: 用户输入的明文密码
        hashed_password: 数据库中存储的哈希密码

    返回:
        bool: True 表示密码正确，False 表示密码错误

    用法:
        if verify_password("输入的密码", user.password_hash):
            # 密码正确，允许登录
        else:
            # 密码错误
    """
    password_bytes = plain_password.encode("utf-8")

    # 同样处理超过 72 字节的情况
    if len(password_bytes) > 72:
        import hashlib
        password_bytes = hashlib.sha256(password_bytes).digest()

    hashed_bytes = hashed_password.encode("utf-8")

    return bcrypt.checkpw(password_bytes, hashed_bytes)
