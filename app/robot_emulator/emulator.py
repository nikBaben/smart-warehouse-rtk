import os, random, asyncio
from datetime import datetime, timezone
import aiohttp

PRODUCTS = [
    {"id":"TEL-4567","name":"Роутер RT-AC68U"},
    {"id":"TEL-8901","name":"Модем DSL-2640U"},
    {"id":"TEL-2345","name":"Коммутатор SG-108"},
    {"id":"TEL-6789","name":"IP-телефон T46S"},
    {"id":"TEL-3456","name":"Кабель UTP Cat6"},
]

class Robot:
    def __init__(self, robot_id, api_url):
        self.id = robot_id
        self.url = api_url.rstrip("/")
        self.battery = 100.0
        self.zone, self.row, self.shelf = "A", 1, 1

    def scan(self):
        k = random.randint(1, 3)
        selected = random.sample(PRODUCTS, k=k)
        results = []
        for p in selected:
            q = random.randint(5, 100)
            status = "OK" if q>20 else ("LOW_STOCK" if q>10 else "CRITICAL")
            results.append({"product_id":p["id"], "product_name":p["name"], "quantity":q, "status":status})
        return results

    def move(self):
        self.shelf += 1
        if self.shelf > 10:
            self.shelf = 1
            self.row += 1
            if self.row > 20:
                self.row = 1
                self.zone = chr(ord(self.zone) + 1) if self.zone < "E" else "A"
        self.battery -= random.uniform(0.1, 0.5)
        if self.battery < 15:
            self.battery = 100.0 

    async def tick(self, session: aiohttp.ClientSession):
        payload = {
            "robot_id": self.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": {"zone": self.zone, "row": self.row, "shelf": self.shelf},
            "scan_results": self.scan(),
            "battery_level": round(self.battery, 1),
            "next_checkpoint": f"{self.zone}-{self.row+1}-{self.shelf}",
        }
        async with session.post(
            f"{self.url}/api/robots/data",
            json=payload,
            headers={"Authorization": f"Bearer robot_token_{self.id}"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            txt = await r.text()
            print(self.id, r.status, txt[:100])

    async def run(self, interval: float):
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    await self.tick(session)
                    self.move()
                except Exception as e:
                    print(self.id, "err", e)
                await asyncio.sleep(interval)

async def main():
    api = os.getenv("API_URL", "http://localhost:8000")
    count = int(os.getenv("ROBOTS_COUNT", 5))
    interval = float(os.getenv("UPDATE_INTERVAL", 2))
    tasks = [asyncio.create_task(Robot(f"RB-{i:03d}", api).run(interval)) for i in range(1, count+1)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
