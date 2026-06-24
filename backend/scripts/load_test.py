import asyncio
import time
import httpx
import sys
import os

# Target API URL (default to local dev server)
BASE_URL = os.getenv("TARGET_URL", "http://localhost:8000")

async def worker(session: httpx.AsyncClient, duration: float, results: list):
    start_time = time.time()
    end_time = start_time + duration
    
    while time.time() < end_time:
        req_start = time.perf_counter()
        try:
            resp = await session.get(f"{BASE_URL}/health")
            latency = time.perf_counter() - req_start
            results.append({
                "status": resp.status_code,
                "latency": latency,
                "success": resp.status_code == 200
            })
        except Exception as e:
            latency = time.perf_counter() - req_start
            results.append({
                "status": 0,
                "latency": latency,
                "success": False,
                "error": str(e)
            })
        # Micro-sleep to prevent completely blocking the event loop
        await asyncio.sleep(0.01)

async def main():
    concurrency = int(os.getenv("LOAD_CONCURRENCY", "10"))
    duration = float(os.getenv("LOAD_DURATION", "5.0"))
    
    print(f"Starting load test on {BASE_URL}")
    print(f"Concurrency: {concurrency} workers, Duration: {duration} seconds...")
    
    results = []
    start_time = time.perf_counter()
    
    async with httpx.AsyncClient(timeout=5.0) as session:
        tasks = [worker(session, duration, results) for _ in range(concurrency)]
        await asyncio.gather(*tasks)
        
    total_time = time.perf_counter() - start_time
    total_requests = len(results)
    
    if total_requests == 0:
        print("No requests completed.")
        return
        
    successes = sum(1 for r in results if r["success"])
    failures = total_requests - successes
    latencies = [r["latency"] for r in results]
    
    avg_latency = (sum(latencies) / total_requests) * 1000
    min_latency = min(latencies) * 1000
    max_latency = max(latencies) * 1000
    rps = total_requests / total_time
    
    print("\n================ LOAD TEST RESULTS ================")
    print(f"Total Time:         {total_time:.2f} seconds")
    print(f"Total Requests:     {total_requests}")
    print(f"Successful:         {successes} ({(successes/total_requests)*100:.1f}%)")
    print(f"Failed:             {failures}")
    print(f"RPS (Throughput):   {rps:.2f} req/sec")
    print(f"Min Latency:        {min_latency:.2f} ms")
    print(f"Max Latency:        {max_latency:.2f} ms")
    print(f"Avg Latency:        {avg_latency:.2f} ms")
    print("===================================================\n")

if __name__ == "__main__":
    asyncio.run(main())
