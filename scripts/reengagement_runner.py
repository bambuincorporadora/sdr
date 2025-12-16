import asyncio
import sys
from pathlib import Path

# garante que o pacote backend/app esteja no PYTHONPATH quando rodado fora do uvicorn
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.jobs.reengagement import run_reengagement


async def main() -> None:
    while True:
        try:
            await run_reengagement()
        except Exception as exc:  # pragma: no cover
            print(f"[reengagement] erro: {exc}")
        await asyncio.sleep(300)  # 5 minutos


if __name__ == "__main__":
    asyncio.run(main())
