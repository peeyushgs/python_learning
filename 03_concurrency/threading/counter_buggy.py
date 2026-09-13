import threading
import time

COUNT = 1_000_000
THREADS = 8

counter = 0
def worker():
    global counter

    for _ in range(COUNT):
        counter += 1

threads = [
    threading.Thread(target=worker)
    for _ in range(THREADS)
]

start_time = time.time()

for t in threads:
    t.start()

for t in threads:
    t.join()

print("Time:", time.time() - start_time)
print("Counter:", counter)
print("Expected:", COUNT * THREADS)