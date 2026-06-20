import asyncio
import sys

import websockets
from cryptography.fernet import Fernet

# ============================================================
# STEP 1: Generate a shared key (run this once, then hardcode)
# ============================================================
# Uncomment the line below and run "python client.py" once.
# Then copy the printed key to the SHARED_KEY variable below.
# print(f"YOUR SECRET KEY: {Fernet.generate_key().decode()}")

# ============================================================
# PASTE YOUR GENERATED KEY HERE (both clients use SAME key)
# ============================================================
SHARED_KEY = b"81sml-JrfK4pMOsbkxJn5Bx5S4BeBoRrbyaO0LwhZ_o="
cipher = Fernet(SHARED_KEY)


async def receive_messages(websocket):
    """Listen for incoming messages and decrypt them."""
    try:
        async for encrypted_msg in websocket:
            try:
                decrypted = cipher.decrypt(encrypted_msg).decode()
                print(f"\n[Friend]: {decrypted}")
                print("You: ", end="", flush=True)
            except Exception:
                print("\n[!] Failed to decrypt message")
    except Exception:
        print("Connection closed")


async def send_messages(websocket):
    """Read user input, encrypt, and send."""
    loop = asyncio.get_running_loop()
    while True:
        msg = await loop.run_in_executor(None, sys.stdin.readline)
        if msg.strip().lower() == "/quit":
            break

        if msg.strip():
            encrypted = cipher.encrypt(msg.encode())
            await websocket.send(encrypted)


async def main():
    if SHARED_KEY == b"YOUR_SECRET_KEY_HERE":
        print("Please set SHARED_KEY in client.py before running.")
        return

    server = "ws://localhost:8765"
    print(f"Connecting to {server}...")
    print("Type messages. Type '/quit' to exit")
    print("You: ", end="", flush=True)

    async with websockets.connect(server) as websocket:
        receive_task = asyncio.create_task(receive_messages(websocket))
        send_task = asyncio.create_task(send_messages(websocket))

        done, pending = await asyncio.wait(
            {receive_task, send_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        await asyncio.gather(*done, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
