# Understanding sync operations

Let's proceed from the ground up and then map everything directly to our MCP client.

## 1. First: what problem does `async` solve?

Imagine your MCP client does this:

```python
result = session.call_tool("get_customer", {"customer_id": 1})
```

The client sends a request to the MCP server.

But the server might take:

* 10 ms
* 500 ms
* 5 seconds
* 30 seconds

During that time, your Python program is basically **waiting**.

The important question is:

> **While I'm waiting for the server, can Python do something else?**

With normal synchronous code, generally:

```text
Client
  |
  |---- request ----> Server
  |
  |     WAITING
  |     WAITING
  |     WAITING
  |
  |<---- response ----
  |
continue
```

With asynchronous programming:

```text
Client
  |
  |---- request ----> Server
  |
  |     WAITING
  |     
  |     "I can do other work"
  |
  |---- do other work ----
  |
  |<---- response --------
  |
continue
```

That's the fundamental reason `async` exists.

---

# 2. The three words you need to understand

There are really three concepts:

```python
async def
await
asyncio.run()
```

They have different responsibilities.

### `async def`

Means:

> "This function is asynchronous and can pause while waiting."

Example:

```python
async def get_customer():
    ...
```

### `await`

Means:

> "Wait for this asynchronous operation to finish, but don't block the entire event loop while waiting."

Example:

```python
customer = await get_customer()
```

### `asyncio.run()`

Means:

> "Start Python's asynchronous event loop and run this async function."

Example:

```python
asyncio.run(main())
```

Think:

```text
async def
   ↓
defines async work

await
   ↓
waits for async work

asyncio.run()
   ↓
starts the async world
```

---

# 3. The most important mental model: a restaurant

Imagine you are a waiter.

### Synchronous waiter

You take an order:

```text
Customer: "Give me coffee."

Waiter:
  Go to kitchen
  WAIT
  WAIT
  WAIT
  coffee ready
  return
```

While the coffee is being prepared, the waiter does nothing.

That's similar to synchronous blocking code.

---

### Asynchronous waiter

You take an order:

```text
Customer A: "Coffee"
          ↓
        kitchen

WAITING...

Instead of standing there:

Customer B: "Tea"
          ↓
        kitchen

Customer C: "Sandwich"
          ↓
        kitchen
```

When coffee is ready:

```text
Coffee ready
    ↓
serve A
```

The waiter didn't stop working while waiting.

That's asynchronous programming.

---

# 4. What does `async` actually mean?

Look at:

```python
async def main():
    print("Hello")
```

You might think:

> "`async` means Python runs this function in another thread."

**No.**

That's a very important misconception.

`async` does **not automatically create a thread**.

Instead, it creates a **coroutine function**.

For example:

```python
async def main():
    print("Hello")
```

Calling:

```python
main()
```

doesn't immediately execute the function like a normal function.

It produces a coroutine object.

Conceptually:

```text
main()
  ↓
Coroutine
```

Something needs to run that coroutine.

That's what:

```python
asyncio.run(main())
```

does.

---

# 5. What does `await` mean?

Suppose:

```python
async def get_data():
    ...
```

Then:

```python
result = await get_data()
```

means roughly:

> "I need the result of `get_data()`. While that operation is waiting, give the event loop an opportunity to run other asynchronous work."

That's why `await` is normally used with things that are **awaitable**, such as coroutines.

For example:

```python
async def get_customer():
    await something()
    return "Customer"
```

Then:

```python
customer = await get_customer()
```

---

# 6. Your MCP code

Now let's look at your code conceptually.

```python
async def main():

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            await session.initialize()

            tools = await session.list_tools()

            result = await session.call_tool(
                "get_customer",
                {
                    "customer_id": 1
                }
            )
```

There are **three different asynchronous concepts** here:

```text
async def
async with
await
```

Let's understand each.

---

# 7. Why is `main()` async?

You have:

```python
async def main():
```

