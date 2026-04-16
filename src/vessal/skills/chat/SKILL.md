---
name: chat
description: Send and receive human messages
---

# chat

Send and receive messages. The signal shows recent conversation and unread count.

## Methods

chat.read(n=5) — Returns the last n messages and clears unread count
chat.reply(content, wait=0) — Sends a message. wait>0 blocks until a reply is received

## Usage

When a message arrives (signal shows unread):

```python
msgs = chat.read()
chat.reply("result processed")
```

When human confirmation is needed:

```python
answer = chat.reply("Continue?", wait=60)
```

Call sleep() after handling.
