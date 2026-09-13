import time
from concurrent.futures import ThreadPoolExecutor

COUNT = 1_000_000
THREADS = 8


def worker():
    local_counter = 0

    for _ in range(COUNT):
        local_counter += 1
    return local_counter


start_time = time.time()

with ThreadPoolExecutor(max_workers=THREADS) as executor:
    results = list(executor.map(lambda _: worker(), range(THREADS)))

print(results)

counter = sum(results)

print("Time", time.time() - start_time)
print("Counter:", counter)
print("Expected:", COUNT * THREADS)
