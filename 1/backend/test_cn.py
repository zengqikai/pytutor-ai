import asyncio, httpx
async def t():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("http://localhost:8000/api/v1/auth/login", json={"email":"tt@t.com","password":"test12345"})
        token = r.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}
        r = await c.post("http://localhost:8000/api/v1/code/submit", json={"code":"print(chr(38472)+chr(20048)+chr(22825)+chr(29233)+chr(23398)+chr(20064))"}, headers=h)
        d = r.json()
        s = d["result"]["stdout"]
        target = chr(38472)
        print("OK" if target in s else "CORRUPTED")
asyncio.run(t())
