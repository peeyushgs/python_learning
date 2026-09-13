import threading
import time

THREADS = 8


def fib(n: int) -> int:
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)


def main():
    start_time = time.time()

    threads = []

    # create and start 8 threads for a CPU bound task
    for i in range(THREADS):
        thread = threading.Thread(target=fib, args=(35,))
        thread.start()
        threads.append(thread)

    # wait for all threads to complete
    for thread in threads:
        thread.join()

    print(f"Completed: {time.time() - start_time:.2f} seconds")


if __name__ == "__main__":
    main()
