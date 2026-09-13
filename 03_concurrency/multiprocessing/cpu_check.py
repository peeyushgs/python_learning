import ctypes
import os
import time

get_cpu = ctypes.windll.kernel32.GetCurrentProcessorNumber

print("PID:", os.getpid(), flush=True)

while True:
    end = time.perf_counter() + 1

    # Keep the CPU busy for one second
    while time.perf_counter() < end:
        pass

    print("Current logical CPU:", get_cpu(), flush=True)