Why?

Because inside `main()` you have:

```python
await session.initialize()
await session.list_tools()
await session.call_tool(...)
```

Python has a rule:

> You can only use `await` inside an `async def` function.

So this is valid:

```python
async def main():

    result = await something()
```

But this isn't:

```python
def main():

    result = await something()   # ❌
```

Therefore:

```python
async def main():
```

is necessary because your MCP operations are asynchronous.

---

# 8. Why is MCP using async?

This is where MCP becomes a great example.

Your MCP client is communicating with an MCP server:

```text
Python MCP Client
       |
       | communication
       ↓
MCP Server
       |
       ↓
Tool
```

Your client might need to:

```text
send request
      ↓
wait for server
      ↓
receive response
```

Communication is inherently I/O-heavy.

For example:

```python
await session.call_tool(...)
```

The client sends something like:

```text
"Call get_customer with customer_id = 1"
```

to the server.

The server might then:

```text
receive request
      ↓
query database
      ↓
wait for database
      ↓
process result
      ↓
send response
```

The client doesn't need to burn CPU while waiting.

So async is very useful.

---

# 9. Let's understand your first `await`

You have:

```python
await session.initialize()
```

Conceptually:

```text
Client
  |
  | initialize request
  ↓
MCP Server
  |
  | processing...
  |
  | processing...
  ↓
response
```

The client has to wait for the response.

So:

```python
await session.initialize()
```

means:

> "Start the initialization operation and wait until it completes, but allow the event loop to handle other asynchronous work while we're waiting."

---

# 10. Next one

```python
tools = await session.list_tools()
```

This is another asynchronous operation.

The client asks:

```text
"What tools does this MCP server provide?"
```

Server responds:

```text
get_customer
create_customer
delete_customer
...
```

So:

```python
tools = await session.list_tools()
```

means:

```text
Start list_tools()
        ↓
wait for response
        ↓
response arrives
        ↓
store response in tools
```

The important point:

### `await` returns the result.

For example:

```python
result = await something()
```

means:

```text
something()
   ↓
async operation
   ↓
wait
   ↓
result
```

---

# 11. Your most important line

This one:

```python
result = await session.call_tool(
    "get_customer",
    {
        "customer_id": 1
    }
)
```

Let's break it down.

You are asking the MCP server:

```text
Call the get_customer tool
with customer_id = 1
```

Communication might look like:

```text
CLIENT
  |
  | "call get_customer(customer_id=1)"
  |
  ↓
SERVER
  |
  | execute tool
  |
  | query database
  |
  | process result
  |
  ↓
CLIENT
  |
  | result
  ↓
result
```

Because the client needs to wait for the server:

```python
await session.call_tool(...)
```

is appropriate.

---

# 12. Now let's understand `async with`

This is a different concept.

You have:

```python
async with stdio_client(server_params) as (read, write):
```

Don't confuse:

```python
async with
```

with:

```python
await
```

They are related to asynchronous programming, but they solve different problems.

---

## Normal `with`

You've probably seen:

```python
with open("file.txt") as f:
    data = f.read()
```

The `with` statement manages a resource.

Conceptually:

```text
open resource
     ↓
use resource
     ↓
close resource
```

For example:

```python
with open(...) as file:
    ...
```

Python automatically handles cleanup.

---

# 13. Why `async with`?

Some resources themselves require asynchronous operations to open or close.

For example, your MCP communication channel.

You have:

```python
async with stdio_client(server_params) as (read, write):
```

Conceptually:

```text
start MCP server
       ↓
establish communication
       ↓
give me read/write streams
       ↓
use them
       ↓
close communication asynchronously
```

So:

```python
async with
```

means roughly:

> "Manage this resource using asynchronous setup and cleanup."

---

# 14. Your MCP structure

Your code essentially says:

```python
async def main():

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            await session.initialize()

            tools = await session.list_tools()

            result = await session.call_tool(...)
```

