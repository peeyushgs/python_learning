import asyncio
import threading


async def worker(name, delay):
    thread = threading.current_thread()
    task = asyncio.current_task()

    print(
        f"{name} starting | "
        f"task={task.get_name()} | "
        f"thread={thread.name} | "
        f"thread_id={thread.ident} | "
        f"native_id={thread.native_id}"
    )
    await asyncio.sleep(delay)

    thread = threading.current_thread()
    print(
        f"{name} finished after {delay} seconds | "
        f"thread={thread.name} | "
        f"thread_id={thread.ident} | "
        f"native_id={thread.native_id}"
    )

async def main():
    task1 = asyncio.create_task(worker("Worker 1", 1), name="task-1")
    task2 = asyncio.create_task(worker("Worker 2", 1), name="task-2")
    task3 = asyncio.create_task(worker("Worker 3", 1), name="task-3")

    await task1
    await task2
    await task3

asyncio.run(main())
