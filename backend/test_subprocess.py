import re, asyncio, sys, os, tempfile
from pathlib import Path

async def t():
    code = "print(chr(38472)+chr(20048)+chr(22825)+chr(29233)+chr(23398)+chr(20064))"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        tmp = Path(f.name)
    env = {}
    for k,v in os.environ.items():
        try: env[k] = v
        except: env[k] = ""
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    proc = await asyncio.create_subprocess_exec(sys.executable, "-X", "utf8", str(tmp), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env)
    out, err = await proc.communicate()
    s = out.decode("utf-8", errors="replace").rstrip()
    print("OK" if chr(38472) in s else "CORRUPTED hex="+out.hex()[:40])
    tmp.unlink()
asyncio.run(t())