Visually:

```text
asyncio.run(main())
        │
        ▼
   async def main()
        │
        ▼
┌─────────────────────────────┐
│ async with stdio_client     │
│                             │
│   MCP communication starts  │
│             │               │
│             ▼               │
│   ┌─────────────────────┐   │
│   │ async with          │   │
│   │ ClientSession       │   │
│   │                     │   │
│   │ await initialize()  │   │
│   │        │            │   │
│   │        ▼            │   │
│   │ await list_tools()  │   │
│   │        │            │   │
│   │        ▼            │   │
│   │ await call_tool()   │   │
│   │                     │   │
│   └─────────────────────┘   │
│                             │
│ cleanup                     │
└─────────────────────────────┘
```

---

# 15. Finally, `asyncio.run(main())`

At the bottom:

```python
if __name__ == "__main__":
    asyncio.run(main())
```

This is the bridge between normal Python and asynchronous Python.

Your Python program starts normally.

Then:

```python
asyncio.run(main())
```

says:

> "Create an event loop, execute my `main()` coroutine, wait until it finishes, and then shut down the event loop."

Think of it as:

```text
Normal Python world
       |
       ↓
asyncio.run()
       |
       ↓
ASYNC WORLD
       |
       ├── main()
       ├── await operation
       ├── await operation
       └── await operation
```

---

# 16. The event loop — the missing piece

This is probably the most important concept for you to understand.

When you use:

```python
asyncio
```

there is an **event loop**.

Think of it as a manager.

Suppose you have:

```python
async def task1():
    await something()

async def task2():
    await something_else()
```

The event loop manages them.

Conceptually:

```text
             EVENT LOOP
                 │
        ┌────────┼────────┐
        ↓        ↓        ↓
      Task 1   Task 2   Task 3
        │        │        │
      waiting  running  waiting
        │        │
        │        ↓
        │      waiting
        │        │
        ↓        ↓
      resume   resume
```

When one task reaches:

```python
await something()
```

and `something()` is waiting for I/O, the event loop can work on another task.

---

# 17. A simple example

Consider:

```python
import asyncio

async def task1():
    print("Task 1 started")
    await asyncio.sleep(3)
    print("Task 1 finished")

async def task2():
    print("Task 2 started")
    await asyncio.sleep(1)
    print("Task 2 finished")

async def main():
    await asyncio.gather(task1(), task2())

asyncio.run(main())
```

You might expect:

```text
Task 1 started
(wait 3 seconds)
Task 1 finished

Task 2 started
(wait 1 second)
Task 2 finished
```

But that's not what happens.

Instead:

```text
Task 1 started
Task 2 started

(wait)

Task 2 finished

(wait)

Task 1 finished
```

Because when Task 1 reaches:

```python
await asyncio.sleep(3)
```

it effectively says:

> "I'm waiting. Event loop, you can work on something else."

So the event loop starts Task 2.

---

# 18. Why `await` doesn't mean "do it concurrently"

This is another common misconception.

Consider:

```python
await task1()
await task2()
```

This does **not** mean task1 and task2 run concurrently.

It means:

```text
task1
  ↓
wait until task1 finishes
  ↓
task2
  ↓
wait until task2 finishes
```

If you want concurrent execution:

```python
await asyncio.gather(
    task1(),
    task2()
)
```

Now:

```text
       Event Loop
           |
     ┌─────┴─────┐
     ↓           ↓
   task1       task2
     │           │
   await       await
     │           │
     └─────┬─────┘
           ↓
       both finish
```

This distinction is extremely important when building MCP clients/servers.

---

# 19. When should YOU use `async`?

As a practical rule:

Use `async def` when your function needs to perform **asynchronous I/O** or call asynchronous functions.

Examples:

### HTTP request

```python
async def get_data():
    response = await client.get(...)
```

### Database query

```python
async def get_customer():
    result = await db.execute(...)
```

