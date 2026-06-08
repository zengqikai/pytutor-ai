
import asyncio, httpx
async def t():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("http://localhost:8000/api/v1/auth/login", json={"email":"tt@t.com","password":"test12345"})
        h = {"Authorization": f"Bearer {r.json()[\"access_token\"]}"}
        r = await c.post("http://localhost:8000/api/v1/code/submit", json={"code":"print(\"你好世界\")"}, headers=h)
        d = r.json()
        s = d["result"]["stdout"]
        ok = "你好" in s
        print("OK" if ok else f"FAIL: {s.encode(\"utf-8\",errors=\"replace\")[:50]}")
asyncio.run(t())

