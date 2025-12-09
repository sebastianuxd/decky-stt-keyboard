import asyncio

class Plugin:
    @staticmethod
    async def _ensure_dependencies(self):
        print("Inside _ensure_dependencies")

    async def _main(self):
        print("Calling _ensure_dependencies")
        await self._ensure_dependencies()

async def run():
    p = Plugin()
    try:
        await p._main()
    except TypeError as e:
        print(f"Caught expected error: {e}")

if __name__ == "__main__":
    asyncio.run(run())