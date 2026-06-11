
import asyncio, httpx
async def t():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("http://localhost:8000/api/v1/auth/login", json={"email":"tt@t.com","password":"test12345"})
        h = {"Authorization": f"Bearer {r.json()["access_token"]}"}
        r = await c.post("http://localhost:8000/api/v1/code/submit", json={"code":"print(\"你好\")"}, headers=h)
        txt = r.text
        if "你好" in txt:
            print("OK: Raw UTF-8 in JSON response")
        elif "\u4f60" in txt:
            print("STILL: unicode escapes in JSON")
        else:
            print("OTHER:", txt[:200].encode("utf-8", errors="replace"))
asyncio.run(t())

