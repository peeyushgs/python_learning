# Python Concurrency: A Guided Learning Path

These notes assume you already understand normal sequential Python but are new
to threads, processes, and `asyncio`. Read the lessons in order. Each lesson
introduces one problem, one new tool, and the syntax needed to use it.

The examples follow the learning sequence used by the
[Geekuni concurrency article](https://blog.geekuni.com/2026/04/python-concurrency.html),
with corrections and clarifications from the official Python documentation.

## Why learn concurrency?

Most small programs are easiest to write sequentially. Concurrency becomes
useful when a program has independent work that otherwise leaves resources idle
or fails to use available CPU capacity. Common examples include:

- downloading files, scraping websites, and calling REST APIs;
- querying databases or reading and writing many files;
- parsing and cleaning independent ETL partitions;
- hashing many independent files;
- running simulations or CPU-heavy transformations; and
- serving several users or requests during the same time period.

Concurrency is not automatically an improvement. It introduces scheduling,
coordination, failure handling, and measurement costs. Begin with correct
sequential code, identify independent work, and introduce concurrency only when
the expected benefit justifies that complexity.

## Essential definitions

**Sequential execution:** One task runs and finishes before the next task
begins.

**Concurrency:** Multiple tasks make progress during the same period. They may
take turns and do not have to execute at exactly the same instant. Concurrency
can be implemented with asyncio tasks, threads, or processes; it is not limited
to one process.

**Event loop:** A scheduler that waits for events such as completed I/O and
timers, runs tasks that are ready, and repeats. In normal `asyncio` usage, one
event-loop thread switches cooperatively between tasks at `await` points.

**Parallelism:** Multiple operations execute at the same instant, usually on
different CPU cores. Multiprocessing and free-threaded multithreading are two
ways to obtain CPU parallelism; parallelism is not another name for
multiprocessing.

**Multiprocessing:** A program uses multiple processes. Each process has its
own Python interpreter and normally has a separate memory space.

**Multithreading:** One process contains multiple threads of execution. The
threads share the process's objects and resources, but each function call still
has its own local variables and call stack. Threads may provide concurrency
without parallelism; with a GIL-enabled CPython interpreter, pure-Python CPU
threads normally take turns executing bytecode.

**Thread safety:** Code is thread-safe when multiple threads can use it without
breaking its rules or producing corrupted application results. Shared mutable
state commonly needs a lock, a thread-safe queue, or a redesign using
per-worker local data. The GIL does not automatically make application code
thread-safe.

### One-chef mental model

```text
Sequential:
one chef finishes dish A, then begins dish B

Concurrent:
one chef starts soup, works on salad while soup boils,
then returns to the soup when the timer fires

Parallel:
two chefs actively prepare two dishes at the same instant

Multithreading:
several workers operate inside one shared kitchen/process
and therefore share its ingredients/resources/memory
```

An event loop resembles the coordinator used by the one concurrent chef: it
tracks timers and I/O readiness, runs a ready task, and switches when that task
waits. It schedules async tasks—not background OS threads by default.

## Current project environment

The project accepts Python 3.12 or newer, but `.python-version` currently selects
the Python 3.14 free-threaded build:

```text
3.14t
```

Check the interpreter that actually runs a command:

```powershell
python -VV
python -c "import sys; print('GIL enabled:', getattr(sys, '_is_gil_enabled', lambda: True)())"
```

The current virtual environment reports Python 3.14 free-threaded with the GIL
disabled. Always verify this because an old virtual environment can remain after
`.python-version` changes.

Unless a command says otherwise, run repository examples from the repository
root (`python_learning`).

## Learning sequence

1. [Begin with sequential execution](#1-begin-with-sequential-execution)
2. [Run synchronous functions in threads](#2-run-synchronous-functions-in-threads)
3. [Understand the GIL and free-threaded Python](#3-understand-the-gil-and-free-threaded-python)
4. [Run independent CPU work: `fib.py`](#4-run-independent-cpu-work-fibpy)
5. [Observe a race condition: `counter_buggy.py`](#5-observe-a-race-condition-counter_buggypy)
6. [Fix correctness with a lock: `counter_fixed.py`](#6-fix-correctness-with-a-lock-counter_fixedpy)
7. [Design for parallelism: `counter_fixed_fast.py`](#7-design-for-parallelism-counter_fixed_fastpy)
8. [Reuse threads with executors and futures](#8-reuse-threads-with-executors-and-futures)
9. [Use processes for isolated CPU parallelism](#9-use-processes-for-isolated-cpu-parallelism)
10. [Use `asyncio` for cooperative I/O concurrency](#10-use-asyncio-for-cooperative-io-concurrency)
11. [Choose synchronization tools](#11-choose-synchronization-tools)
12. [Choose the correct concurrency model](#12-choose-the-correct-concurrency-model)
13. [Measure performance correctly](#13-measure-performance-correctly)

### How to study this without overload

Do not read all 13 lessons in one sitting:

1. **Session 1:** lessons 1 and 2; type and run the sequential and raw-thread
   examples.
2. **Session 2:** lessons 3 and 4; compare the GIL modes with `fib.py`.
3. **Session 3:** lessons 5 through 7; run the three counter programs in order.
4. **Session 4:** lesson 10; run `worker.py` and follow its event-loop timeline.
5. Keep lessons 8, 9, and 11 through 13 as reference material until you need
   those tools.

After each session, stop and explain the three “What to remember” bullets in
your own words. You do not need to memorize every API.

## Your questions — brief answers

**What is the GIL?** It is CPython's interpreter lock. With the GIL enabled,
normally only one thread in a process executes Python bytecode at a time.

**Why does CPython have it?** It historically provided a simple way to protect
reference counting and other interpreter internals shared by threads.

**What are its main pros and cons?** It simplifies internal memory safety and
has historically helped single-threaded performance, but it prevents
pure-Python CPU threads from executing in parallel across CPU cores.

**Can threads still be used with the GIL?** Yes. They can speed up I/O-bound
programs because one thread can run while another waits for file, network, or
database I/O. They normally do not speed up pure-Python CPU work.

**If threads handle I/O, why have `async` and `await`?** Both overlap waiting.
Threads use OS-scheduled workers and work naturally with blocking functions;
`asyncio` uses lightweight tasks scheduled by an event loop and works with
async-compatible functions.

**Must I/O use `asyncio` instead of threads?** No. Use threads for an existing
blocking API, `asyncio` for an async API, and `asyncio.to_thread()` when async
code must call a blocking function.

---

**Part I — Core story: sequential calls, threads, the GIL, races, and the
local-state solution**

## 1. Begin with sequential execution

Sequential execution means the current function finishes one operation before
starting the next.

```python
import time


def download(name: str) -> str:
    print(f"Starting {name}")
    time.sleep(1)  # represents waiting for file or network I/O
    print(f"Finished {name}")
    return name


results = []

for number in range(3):
    result = download(f"file-{number}")
    results.append(result)

print(results)
```

The order is:

```text
download file-0 -> wait 1 second -> finish
download file-1 -> wait 1 second -> finish
download file-2 -> wait 1 second -> finish
```

The total time is about three seconds because each call blocks the same thread.

### Syntax used here

- `def download(...):` defines a function. It does not execute the body.
- `download` means the function object.
- `download("file-0")` calls it immediately and waits for its return value.
- `name: str` and `-> str` are type hints. They document types but do not create
  concurrency.
- `f"file-{number}"` inserts `number` into a string.
- `range(3)` produces `0`, `1`, and `2`.
- `return name` sends a value back to the caller.

### I/O-bound versus CPU-bound

- An **I/O-bound** task spends most of its time waiting for a network, disk,
  database, or user. `download()` represents I/O-bound work.
- A **CPU-bound** task spends most of its time executing calculations.
  Recursive Fibonacci calculation represents CPU-bound work.

This distinction determines which concurrency tool is useful.

### What to remember

- Calling `function(...)` directly is synchronous: the caller waits.
- Waiting on external work is I/O-bound; spending time calculating is
  CPU-bound.
- Concurrency starts by identifying work that can safely overlap.

---

## 2. Run synchronous functions in threads

A thread is an execution path inside a process. Threads in the same process
share memory, files, and other process resources.

You do not have to rewrite a normal synchronous function before a thread can
call it. Instead of calling the function yourself, give the function and its
arguments to a `Thread` object.

### Create one thread

```python
import threading


thread = threading.Thread(
    target=download,
    args=("file-0",),
    name="download-0",
)
```

This constructs a thread description. It has not started yet.

- `target=download` passes the function itself.
- Do not write `target=download("file-0")`. That would call `download`
  immediately on the current thread and pass its return value as `target`.
- `args=("file-0",)` is the tuple of positional arguments for the target.
- The comma matters: `("file-0",)` is a one-item tuple, while `("file-0")` is
  only a string.
- `name=` is optional and helps with logs and debugging.

When started, this thread performs the equivalent of:

```python
download("file-0")
```

### Start and wait for one thread

```python
thread.start()
thread.join()
```

- `start()` asks the operating system to start a new thread and invoke the
  target. A `Thread` object can be started only once.
- `join()` blocks the calling thread until the worker terminates.
- Calling `thread.run()` directly does not create a new thread; it runs the
  target sequentially on the caller.

### Run three calls concurrently

```python
import threading


threads = []

for number in range(3):
    thread = threading.Thread(
        target=download,
        args=(f"file-{number}",),
    )
    threads.append(thread)

for thread in threads:
    thread.start()

for thread in threads:
    thread.join()
```

The important pattern is:

```text
create all -> start all -> join all
```

After all three calls start, their one-second I/O waits overlap:

```text
Main thread: start T1 -> start T2 -> start T3 -> join/wait
Thread T1:   start file-0 -> wait ------------> finish
Thread T2:   start file-1 -> wait ------------> finish
Thread T3:   start file-2 -> wait ------------> finish
```

The total time is about one second instead of three.

This incorrect arrangement removes most concurrency:

```python
for number in range(3):
    thread = threading.Thread(
        target=download,
        args=(f"file-{number}",),
    )
    thread.start()
    thread.join()  # waits before the next thread starts
```

### What threads do not do

Threads do not change `download()` into an `async def` function. The function
remains synchronous; it simply runs on another operating-system thread.

Raw `Thread` objects also do not directly return the target's value through
`join()`. `join()` always returns `None`. Uncaught target exceptions are sent to
`threading.excepthook()` and normally printed, not re-raised by `join()`.
Executors solve both problems later in these notes.

### For I/O, should I use threads or `asyncio`?

Both are valid. Python does **not** have a rule saying that all I/O must use
`async` and `await`. The standard-library [`threading`
documentation](https://docs.python.org/3/library/threading.html) describes
threads as an appropriate model for running multiple I/O-bound tasks and
describes [`asyncio`](https://docs.python.org/3/library/asyncio.html) as an
alternative that achieves task-level concurrency without requiring one
operating-system thread per task.

Threads are not only for parallelism. With the GIL enabled, threads provide
useful **I/O concurrency** even though they cannot execute pure-Python
CPU-bound code in parallel.

Both approaches overlap waiting, but they use different schedulers:

```text
Threads:
operating system switches among several threads
a blocking I/O call blocks only its worker thread

asyncio:
an event loop switches among tasks, usually on one thread
an awaitable I/O call pauses only its current task
```

Choose according to the API you actually have:

| Existing function or library | Start with | Why |
|---|---|---|
| Blocking synchronous I/O, such as `requests.get()` | `ThreadPoolExecutor` | It works without rewriting the function |
| Async I/O, such as an async HTTP or database client | `asyncio` | Its operations already provide awaitables |
| Blocking function inside an async application | `await asyncio.to_thread(...)` | Keeps the event-loop thread responsive |
| Pure-Python CPU work with the GIL enabled | `ProcessPoolExecutor` | CPU threads cannot execute Python bytecode in parallel |
| Independent CPU work in free-threaded Python | `ThreadPoolExecutor` | Threads may execute Python code on multiple cores |

The same blocking function can be scheduled on a thread pool:

```python
from concurrent.futures import ThreadPoolExecutor


with ThreadPoolExecutor(max_workers=10) as executor:
    results = list(executor.map(download, filenames))
```

An async-native function is scheduled as asyncio tasks:

```python
results = await asyncio.gather(
    download_async("file-0"),
    download_async("file-1"),
    download_async("file-2"),
)
```

Do not choose by saying “I/O means asyncio.” Ask whether the library gives you
a normal blocking function or an async function. For a modest number of
blocking operations, threads are often the smallest change. For many
connections in an async-compatible application, lightweight asyncio tasks are
often a better fit.

### What to remember

- Pass the function as `target=download`, without parentheses, and put its
  arguments in `args=(...)`; a one-item tuple needs a trailing comma.
- Create all threads, start all threads, and then join all threads.
- For I/O, choose threads for blocking APIs and `asyncio` for async APIs; both
  are standard concurrency approaches.

---

## 3. Understand the GIL and free-threaded Python

### Concurrency is not the same as parallelism

- **Concurrency:** multiple jobs make progress during the same time period.
- **Parallelism:** multiple jobs execute at the same instant.

Threads can be concurrent even when only one thread executes Python code at a
time. True CPU parallelism requires multiple execution units to run
simultaneously.

### Process, thread, and CPU terminology

- A **process** is a running program with its own memory space.
- A **software thread** is an execution path inside a process.
- A **physical CPU core** is a hardware execution core.
- A **logical processor** is a processor exposed to the operating system.
  Simultaneous multithreading may expose two logical processors per physical
  core.

A program may create more software threads than logical processors. The
operating-system scheduler gives them turns:

```text
20 runnable software threads on 8 logical processors
-> at most roughly 8 execute at one instant
-> the remaining threads wait for later time slices
```

### What is the GIL?

The Global Interpreter Lock is a lock used by standard CPython. A thread must
hold it before executing Python bytecode, and normally only one thread per
process holds it at a time.

Think of one microphone shared by several speakers:

```text
Thread A holds microphone -> executes Python
Thread B waits
Thread A releases it
Thread B acquires it -> executes Python
```

CPython historically used the GIL as a relatively simple way to protect
reference counts and other interpreter internals. It also simplified the C
extension interface. The GIL protects interpreter integrity; it does not make a
program's multi-step shared-data operations thread-safe.

### Why did CPython need the GIL?

In simple terms, many threads share the same Python objects and interpreter
memory. CPython must prevent two threads from corrupting that internal state
while they update it. Its traditional solution was one interpreter-wide lock
instead of many smaller locks:

```text
without protection:
two threads update Python's internal object bookkeeping at the same time
-> bookkeeping may become corrupted

traditional CPython protection:
one thread holds the GIL while executing Python bytecode
-> interpreter internals remain consistent
```

The GIL is a CPython implementation mechanism, not a requirement of the Python
language. A free-threaded CPython build replaces that one global lock with
other thread-safe mechanisms. Therefore, the traditional build needs the GIL
because its internals were designed around it; free-threaded CPython can operate
without it because those internals were redesigned.

### GIL advantages and disadvantages

| Advantages | Disadvantages |
|---|---|
| Provides a comparatively simple way to protect interpreter internals | Serializes execution of Python bytecode within a process |
| Makes reference-counting memory management easier to coordinate | Prevents GIL-enabled pure-Python CPU threads from running in parallel across cores |
| Historically simplified integration with many C extensions | CPU threads may become slower because of scheduling and lock hand-offs |
| Avoids requiring a fine-grained application-visible lock around every Python object operation | CPU parallelism often requires processes, native code that releases the GIL, or free-threaded Python |
| Still permits useful I/O concurrency because blocking operations can release the GIL | Multiprocessing workarounds use more memory and require data serialization or inter-process communication |

The most important boundary is:

```text
The GIL protects CPython's interpreter state.
Your lock protects your application's shared state.
```

For example, the GIL is not a promise that a multi-step operation such as
`counter += 1` is safe from logical races.

### Effect of the GIL

For blocking I/O, CPython and many libraries release the GIL while waiting:

```text
Thread A starts network read -> releases GIL and waits
Thread B executes Python while A waits
```

That is why threads are useful for I/O even with the GIL enabled.

For pure-Python CPU work, a standard GIL-enabled process cannot execute Python
bytecode on several cores simultaneously. CPU threads take turns and may be
slower because of scheduling overhead.

Native extensions are an exception when they release the GIL and perform work
outside Python bytecode.

### Free-threaded CPython

A free-threaded build can disable the GIL. Multiple threads may then execute
Python code in parallel on different CPU cores:

```text
GIL enabled:  Core 1 -> Thread A; Thread B waits for GIL
GIL disabled: Core 1 -> Thread A; Core 2 -> Thread B
```

Python 3.13 introduced an experimental free-threaded build. Python 3.14 made it
officially supported but still optional.

### Install a free-threaded interpreter with `uv`

Create a virtual environment without replacing the computer's normal Python:

Windows PowerShell:

```powershell
uv venv --python 3.14t
.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
uv venv --python 3.14t
source .venv/bin/activate
```

The `t` selects the free-threaded build. Confirm what was installed:

```powershell
python -VV
```

Check build capability and current runtime state:

```python
import sys
import sysconfig

print(sysconfig.get_config_var("Py_GIL_DISABLED"))
print(sys._is_gil_enabled())
```

- `Py_GIL_DISABLED == 1` means the interpreter supports disabling the GIL.
- `sys._is_gil_enabled() is False` means this process is currently running
  without the GIL.

Compare both modes using the same free-threaded interpreter:

```powershell
python program.py
python -X gil=0 program.py
python -X gil=1 program.py
```

`-X` is an interpreter option, so it appears before the script name.

### Free threading is not automatic speed

Free threading helps when threads perform substantial independent CPU work.
It may not help when:

- work is too small to repay scheduling overhead;
- most work is protected by one shared lock;
- workers constantly mutate the same memory;
- memory bandwidth is the bottleneck;
- there are more runnable workers than useful CPU capacity;
- a dependency re-enables the GIL.

Free-threaded CPython replaces one global lock with internal mechanisms such as
fine-grained container locks, biased and deferred reference counting,
immortalized objects, and the `mimalloc` allocator. Application synchronization
is still required.

### What to remember

- The GIL permits multithreading but normally serializes Python bytecode inside
  one process.
- Threads still work well for I/O; CPU parallelism needs free threading,
  processes, or native code that releases the GIL.
- Disabling the GIL guarantees neither speed nor thread safety.

---

## 4. Run independent CPU work: `fib.py`

The repository's [`fib.py`](multiprocessing/fib.py) runs eight
independent Fibonacci calculations. The folder name is historical; this file
uses threads, not `multiprocessing`.

```python
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

    for _ in range(THREADS):
        thread = threading.Thread(target=fib, args=(35,))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    print(f"Completed: {time.time() - start_time:.2f} seconds")


if __name__ == "__main__":
    main()
```

### Understand `fib()`

`fib()` is recursive: it calls itself with smaller values until it reaches the
base case `n <= 1`.

```text
fib(4)
-> fib(3) + fib(2)
-> many smaller fib() calls
```

It performs many Python function calls and almost no I/O, so it is CPU-bound.
The eight calls do not share application data, making this an
**embarrassingly parallel** workload.

### Understand the thread syntax

```python
threading.Thread(target=fib, args=(35,))
```

means:

```text
run fib(35) on this thread when start() is called
```

The loop variable is `_` because its value is unused. `range(THREADS)` simply
repeats the body eight times.

The integer returned by `fib()` is discarded because raw `Thread` does not
collect return values. That is acceptable for this timing demonstration, but an
executor is preferable when results matter.

### Observed result

```text
python 03_concurrency/multiprocessing/fib.py          -> GIL disabled -> 0.81 seconds
python -X gil=1 03_concurrency/multiprocessing/fib.py -> GIL enabled  -> 4.13 seconds
```

The observed speedup is approximately:

```text
4.13 / 0.81 = 5.1 times
```

It is not exactly eight times because eight threads do not guarantee eight
fully independent physical cores. Scheduling, logical-versus-physical cores,
CPU frequency, memory management, and the serial parts of the program all
limit scaling.

### What to remember

- `fib.py` is CPU-bound and its eight calculations are independent.
- Independent local work needs no application lock.
- A raw `Thread` discards `fib()`'s return value; this file is a timing
  experiment.

---

## 5. Observe a race condition: `counter_buggy.py`

Eight workers each attempt one million increments:

```python
COUNT = 1_000_000
THREADS = 8
counter = 0


def worker():
    global counter

    for _ in range(COUNT):
        counter += 1
```

`global counter` means assignments inside `worker()` update the module-level
name rather than creating a function-local variable.

The expected result is:

```text
COUNT * THREADS = 1,000,000 * 8 = 8,000,000
```

### Why `counter += 1` is unsafe

An integer is immutable, so this operation conceptually performs:

```text
read counter -> calculate counter + 1 -> assign the new integer
```

Two threads can interleave:

```text
counter begins at 0
Thread A reads 0
Thread B reads 0
Thread A computes 1
Thread B computes 1
Thread A writes 1
Thread B writes 1  <- A's update is lost
expected 2, actual 1
```

This is a **lost update**, one kind of race condition. A race condition means
the result depends on unpredictable timing.

### Observed result

```text
python -X gil=1 03_concurrency/threading/counter_buggy.py -> Counter: 8,000,000
python 03_concurrency/threading/counter_buggy.py          -> Counter: 1,105,222
```

The correct GIL-enabled result does not prove the program is thread-safe. That
particular execution did not expose the race. Python code must not use the GIL
as an application data lock.

The free-threaded run exposes the bug frequently because several threads can
read and write the shared binding simultaneously.

### Golden correctness rule

> If multiple threads access the same shared state and at least one writes,
> synchronize access or redesign the program to avoid sharing it.

### What to remember

- `counter += 1` is read, compute, then write—not one indivisible operation.
- A correct result in one run, including a GIL-enabled run, does not prove
  thread safety.
- Timing-dependent lost updates are a race condition.

---

## 6. Fix correctness with a lock: `counter_fixed.py`

The simple repair uses one shared lock:

```python
import threading

counter = 0
lock = threading.Lock()


def worker():
    global counter

    for _ in range(COUNT):
        with lock:
            counter += 1
```

### Understand the lock syntax

`threading.Lock()` creates a mutex. All workers must use the same lock object.
A separate lock per worker would protect nothing because the workers would not
coordinate with one another.

```python
with lock:
    counter += 1
```

is conceptually:

```python
lock.acquire()
try:
    counter += 1
finally:
    lock.release()
```

`with` guarantees release even if the protected code raises an exception.
Only one thread may execute this critical section at a time.

### Correctness versus performance

Observed results:

```text
python -X gil=1 03_concurrency/threading/counter_fixed.py -> 0.551 s -> Counter: 8,000,000
python 03_concurrency/threading/counter_fixed.py          -> 0.867 s -> Counter: 8,000,000
```

Both results are correct, but the free-threaded run is about 1.58 times slower
(`0.867 / 0.551`).

The application acquires the lock eight million times and serializes the only
useful operation. Disabling the GIL cannot make a lock-protected serial section
parallel. With the GIL disabled, multiple cores also compete for the same lock.

Repeated writes to one memory location may move its cache line between CPU
caches, called cache-line bouncing or ping-pong. This is a plausible extra cost,
but elapsed time alone cannot prove how much it contributed; hardware profiling
would be needed.

The lock fixes correctness. It does not fix the poor parallel design.

### What to remember

- Every participant must use the same lock around the shared invariant.
- A lock restores correctness by letting only one thread enter its protected
  section.
- Protecting the entire useful operation can serialize the program and remove
  the speed benefit.

---

## 7. Design for parallelism: `counter_fixed_fast.py`

The scalable design gives each worker local state and combines small results
afterward:

```python
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
    results = list(
        executor.map(lambda _: worker(), range(THREADS))
    )

counter = sum(results)

print("Time:", time.time() - start_time)
print("Counter:", counter)
print("Expected:", COUNT * THREADS)
```

### Why local state is safe

Each call to `worker()` creates a different `local_counter`. No other worker can
access that local variable. Every worker returns `1_000_000`, and the main
thread combines the eight values after all workers finish:

```text
[1,000,000, 1,000,000, ..., 1,000,000]
-> sum(...)
-> 8,000,000
```

This pattern is called **map then reduce**:

```text
split inputs -> process independently -> collect results -> reduce/merge
```

### Understand the executor syntax

```text
with ThreadPoolExecutor(max_workers=THREADS) as executor:
```

- Creates a reusable pool with at most eight worker threads.
- Assigns the pool to `executor`.
- Automatically calls `executor.shutdown(wait=True)` when the block exits.

```python
range(THREADS)
```

produces `0` through `7`, giving `map()` eight inputs.

```python
lambda _: worker()
```

defines a small function that accepts one input, ignores it, and calls
`worker()`. `_` is an ordinary variable name conventionally used for an ignored
value.

```python
executor.map(lambda _: worker(), range(THREADS))
```

schedules the lambda once per range value and yields return values in input
order. `list(...)` consumes those results and waits as necessary.

A clearer version passes the iteration count directly:

```python
def worker(iterations):
    local_counter = 0

    for _ in range(iterations):
        local_counter += 1

    return local_counter


with ThreadPoolExecutor(max_workers=THREADS) as executor:
    results = list(executor.map(worker, [COUNT] * THREADS))
```

Read the expression from the inside outward.

#### 1. Build the arguments

```python
[COUNT] * THREADS
```

List multiplication repeats list elements. If `COUNT = 5` and `THREADS = 3`,
the expression produces:

```python
[COUNT] * THREADS
# [5, 5, 5]
```

This list does not become one argument. It is an **iterable of arguments**:
one element for each function call.

#### 2. Map each argument to one call

```python
executor.map(worker, [5, 5, 5])
```

is conceptually equivalent to scheduling:

```python
worker(5)  # first list element
worker(5)  # second list element
worker(5)  # third list element
```

For the real values, it schedules eight independent calls:

```text
worker(COUNT), worker(COUNT), ... eight times
```

Each list element is passed to the `iterations` parameter:

```python
def worker(iterations):
    # iterations receives COUNT in every call
    ...
```

The parameter does not need to be named `COUNT`. Argument passing is
positional: the first value goes into the first parameter. `COUNT` is the
caller's variable; `iterations` is the worker's local name for the received
integer.

#### 3. Run calls using the pool

```python
ThreadPoolExecutor(max_workers=THREADS)
```

creates a pool that may run at most `THREADS` calls simultaneously. It does not
guarantee which particular thread runs a call. When a thread finishes one call,
the pool can give that thread another pending call.

The same scheduling written with `submit()` is:

```python
with ThreadPoolExecutor(max_workers=THREADS) as executor:
    futures = [
        executor.submit(worker, COUNT)
        for _ in range(THREADS)
    ]
    results = [future.result() for future in futures]
```

`executor.submit(worker, COUNT)` means “schedule `worker(COUNT)`” and returns a
`Future`. `executor.map()` performs this repeated submission more compactly.

#### 4. Collect the returned values

`executor.map(...)` returns an iterator over the workers' return values in the
same order as the input arguments. Wrapping it in `list(...)` consumes that
iterator and waits when the next result is not ready:

```python
results = list(executor.map(worker, [5, 5, 5]))
# [5, 5, 5]
```

Every `worker(5)` creates its own `local_counter`, increments it five times, and
returns `5`. Finally, `sum(results)` produces `15`.

With the real settings:

```text
arguments: [1,000,000, ... eight entries]
calls:     worker(1,000,000) eight times
returns:   [1,000,000, ... eight results]
sum:       8,000,000
```

#### Passing more than one argument

Give `map()` one iterable per function parameter:

```python
def worker(name, iterations):
    return f"{name}: {iterations}"


names = ["A", "B", "C"]
counts = [5, 10, 15]

with ThreadPoolExecutor(max_workers=3) as executor:
    results = list(executor.map(worker, names, counts))
```

This schedules `worker("A", 5)`, `worker("B", 10)`, and `worker("C", 15)`.
`map()` takes one value from each iterable for every call and stops when the
shortest iterable is exhausted.

### Observed result

```text
python 03_concurrency/threading/counter_fixed_fast.py          -> 0.056 s -> Counter: 8,000,000
python -X gil=1 03_concurrency/threading/counter_fixed_fast.py -> 0.101 s -> Counter: 8,000,000
```

For this run, disabling the GIL gave approximately `0.101 / 0.056 = 1.8` times
the throughput.

The improvement comes from restructuring the work:

1. Workers do not acquire an application lock in the hot loop.
2. Independent loops may run on separate cores without the GIL.
3. Only eight small results are shared.
4. The main thread merges results once at the end.

This greatly reduces shared cache-line contention; it does not mean that
hardware performs literally zero cache-coherence work.

### More threads than CPU processors

`max_workers` limits software threads; it does not reserve physical cores. If a
machine exposes eight logical processors:

```text
2 workers  -> true parallelism on up to 2 processors; capacity remains idle
8 workers  -> possible full utilization
20 workers -> roughly 8 run at once; the rest are time-sliced
```

The output stays correct with 20 workers because every worker owns local state,
and `Expected` also changes to `COUNT * THREADS`. Correctness does not imply
faster execution.

Choose an initial CPU worker count with:

```python
import os

get_available_cpus = getattr(os, "process_cpu_count", os.cpu_count)
workers = get_available_cpus() or 1
```

- `getattr()` selects `os.process_cpu_count` when available and falls back to
  `os.cpu_count`.
- The selected object is a function, so the following `()` calls it.
- `or 1` handles the uncommon case where CPU count cannot be determined.

Benchmark nearby values. Logical processors on one physical core share
resources, and libraries may create their own native threads.

### Golden performance rule

> Split a large job into independent chunks, avoid communication in the hot
> path, and merge a small set of results at the end.

### What to remember

- Each worker updates local state, so the hot loop needs no shared lock.
- `executor.map()` runs one call per input and produces their returned values.
- More software threads than processors can still be correct, but usually do
  not increase CPU throughput.

---

**Part II — Reference toolbox: executors, processes, asyncio, synchronization,
selection, and measurement**

## 8. Reuse threads with executors and futures

For ordinary lists of tasks, prefer `ThreadPoolExecutor` over manually creating
one `Thread` per call.

### One function, one argument per task

Sequential:

```python
results = [work(item) for item in items]
```

Thread pool:

```python
from concurrent.futures import ThreadPoolExecutor


with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(work, items))
```

`map(work, items)` conceptually schedules `work(items[0])`, `work(items[1])`,
and so on. Results are yielded in input order, not completion order.

### Several arguments and individual futures

```python
with ThreadPoolExecutor(max_workers=4) as executor:
    future = executor.submit(
        some_function,
        first_arg,
        second_arg,
        option=True,
    )

    result = future.result()
```

`submit()` schedules:

```python
some_function(first_arg, second_arg, option=True)
```

and immediately returns a `Future`, which is a handle to a result that may not
exist yet.

- `future.result()` waits if necessary and returns the function's value.
- If the worker raised an exception, `result()` re-raises it in the caller.
- `future.done()` reports whether it finished or was cancelled.
- `future.cancel()` cancels only work that has not started.

Python cannot safely force-stop an arbitrary running thread. A running function
must cooperate, commonly by checking a `threading.Event`.

### Handle results as they finish

```python
from concurrent.futures import as_completed


with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [
        executor.submit(work, item)
        for item in items
    ]

    for future in as_completed(futures):
        try:
            print(future.result())
        except Exception as error:
            print("Task failed:", error)
```

The list comprehension submits all work. `as_completed()` yields futures in
completion order. `try/except` handles worker exceptions in the caller.

Do not have a pool worker wait for another future from the same undersized pool.
A one-worker pool deadlocks if its only worker submits more work to that pool
and waits for it.

In Python 3.14+, `executor.map(..., buffersize=N)` limits how many submitted
results wait to be yielded, adding backpressure for large input streams.

### Run a synchronous function from `asyncio`

`asyncio.to_thread()` creates an awaitable for a normal blocking function:

```python
import asyncio


async def main():
    results = await asyncio.gather(
        asyncio.to_thread(download, "file-0"),
        asyncio.to_thread(download, "file-1"),
        asyncio.to_thread(download, "file-2"),
    )
    print(results)


asyncio.run(main())
```

The synchronous `download()` function is unchanged. It runs on a thread-pool
worker while the event-loop thread remains responsive.

This is not the same as changing `def` to `async def`. A native coroutine must
use non-blocking awaitable operations internally.

---

## 9. Use processes for isolated CPU parallelism

Each process has its own interpreter and memory. Processes can execute
pure-Python CPU work across cores even when the GIL is enabled.

Sequential version:

```python
def square(number):
    return number * number


numbers = [1, 2, 3, 4]
results = [square(number) for number in numbers]
```

Process-pool version:

```python
from concurrent.futures import ProcessPoolExecutor


def square(number):
    return number * number


def main():
    numbers = [1, 2, 3, 4]

    with ProcessPoolExecutor() as executor:
        results = list(executor.map(square, numbers))

    print(results)


if __name__ == "__main__":
    main()
```

### Process syntax

- `ProcessPoolExecutor()` owns reusable worker processes.
- `map(square, numbers)` serializes inputs, sends calls to workers, and returns
  squares in input order.
- `if __name__ == "__main__":` prevents imported worker processes from
  recursively creating new pools. It is essential on Windows.
- Worker functions should be defined at module level.
- Arguments, return values, and callables must usually be picklable. Lambdas
  and nested functions should not be expected to work.

Squaring four integers is only a syntax example and will usually be slower in a
process pool. Each submitted task needs enough CPU work to repay process startup
and serialization costs.

Processes do not normally share Python objects. Common communication tools are:

| Tool | Main operations | Purpose |
|---|---|---|
| `multiprocessing.Queue` | `put()`, `get()` | Serialized messages among processes |
| `multiprocessing.Pipe` | `send()`, `recv()` | Direct communication between two endpoints |
| `multiprocessing.Value/Array` | Shared scalar or fixed array plus locks | Small shared regions |
| `multiprocessing.shared_memory` | Named shared byte buffer | Large binary data |
| `multiprocessing.Manager` | Proxy lists, dicts, queues, and locks | Convenient but slower shared objects |

Do not use a normal `queue.Queue` for communication among processes; that queue
is for threads.

### Python 3.14 isolated interpreters

`InterpreterPoolExecutor` runs each worker thread in a separate interpreter.
Each interpreter has its own runtime state and GIL, enabling multi-core
parallelism. Mutable Python objects are isolated, and calls and results are
serialized.

This model sits between threads and processes but has stricter compatibility
requirements. Verify that imported extension modules support isolated
interpreters.

---

## 10. Use `asyncio` for cooperative I/O concurrency

`asyncio` normally runs many tasks on one event-loop thread. Tasks cooperate by
yielding control at `await` points.

### Sequential synchronous version

```python
import time


def worker(name, delay):
    print(name, "starting")
    time.sleep(delay)
    return name


first = worker("A", 1)
second = worker("B", 1)
```

This takes about two seconds because `time.sleep()` blocks the thread.

### Native async version

```python
import asyncio


async def worker(name, delay):
    print(name, "starting")
    await asyncio.sleep(delay)
    return name


async def main():
    results = await asyncio.gather(
        worker("A", 1),
        worker("B", 1),
        worker("C", 1),
    )
    print(results)


asyncio.run(main())
```

The three waits overlap and finish in about one second.

### Understand async syntax

- `async def` defines a coroutine function.
- Calling `worker("A", 1)` returns a coroutine object; it does not immediately
  execute the body.
- `await expression` pauses the current coroutine until an awaitable completes
  and lets the event loop run other ready tasks.
- `await asyncio.sleep(1)` pauses this task without blocking the thread.
- `asyncio.gather(...)` schedules all supplied coroutines, waits for all, and
  returns values in argument order.
- `asyncio.run(main())` creates the event loop, runs `main()` to completion, and
  closes the loop. A normal script calls it once at the boundary.

These calls remain sequential:

```python
first = await worker("A", 1)
second = await worker("B", 1)
```

The second call is not reached until the first finishes.

### Event-loop execution order

```text
main schedules A, B, and C
A runs -> reaches await -> pauses
B runs -> reaches await -> pauses
C runs -> reaches await -> pauses
timers complete
tasks become ready and resume
```

Async tasks are not automatically threads. In the usual setup, one event-loop
thread executes one task at a time between await points.

### Create explicit tasks

```python
task = asyncio.create_task(
    worker("A", 1),
    name="worker-A",
)

result = await task
```

`create_task()` schedules the coroutine and returns a `Task` handle immediately.
`await task` retrieves its result or exception.

Prefer structured ownership for groups:

```python
async def main():
    async with asyncio.TaskGroup() as group:
        task_a = group.create_task(worker("A", 1))
        task_b = group.create_task(worker("B", 2))

    print(task_a.result(), task_b.result())
```

Leaving `async with` waits for the children. If one fails, `TaskGroup` cancels
the remaining children, waits for cleanup, and raises an exception group.

By contrast, `gather()` propagates its first exception by default but does not
automatically cancel the other submitted awaitables.

### Read the repository's `worker.py` in execution order

[`worker.py`](multiprocessing/worker.py) uses task names and thread identifiers
to make scheduling visible. Its directory name is historical; this example is
`asyncio`, not `multiprocessing`.

Run it from the repository root:

```powershell
python 03_concurrency/multiprocessing/worker.py
```

Its important inspection code is:

```python
thread = threading.current_thread()
task = asyncio.current_task()

print(
    task.get_name(),
    thread.name,
    thread.ident,
    thread.native_id,
)
```

- `current_task()` returns the currently executing asyncio task.
- `task.get_name()` distinguishes `task-1`, `task-2`, and `task-3`.
- `current_thread()` returns the operating-system thread executing that code.
- `ident` is Python's thread identifier; `native_id` is the OS-assigned native
  thread identifier.

The execution story is:

```text
asyncio.run(main()) creates the event loop
main creates task-1, task-2, and task-3
main reaches await task1 and yields control
task-1 starts and yields at asyncio.sleep()
task-2 starts and yields at asyncio.sleep()
task-3 starts and yields at asyncio.sleep()
their timers expire and the tasks become ready
the event loop resumes each task so it can finish
main observes all three completed tasks and returns
asyncio.run() closes the loop
```

The start and finish messages normally show the same thread name and ID because
all three tasks use one event-loop thread. They are separate **tasks**, not
separate threads. Their exact ordering should not be used as a correctness
guarantee; only the order within one coroutine is guaranteed. The next section
explains why tasks can still race when shared state is split across an `await`.

### Async race conditions and locks

One thread does not remove logical races. Another task can change shared state
while the first task is paused:

```python
balance = 100


async def withdraw(amount):
    global balance
    old_balance = balance
    await asyncio.sleep(0)
    balance = old_balance - amount
```

Protect the invariant with one shared async lock:

```python
lock = asyncio.Lock()


async def withdraw_safely(amount):
    global balance

    async with lock:
        old_balance = balance
        await asyncio.sleep(0)
        balance = old_balance - amount
```

`async with lock` waits without blocking the event-loop thread, allows one task
inside, and releases the lock on exit. `asyncio.Lock` coordinates asyncio tasks;
it does not protect data accessed by separate OS threads.

### Timeouts and cancellation

```python
async def main():
    try:
        async with asyncio.timeout(2):
            await worker("slow", 10)
    except TimeoutError:
        print("Operation timed out")
```

The timeout gives its block a two-second deadline. Cancellation is cooperative
and is normally delivered at an await point. Cleanup belongs in `try/finally`;
do not normally swallow `asyncio.CancelledError`.

### Bounded concurrency and backpressure

```python
limit = asyncio.Semaphore(10)


async def limited_call(item):
    async with limit:
        return await call_service(item)
```

`Semaphore(10)` owns ten permits. Each task acquires one before entering and
returns it on exit, limiting simultaneous service calls to ten.

For continuous streams, use a bounded queue:

```python
queue = asyncio.Queue(maxsize=10)

await queue.put(item)
item = await queue.get()
try:
    await process(item)
finally:
    queue.task_done()

await queue.join()
```

The producer pauses when the queue is full. This pressure prevents producers
from overwhelming consumers or memory.

### Never block the event loop

Do not call slow blocking functions directly inside `async def`:

```python
# Wrong: blocks every task on this event-loop thread
time.sleep(1)

# Native async wait
await asyncio.sleep(1)

# Existing blocking function moved to a thread
result = await asyncio.to_thread(blocking_function, argument)
```

On GIL-enabled CPython, send pure-Python CPU work to a process pool. On a
compatible free-threaded build, a thread executor can also run it in parallel.

---

## 11. Choose synchronization tools

### Why does synchronization exist?

Concurrency lets workers overlap, but sometimes those workers must coordinate:

```text
Problem 1: two workers try to change the same value
Problem 2: a worker must wait until another worker produces something
Problem 3: only a limited number of workers may use a resource
Problem 4: the main program needs to ask workers to stop
```

Synchronization tools provide rules for that coordination. Their purpose is
normally **correctness and control**, not speed. Waiting for a lock may make a
program slower, but an incorrect fast result is useless.

First ask whether sharing can be removed:

```text
Best: each worker owns local data and returns a result
Next: workers exchange messages through a Queue
When sharing is necessary: protect the shared rule with synchronization
```

### Choose a tool by asking a question

| Question | Tool | Intuitive picture |
|---|---|---|
| Must only one thread enter this code at a time? | `Lock` | One key for one room |
| Should workers stop or begin after one signal? | `Event` | A red/green signal light |
| May at most N workers use this resource? | `Semaphore` | A limited number of tickets |
| Should one thread safely give jobs to another? | `queue.Queue` | A protected inbox |
| Must a thread wait until a shared condition becomes true? | `Condition` | Sleep until a doorbell rings, then recheck |
| Must all workers reach the same stage before continuing? | `Barrier` | Everyone meets at a checkpoint |
| Must the same thread acquire a lock recursively? | `RLock` | An owner may re-enter its room |
| Does each thread need its own separate value? | `threading.local` | A private notebook per worker |

For a beginner, learn `Lock`, `Event`, `Semaphore`, and `Queue` first. The other
tools solve less common coordination patterns.

### `Lock`: exactly one thread at a time

Imagine several threads sharing one printer. Documents must not be mixed, so
all threads share one lock:

```python
import threading
import time

printer_lock = threading.Lock()


def use_printer(name):
    with printer_lock:
        print(name, "started printing")
        time.sleep(1)
        print(name, "finished printing")


threads = [
    threading.Thread(target=use_printer, args=(name,))
    for name in ["A", "B", "C"]
]

for thread in threads:
    thread.start()

for thread in threads:
    thread.join()
```

`with printer_lock:` means: wait for the shared key, enter, and return the key
on exit. Only the protected block is serialized; code outside it may overlap.

### `Event`: broadcast a yes/no signal

An event stores a flag. `set()` changes it to true and wakes threads waiting for
it. A common use is requesting a graceful stop:

```python
import threading
import time

stop_requested = threading.Event()


def worker():
    while not stop_requested.wait(timeout=0.2):
        print("working")
    print("worker stopped")


thread = threading.Thread(target=worker)
thread.start()

time.sleep(0.7)
stop_requested.set()
thread.join()
```

`wait(0.2)` returns `True` immediately when the event is set. Unlike a lock, an
event does not give one thread exclusive ownership; every observer can see the
same signal.

### `Semaphore`: allow at most N users

Suppose a service permits only two simultaneous requests:

```python
import threading
import time

service_slots = threading.Semaphore(2)


def call_service(name):
    with service_slots:
        print(name, "entered")
        time.sleep(1)
        print(name, "left")


threads = [
    threading.Thread(target=call_service, args=(f"task-{number}",))
    for number in range(5)
]

for thread in threads:
    thread.start()

for thread in threads:
    thread.join()
```

At most two workers can be inside the `with service_slots:` block. A lock is
effectively a one-permit tool; this semaphore has two permits.

### `Queue`: safely hand jobs between threads

A queue is useful when producers create jobs and consumers process them. The
threads share the queue rather than directly modifying each other's lists:

```python
import threading
from queue import Queue

jobs = Queue()


def consumer():
    while True:
        item = jobs.get()
        try:
            if item is None:
                return
            print("processed", item)
        finally:
            jobs.task_done()


thread = threading.Thread(target=consumer)
thread.start()

for item in ["A", "B", "C"]:
    jobs.put(item)

jobs.put(None)  # sentinel: no more jobs
jobs.join()     # wait until every queued item received task_done()
thread.join()   # wait until the consumer function returns
```

- `put(item)` places a message in the protected inbox.
- `get()` waits for and removes one message.
- `task_done()` says that one removed message is finished.
- `join()` waits until all queued messages are marked finished.
- `None` is a sentinel: an agreed message telling the consumer to exit.

Use `Queue(maxsize=10)` to make producers wait when ten unprocessed messages
are already buffered. This prevents unlimited memory growth.

### Thread tools versus asyncio tools

Use `threading.Lock`, `threading.Event`, and `queue.Queue` among OS threads. Use
`asyncio.Lock`, `asyncio.Event`, and `asyncio.Queue` among tasks running on an
event loop. They express similar ideas, but asyncio versions wait with `await`
instead of blocking the event-loop thread.

### Safety rules

- Every participant must use the same lock for the same invariant.
- Keep critical sections small.
- Acquire multiple locks in one consistent order to reduce deadlock risk.
- Avoid holding a lock during slow I/O.
- Do not share one iterator among free-running threads without coordination;
  duplicate or missing elements may result.
- Prefer immutable data, per-worker data, queues, and returned results.
- Daemon threads may be stopped abruptly at shutdown. Prefer non-daemon threads
  and an explicit stop signal for important work.

### Free-threaded package compatibility

CPython protects its own internal state in a free-threaded build, but application
data still needs synchronization.

An extension module that has not declared free-threading support normally emits
a warning and re-enables the GIL. Forcing `-X gil=0` overrides that fallback;
only do so when the extension explicitly supports it.

Compatibility is version-specific:

- [NumPy free-threading and thread-safety guidance](https://numpy.org/doc/stable/reference/thread_safety.html)
- [pandas thread-safety guidance](https://pandas.pydata.org/pandas-docs/stable/user_guide/gotchas.html#thread-safety)
- [scikit-learn free-threaded Python 3.14 support](https://scikit-learn.org/stable/whats_new/v1.8.html#free-threaded-cpython-3-14-support)

Even a compatible library may expose mutable objects that are unsafe to modify
concurrently.

---

## 12. Choose the correct concurrency model

| Situation | Start with | Reason |
|---|---|---|
| Normal sequential dependency | Direct calls | Later work needs earlier result |
| Blocking files, network, or database calls | `ThreadPoolExecutor` | Waiting periods overlap |
| Many async-compatible I/O operations | `asyncio` | Many tasks share one event-loop thread |
| Pure-Python CPU work with the GIL enabled | `ProcessPoolExecutor` | Separate interpreters use several cores |
| Independent CPU work on compatible free-threaded Python | `ThreadPoolExecutor` | Python threads may run in parallel |
| Isolated CPU work on Python 3.14+ | `InterpreterPoolExecutor` | Separate interpreters in worker threads |

Decision process:

1. Determine whether the task mostly waits or calculates.
2. Determine whether individual jobs can run independently.
3. Identify all shared mutable state.
4. Check whether the active interpreter has the GIL enabled.
5. Check extension-library compatibility.
6. Start with a bounded worker count.
7. Collect results and exceptions.
8. Define shutdown and cancellation behavior.
9. Measure a correct sequential baseline and the concurrent version.

---

## 13. Measure performance correctly

Use a monotonic high-resolution clock for elapsed time:

```python
import time

started = time.perf_counter()
result = do_work()
elapsed = time.perf_counter() - started

print(f"Elapsed: {elapsed:.3f} seconds")
```

Fair benchmark rules:

- Compare implementations that produce the same correct result.
- Use the same amount of work and the same interpreter build.
- Include a sequential baseline.
- Run each case several times and compare medians.
- Alternate test order to reduce warm-up and background-load bias.
- Do not treat one machine's result as a universal guarantee.
- Distinguish wall-clock time from total CPU time.

Useful measurements:

```text
speedup    = sequential time / parallel time
efficiency = speedup / worker count
```

Parallel speedup is limited by serial work and overhead. Amdahl's law estimates:

```text
maximum speedup = 1 / ((1 - P) + P / N)
```

- `P` is the fraction that can run in parallel.
- `N` is the worker count.
- `1 - P` is the serial fraction.

If 90% can run in parallel and 10% must remain serial, unlimited workers still
cannot exceed a ten-times speedup.

---

## Repository examples

Run these in order:

1. [`fib.py`](multiprocessing/fib.py) — independent CPU work with raw threads.
2. [`counter_buggy.py`](threading/counter_buggy.py) — lost updates caused by
   shared state.
3. [`counter_fixed.py`](threading/counter_fixed.py) — correct locking with poor
   scalability.
4. [`counter_fixed_fast.py`](threading/counter_fixed_fast.py) — local state,
   executor results, and reduction.
5. [`worker.py`](multiprocessing/worker.py) — three asyncio tasks sharing one
   event-loop thread.
6. [`cpu_check.py`](multiprocessing/cpu_check.py) — Windows-only observation of
   the logical CPU scheduling one busy process; it runs until interrupted.

## Practice exercises

1. Run three one-second sleeps sequentially and measure the total.
2. Run them with raw threads using create-all/start-all/join-all.
3. Repeat with `ThreadPoolExecutor.map()`.
4. Change a worker to return a value and retrieve it from a future.
5. Raise a worker exception and observe raw thread versus future behavior.
6. Compare `fib.py` with the GIL enabled and disabled.
7. Reproduce the counter race, then repair it with a lock.
8. Compare locked shared counting with local counting and reduction.
9. Try one, two, four, eight, and sixteen CPU workers; calculate efficiency.
10. Rewrite the sleep example using native `asyncio`.
11. Wrap the original synchronous sleep function with `asyncio.to_thread()`.
12. Limit async work with a semaphore and bounded queue.
13. Run a CPU function through `ProcessPoolExecutor`.

## Further reading

- [Python concurrency overview](https://docs.python.org/3/library/concurrency.html)
- [`threading`](https://docs.python.org/3/library/threading.html)
- [`concurrent.futures`](https://docs.python.org/3.14/library/concurrent.futures.html)
- [`multiprocessing`](https://docs.python.org/3/library/multiprocessing.html)
- [`asyncio`](https://docs.python.org/3/library/asyncio.html)
- [Python free-threading guide](https://docs.python.org/3/howto/free-threading-python.html)
- [PEP 703: Making the GIL optional](https://peps.python.org/pep-0703/)
