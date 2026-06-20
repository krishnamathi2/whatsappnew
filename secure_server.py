import asyncio
import json
import time

import websockets

# Store clients with their IDs
clients = {}  # {client_id: websocket}
MAX_MESSAGE_BYTES = 64 * 1024
MAX_CLOCK_SKEW_MS = 5 * 60 * 1000
ALLOWED_TYPES = {
    "key_exchange",
    "key_exchange_response",
    "key_confirmed",
    "chat",
    "chat_received",
    "chat_read",
    "typing",
}


def now_ms():
    return int(time.time() * 1000)


def is_fresh(data):
    expires_at = data.get("expires_at")
    if expires_at is None:
        return True
    if not isinstance(expires_at, int):
        return False
    return expires_at + MAX_CLOCK_SKEW_MS >= now_ms()


async def send_error(websocket, message):
    await websocket.send(json.dumps({"type": "error", "message": message}))


async def handler(websocket):
    client_id = None
    try:
        # Wait for client to identify itself
        msg = await websocket.recv()
        data = json.loads(msg)
        client_id = data.get("client_id")

        if isinstance(client_id, str) and client_id.strip():
            if client_id in clients and clients[client_id] != websocket:
                await clients[client_id].close(code=4000, reason="Duplicate client_id")
            clients[client_id] = websocket
            print(f"[+] client connected. Total: {len(clients)}")
            await websocket.send(json.dumps({"type": "connected", "message": "Welcome"}))
        else:
            await send_error(websocket, "Missing client_id")
            return

        # Forward messages between clients
        async for message in websocket:
            if len(message) > MAX_MESSAGE_BYTES:
                await send_error(websocket, "Message too large")
                continue

            data = json.loads(message)
            if data.get("type") not in ALLOWED_TYPES:
                await send_error(websocket, "Unsupported message type")
                continue

            if data.get("from") and data.get("from") != client_id:
                await send_error(websocket, "Sender does not match registered client")
                continue

            if not is_fresh(data):
                await send_error(websocket, "Expired message rejected")
                continue

            target = data.get("to")
            if target and target in clients:
                await clients[target].send(message)
            elif target:
                await send_error(websocket, "Target not online")
            else:
                await send_error(websocket, "Missing target")

    except Exception as exc:
        print(f"Connection error: {type(exc).__name__}")
    finally:
        if client_id and client_id in clients:
            del clients[client_id]
            print(f"[-] client disconnected. Total: {len(clients)}")


async def main():
    print("Secure Server running on ws://localhost:8765")
    async with websockets.serve(handler, "localhost", 8765):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
