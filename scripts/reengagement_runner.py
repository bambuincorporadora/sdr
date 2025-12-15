import asyncio
import os
import time

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
