
import asyncio, httpx
async def t():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("http://localhost:8000/api/v1/auth/login", json={"email":"tt@t.com","password":"test12345"})
        h = {"Authorization": f"Bearer {r.json()["access_token"]}"}
        r = await c.post("http://localhost:8000/api/v1/code/submit", json={"code":"print(chr(20320)+chr(22909))"}, headers=h)
        txt = r.text
        # chr(20320)=你, chr(22909)=好
        if "\u4f60" in txt:
            print("ESCAPED: JSON uses unicode escapes")
        elif chr(20320) in txt:
            print("OK: Raw UTF-8 in JSON")
        else:
            print("RAW:", txt[:200].encode("utf-8", errors="replace"))
asyncio.run(t())