### MCP

```python
async def call_mcp_tool():
    result = await session.call_tool(...)
```

### File/network stream

```python
async def read_data():
    data = await stream.read(...)
```

The common theme:

> **Something outside your Python process needs to respond.**

---

# 20. When should you use normal `def`?

If your function is purely computational:

```python
def calculate_total(items):
    return sum(items)
```

No reason to make it:

```python
async def calculate_total(items):
```

There is nothing to wait for.

Similarly:

```python
def square(x):
    return x * x
```

doesn't need async.

---

# 21. A very useful rule

Ask yourself:

> **"Does this operation involve waiting for something external?"**

If yes, async may be appropriate.

For example:

| Operation                      | Usually async? |
| ------------------------------ | -------------- |
| MCP tool call                  | ✅              |
| HTTP API request               | ✅              |
| Database query                 | ✅              |
| Socket communication           | ✅              |
| Waiting for network            | ✅              |
| Reading async stream           | ✅              |
| `x + y`                        | ❌              |
| Sorting a list                 | ❌              |
| Calculating embeddings locally | Usually ❌      |
| Simple Python calculation      | ❌              |

---

# 22. One subtle but VERY important point

Don't think:

> "If something takes a long time, I should use async."

That's not exactly correct.

Suppose:

```python
def calculate():
    for i in range(10_000_000_000):
        ...
```

This is CPU-intensive.

Making it:

```python
async def calculate():
    for i in range(10_000_000_000):
        ...
```

doesn't magically make it asynchronous.

There is no `await`.

The event loop can still be blocked.

Async is primarily useful for **waiting**, particularly I/O waiting.

For CPU-heavy work, you might need:

* multiprocessing
* worker processes
* threads in some cases
* specialized compute libraries

---

# 23. Let's translate your entire MCP code into English

Your code:

```python
async def main():

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            await session.initialize()

            tools = await session.list_tools()

            print("Available tools:")

            for tool in tools.tools:
                print("-", tool.name)

            result = await session.call_tool(
                "get_customer",
                {"customer_id": 1}
            )

            print(result)
```

In plain English:

> **Define an asynchronous main function.**

```python
async def main():
```

> **Asynchronously establish communication with my MCP server and give me the read/write channels.**

```python
async with stdio_client(server_params) as (read, write):
```

> **Asynchronously create an MCP session using those communication channels.**

```python
async with ClientSession(read, write) as session:
```

> **Wait for the MCP initialization to complete.**

```python
await session.initialize()
```

> **Ask the MCP server for its available tools and wait for the response.**

```python
tools = await session.list_tools()
```

> **Call the `get_customer` tool and wait for its response.**

```python
result = await session.call_tool(...)
```

> **When the session and communication contexts finish, clean them up asynchronously.**

That's essentially the entire async story in your code.

---

# 24. One final mental model

When you see:

```python
async def
```

think:

> 🟢 **"This function participates in the async world."**

When you see:

```python
await
```

think:

> 🟡 **"I'm waiting for an async operation; event loop, you can handle other work while I wait."**

When you see:

```python
async with
```

think:

> 🔵 **"This resource needs asynchronous setup/cleanup."**

When you see:

```python
asyncio.run()
```

think:

> 🔴 **"Start the async world and run this coroutine."**

So your MCP code follows:

```text
asyncio.run(main())
        ↓
async def main()
        ↓
async with MCP connection
        ↓
async with MCP session
        ↓
await initialize()
        ↓
await list_tools()
        ↓
await call_tool()
        ↓
cleanup
```

### The key thing I recommend you learn next

Before going deeper into MCP, practice **one small example with 3 tasks**, first using:

```python
await task1()
await task2()
await task3()
```

and then:

```python
await asyncio.gather(
    task1(),
    task2(),
    task3()
)
```

Once you understand **why `gather()` changes the behavior**, the async architecture of MCP clients becomes much easier to understand.
