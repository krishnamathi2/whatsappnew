# CipherLane Messenger User Guide

CipherLane Messenger is a browser-based encrypted chat app. It uses a local websocket relay to pass messages between users, then encrypts chat content in the browser with an ECDH key exchange and AES-GCM.

## What You Need

- A modern browser such as Microsoft Edge or Chrome.
- Python with the `websockets` package installed.
- Access to the `web` folder in this project.
- A relay URL. For local testing, use `ws://localhost:8765`.

Install the Python dependency if needed:

```powershell
pip install -r requirements.txt
```

## Start the App

Open two PowerShell windows in the project folder.

In the first window, start the websocket relay:

```powershell
python server.py
```

The relay should print:

```text
Server running on ws://localhost:8765
```

In the second window, serve the web app:

```powershell
python -m http.server 8000 --directory web
```

Open the app in your browser:

```text
http://localhost:8000
```

For quick UI-only viewing, you can open `web/index.html` directly. Messaging, service worker install, and some browser features work best through `http://localhost:8000`.

## First-Time Setup

1. Review the onboarding screens.
2. Click `Generate Seed` if a seed was not already generated.
3. Enter a strong `Seed passphrase`.
4. Click `Save Encrypted` to save the seed locally in this browser.
5. Copy the recovery phrase and store it somewhere private.

The seed creates your stable identity. The app can derive an identity ID from it, and that identity helps detect if a contact's identity changes later.

## Start a Secure Chat

For local testing, open the app in two browser windows or two different browser profiles.

In the first window:

1. Set `Server URL` to `ws://localhost:8765`.
2. Set `You` to `Alice`.
3. Set `Friend` to `Bob`.
4. Click `Connect`.

In the second window:

1. Set `Server URL` to `ws://localhost:8765`.
2. Set `You` to `Bob`.
3. Set `Friend` to `Alice`.
4. Click `Connect`.

After both users are connected, click `Start Secure` from either side. When the handshake completes, both sides should show a verification code. Compare the code out of band before sending sensitive messages.

## Send Messages

- Type in the message box and press `Enter`, or click `Send`.
- A single check means the message was sent.
- Double checks mean the peer reported delivery or read status.
- Typing status appears when the peer is composing a message.

If the send button says `Mic`, the message field is empty. Voice notes are not available yet.

## Friend Links

Use friend links to prefill connection details for someone else.

1. Enter your `Server URL` and `You` name.
2. Click `Create Friend Link`.
3. Click `Copy Link`.
4. Send the link to your friend.

When your friend opens the link, the app can fill in the relay and peer fields from the URL parameters.

## Contacts and New Chats

Use the `+` button to open chat options.

- `New contact` lets you save a name and friend link for quick access.
- `New group` and community-style flows are present in the UI, but group messaging is not fully available yet.

## Seed Recovery

Your seed is the recovery phrase for your identity. Keep it private.

To restore:

1. Paste your 12-word recovery phrase into `Recovery phrase appears here`.
2. Click `Restore From Phrase`.
3. Enter a passphrase.
4. Click `Save Encrypted` if you want this browser to remember the encrypted seed.

To unlock a seed already saved in this browser:

1. Enter the same seed passphrase used when saving it.
2. Click `Unlock Saved Seed`.

## Seed QR Transfer

Seed QR transfer is useful for moving your identity to another device.

To export:

1. Generate or restore your seed.
2. Click `Show Seed QR`.
3. Scan the QR from the other device.

To import:

1. Click `Import Seed QR`.
2. Choose an image containing the QR code.
3. Confirm that the identity ID is restored.

Some browsers do not support QR scanning through `BarcodeDetector`. If import fails, paste the recovery phrase manually.

## Install as an App

When the browser supports installation, click `Install App` in the left panel. In Edge, you can also use:

```text
Menu -> Apps -> Install this site as an app
```

Installation works best when the app is opened from `http://localhost:8000` or another web server, not directly from the file system.

## Troubleshooting

### Socket error or disconnected

- Confirm the relay is running with `python server.py`.
- Confirm the app field is set to `ws://localhost:8765`.
- Make sure each user has a unique `You` name.
- Restart the relay if a previous test left stale browser tabs connected.

### Target not online

- The friend name must exactly match the other user's `You` value.
- Both users must click `Connect` before starting the secure channel.

### Secure channel not ready

- Click `Start Secure` after both users are connected.
- Wait for the verification code to appear.
- If the peer identity changed warning appears, compare the verification code before continuing.

### Could not unlock seed

- Check the seed passphrase.
- If the saved encrypted seed is not available on this device, restore from the recovery phrase instead.

### Python does not start

- Install Python and add it to PATH.
- Recreate the virtual environment if `.venv` points to a missing Python install.
- Install dependencies with `pip install -r requirements.txt`.

## Security Notes

- The relay forwards messages, but chat content is encrypted in the browser after the secure handshake.
- Always compare the verification code with your friend through a trusted channel.
- Anyone with your recovery phrase can restore your identity. Store it offline or in a password manager.
- Use a strong seed passphrase. It protects the local encrypted seed stored in the browser.
- Local testing with `ws://localhost:8765` is not the same as production deployment. Use `wss://` behind TLS for remote use.
