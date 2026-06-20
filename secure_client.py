import asyncio
import base64
import json
import sys

import websockets
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import dh
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


# RFC 3526 Group 14 prime (2048-bit), shared by all clients.
GROUP14_PRIME_HEX = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AACAA68FFFFFFFFFFFFFFFF"
)
GROUP14_G = 2


class SecureChat:
    def __init__(self, client_name):
        self.client_name = client_name
        self.peer_name = None
        self.cipher = None
        self.websocket = None
        self.dh_parameters = self.build_shared_parameters()
        self.private_key = None
        self.public_key = None

    def build_shared_parameters(self):
        """Use a known shared DH group so both peers are compatible."""
        p = int(GROUP14_PRIME_HEX, 16)
        parameter_numbers = dh.DHParameterNumbers(p, GROUP14_G)
        return parameter_numbers.parameters(default_backend())

    def generate_keypair(self):
        """Generate private/public keypair."""
        self.private_key = self.dh_parameters.generate_private_key()
        self.public_key = self.private_key.public_key()

    def serialize_public_key(self):
        """Convert public key to bytes for sending."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def deserialize_public_key(self, pem_bytes):
        """Convert bytes back to public key."""
        return serialization.load_pem_public_key(pem_bytes, backend=default_backend())

    def compute_shared_secret(self, peer_public_key):
        """Compute shared secret using peer's public key."""
        shared_secret = self.private_key.exchange(peer_public_key)

        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"secure-chat-key",
            backend=default_backend(),
        )
        derived_key = hkdf.derive(shared_secret)
        fernet_key = base64.urlsafe_b64encode(derived_key)
        return Fernet(fernet_key)

    def encrypt_message(self, message):
        """Encrypt a message using the shared cipher."""
        if self.cipher:
            return self.cipher.encrypt(message.encode())
        return None

    def decrypt_message(self, encrypted):
        """Decrypt a message using the shared cipher."""
        if self.cipher:
            return self.cipher.decrypt(encrypted).decode()
        return None

    async def initiate_key_exchange(self, peer_name):
        """Start Diffie-Hellman key exchange with peer."""
        self.peer_name = peer_name
        self.generate_keypair()

        key_exchange_msg = {
            "type": "key_exchange",
            "from": self.client_name,
            "to": peer_name,
            "public_key": self.serialize_public_key().decode(),
        }
        await self.websocket.send(json.dumps(key_exchange_msg))
        print(f"[*] Sent public key to {peer_name}")

    async def handle_key_exchange(self, data, send_response):
        """Handle incoming public key and compute shared secret."""
        sender = data.get("from")
        if not sender:
            return

        self.peer_name = sender

        # Ensure we have our own keypair before computing the secret.
        if self.private_key is None:
            self.generate_keypair()

        peer_key_pem = data["public_key"].encode()
        peer_public_key = self.deserialize_public_key(peer_key_pem)

        self.cipher = self.compute_shared_secret(peer_public_key)
        print(f"[OK] Secure channel established with {sender}")

        if send_response:
            response_msg = {
                "type": "key_exchange_response",
                "from": self.client_name,
                "to": sender,
                "public_key": self.serialize_public_key().decode(),
            }
            await self.websocket.send(json.dumps(response_msg))
            print(f"[*] Sent public key response to {sender}")
        else:
            confirm_msg = {
                "type": "key_confirmed",
                "from": self.client_name,
                "to": sender,
            }
            await self.websocket.send(json.dumps(confirm_msg))

    async def receive_messages(self):
        """Listen for and process incoming messages."""
        try:
            async for raw_msg in self.websocket:
                data = json.loads(raw_msg)
                msg_type = data.get("type")

                if msg_type == "key_exchange":
                    await self.handle_key_exchange(data, send_response=True)

                elif msg_type == "key_exchange_response":
                    await self.handle_key_exchange(data, send_response=False)

                elif msg_type == "key_confirmed":
                    print(f"[OK] Secure channel confirmed with {data['from']}")

                elif msg_type == "chat":
                    if self.cipher:
                        decrypted = self.decrypt_message(data["content"].encode())
                        if decrypted is not None:
                            print(f"\n[{data['from']}]: {decrypted}")
                            print("You: ", end="", flush=True)
                    else:
                        print("\n[!] Received encrypted message before key exchange.")
                        print("You: ", end="", flush=True)

                elif msg_type == "error":
                    print(f"\n[!] Server error: {data.get('message', 'unknown error')}")
                    print("You: ", end="", flush=True)

        except Exception as exc:
            print(f"Connection error: {exc}")

    async def send_loop(self):
        """Handle user input and send encrypted messages."""
        loop = asyncio.get_running_loop()
        while True:
            msg = await loop.run_in_executor(None, sys.stdin.readline)
            if not msg:
                break

            cmd = msg.strip()
            if cmd.lower() == "/quit":
                break

            if cmd.startswith("/connect "):
                parts = cmd.split(maxsplit=1)
                if len(parts) == 2 and parts[1].strip():
                    await self.initiate_key_exchange(parts[1].strip())
                else:
                    print("Usage: /connect <friend_name>")
                    print("You: ", end="", flush=True)
                continue

            if cmd and self.cipher and self.peer_name:
                encrypted = self.encrypt_message(cmd)
                if encrypted:
                    chat_msg = {
                        "type": "chat",
                        "from": self.client_name,
                        "to": self.peer_name,
                        "content": encrypted.decode(),
                    }
                    await self.websocket.send(json.dumps(chat_msg))
            elif cmd and not cmd.startswith("/"):
                print("Use /connect <friend> first")
                print("You: ", end="", flush=True)

    async def start(self, server_url):
        """Main entry point."""
        print(f"Starting secure chat as '{self.client_name}'")
        print("Commands: /connect <friend_name> | /quit")
        print("You: ", end="", flush=True)

        async with websockets.connect(server_url) as ws:
            self.websocket = ws

            # Register with server
            await ws.send(json.dumps({"client_id": self.client_name}))
            _response = await ws.recv()

            # Start receive and send tasks together
            receive_task = asyncio.create_task(self.receive_messages())
            send_task = asyncio.create_task(self.send_loop())

            done, pending = await asyncio.wait(
                {receive_task, send_task}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            await asyncio.gather(*done, return_exceptions=True)


async def main():
    if len(sys.argv) != 2:
        print("Usage: python secure_client.py <your_name>")
        print("Example: python secure_client.py Alice")
        return

    client = SecureChat(sys.argv[1])
    await client.start("ws://localhost:8765")


if __name__ == "__main__":
    asyncio.run(main())
