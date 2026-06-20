# CipherLane Closed Circle Design

## Purpose

CipherLane should become a secure closed-circle messenger for small trusted groups. A closed circle is an invite-only group where membership, device access, and message keys are controlled by the members rather than by a central account system.

The design extends the current one-to-one encrypted browser chat into group communication while preserving the existing product direction:

- seed-derived identity
- browser-local cryptography
- websocket relay for delivery only
- human-verifiable trust
- no phone-number or email identity requirement

This document is a technical design guide, not legal advice or a patent filing.

## Core Concept

The proposed mechanism is:

**Seed-Based Closed Circle Trust Graph With Rotating Group Epoch Keys**

Each user has a stable identity derived from their recovery phrase. Each device has its own device key. Each group has a signed membership state and an epoch key. Whenever membership changes, the group advances to a new epoch and creates a new group key.

This provides:

- removed members cannot read future messages
- new members cannot read old messages by default
- device restore requires explicit approval
- the relay cannot decrypt content
- users can verify membership changes

## Existing App Fit

Current app pieces that remain useful:

- `identity_id` derived from recovery phrase
- ECDH key exchange
- AES-GCM message encryption
- websocket relay in `server.py`
- browser UI in `web/index.html`
- verification code concept
- seed QR and restore flows

The new design adds a group layer on top of those pieces.

## Entities

### User Identity

A user identity is derived from the recovery phrase.

Fields:

- `identity_id`: stable public identifier, already derived as `cl-...`
- `identity_public_key`: long-term public signing key
- `identity_private_key`: long-term private signing key, derived or restored locally

Future improvement: use separate keys for signing and encryption instead of reusing one key type.

### Device

Each browser/device has a separate device key.

Fields:

- `device_id`: random UUID
- `device_public_key`: public key for this device
- `device_private_key`: private key stored locally
- `identity_id`: owner identity
- `approved_at_epoch`: group epoch where this device became trusted

Why this matters:

If a recovery phrase is restored on a new phone or browser, the identity may be the same, but the device is new. Existing members should approve that device before it receives group keys.

### Closed Circle

A closed circle is an encrypted group.

Fields:

- `circle_id`: random group ID
- `name`: encrypted or local-only group name
- `created_by`: creator identity ID
- `members`: approved identity IDs
- `devices`: approved devices per identity
- `admins`: identity IDs allowed to approve joins/removals
- `epoch`: current group key version
- `membership_state_hash`: hash of current membership state
- `membership_signatures`: signatures from admin or quorum

### Epoch

An epoch is a version of group membership and group encryption material.

Fields:

- `circle_id`
- `epoch_number`
- `created_at`
- `reason`: `create`, `member_added`, `member_removed`, `device_added`, `device_removed`, `key_refresh`
- `member_device_ids`
- `previous_epoch_hash`
- `epoch_public_summary`

Each epoch has a new symmetric group key:

- `group_epoch_key`

Messages are encrypted with the active epoch key.

## Key Model

### Identity Key

Used to prove the stable user identity.

Minimum MVP:

- derive identity ID from recovery phrase
- generate local signing key and store encrypted with seed passphrase

Better version:

- deterministically derive identity signing key from seed using HKDF
- never expose raw seed after restore/generation

### Device Key

Generated per browser install.

Used for:

- receiving encrypted epoch keys
- proving that a device belongs to an identity
- device approval flows

### Group Epoch Key

Generated when:

- group is created
- member joins
- member leaves
- member is removed
- device is added or revoked
- manual key refresh happens

Distributed by encrypting the new epoch key separately to each approved member device.

## Message Types

The relay should forward only typed JSON envelopes. The server does not need to understand encrypted payloads.

### `circle_invite`

Sent by admin to invite a user.

```json
{
  "type": "circle_invite",
  "circle_id": "circle_...",
  "from": "cl-admin",
  "to": "cl-invitee",
  "invite_id": "invite_...",
  "expires_at": 1770000000000,
  "payload": {
    "circle_name_hint": "Family",
    "admin_identity_id": "cl-admin",
    "join_token_hash": "..."
  },
  "signature": "..."
}
```

### `circle_join_request`

Sent by invited user.

```json
{
  "type": "circle_join_request",
  "circle_id": "circle_...",
  "from": "cl-invitee",
  "to": "cl-admin",
  "device_id": "device_...",
  "identity_public_key": {},
  "device_public_key": {},
  "join_token": "...",
  "signature": "..."
}
```

### `circle_join_approved`

Sent by admin after approval.

```json
{
  "type": "circle_join_approved",
  "circle_id": "circle_...",
  "from": "cl-admin",
  "to": "cl-invitee",
  "epoch": 2,
  "membership_state": {},
  "encrypted_epoch_key": {},
  "signature": "..."
}
```

### `circle_epoch_update`

Sent to all approved devices when membership changes.

```json
{
  "type": "circle_epoch_update",
  "circle_id": "circle_...",
  "epoch": 3,
  "from": "cl-admin",
  "to": "cl-member",
  "device_id": "device_...",
  "reason": "member_removed",
  "membership_state": {},
  "encrypted_epoch_key": {},
  "signature": "..."
}
```

### `circle_chat`

Encrypted group message.

```json
{
  "type": "circle_chat",
  "circle_id": "circle_...",
  "epoch": 3,
  "msg_id": "msg_...",
  "from": "cl-member",
  "to": "circle_...",
  "content": {
    "iv": "...",
    "ciphertext": "..."
  },
  "signature": "..."
}
```

## Invite Flow

1. Admin creates a closed circle.
2. App generates `circle_id` and epoch `1`.
3. App generates `group_epoch_key`.
4. Admin creates invite link or QR.
5. Invitee opens invite.
6. Invitee sends `circle_join_request` with identity and device public keys.
7. Admin sees verification code for invitee.
8. Admin approves.
9. Circle advances epoch.
10. New epoch key is encrypted to every approved device.
11. Invitee can now send and receive group messages.

## Human Verification

For non-technical users, verification should be short and visible.

Verification code input:

- circle ID
- invitee identity ID
- invitee device public key fingerprint
- admin identity ID
- epoch number

Display:

```text
Verify with Arun:
4821-9037
```

Members should compare this code out-of-band before approving sensitive groups.

## Member Removal

When removing a member:

1. Admin removes identity or device from membership state.
2. New epoch is created.
3. New `group_epoch_key` is generated.
4. Key is encrypted only to remaining approved devices.
5. Removed member can still possess old messages but cannot decrypt future messages.

This gives forward lockout from the removal point.

## New Device Approval

When a user restores their seed on a new browser:

1. Identity ID is restored.
2. New device key is generated.
3. Device sends `device_join_request`.
4. Existing member/admin approves the new device.
5. Group creates a new epoch or device-specific key grant.
6. New device receives current epoch key only after approval.

The app should never silently trust a new device just because it has the same recovery phrase.

## Relay Responsibilities

The relay should:

- register connected client IDs
- forward allowed message types
- reject oversized messages
- reject expired messages
- avoid storing message content
- avoid logging message bodies

The relay should not:

- decrypt messages
- decide group membership
- generate group keys
- store recovery phrases
- store seed passphrases

Future relay improvement:

- route by `device_id`, not only `identity_id`
- support offline encrypted message queues with short retention
- make logging configurable and off by default

## Browser Storage

Store locally:

- encrypted seed or identity private key
- device private key
- trusted contacts
- trusted circles
- membership state
- current epoch keys

Protect with:

- seed passphrase
- browser storage encryption using Web Crypto
- clear warning when storage is browser-local only

## MVP Scope

The first implementation should be deliberately narrow.

Build:

- create closed circle
- add one member by identity ID
- approve join request
- generate epoch key
- encrypt group message with AES-GCM
- send group message to all approved members through relay
- rotate epoch key when removing member
- show verification code

Do not build yet:

- large communities
- file sharing
- voice/video
- offline queues
- admin quorum
- multiple admins
- public discovery

## Implementation Plan

### Step 1: Data Structures

Add browser-side objects:

- `circles`
- `circleMembers`
- `circleDevices`
- `circleEpochs`
- `currentCircleId`
- `circleEpochKeys`

### Step 2: Relay Message Types

Extend `ALLOWED_TYPES` in `server.py`:

- `circle_invite`
- `circle_join_request`
- `circle_join_approved`
- `circle_epoch_update`
- `circle_chat`
- `device_join_request`
- `device_join_approved`

### Step 3: UI

Add:

- Create Circle
- Invite Member
- Pending Join Requests
- Approve Device
- Circle Members
- Remove Member
- Group chat view
- Verification code panel

### Step 4: Crypto Helpers

Add helpers:

- create group epoch key
- encrypt text with epoch key
- decrypt text with epoch key
- encrypt epoch key to device public key
- decrypt epoch key with device private key
- hash membership state
- sign membership state
- verify membership state signature

### Step 5: Group Send

For each approved member device:

- relay sends the same encrypted group message envelope
- message content remains encrypted with epoch key
- UI renders once per sender, not once per recipient

### Step 6: Epoch Rotation

On membership/device change:

- increment epoch
- generate new epoch key
- update membership state
- sign membership state
- distribute encrypted epoch key to remaining devices

## Threat Model

Protect against:

- relay reading messages
- removed members reading future messages
- accidental invite link reuse
- unknown device silently joining
- identity replacement without warning
- stale messages from old epochs

Not protected in MVP:

- compromised endpoint/browser
- malicious approved member screenshotting or forwarding content
- denial of service by relay
- traffic analysis by network observer
- fully anonymous routing
- formally audited cryptographic security

## Patent Review Notes

Potentially interesting technical mechanism:

**A browser-based closed group messaging method that combines seed-derived identity, per-device approval, human-verifiable join codes, signed membership state, relay-minimized delivery, and epoch-based group key rotation.**

Possible novelty areas to review:

- recovery phrase identity tied to closed-circle trust graph
- device approval before restored identities receive group keys
- human-readable verification code over membership and device state
- epoch key distribution without server-side group authority
- browser-local encrypted membership state and relay-only delivery

Known prior art to compare:

- Signal
- Session
- SimpleX Chat
- Element / Matrix
- Wire
- Threema

Do not make public novelty claims until a patent attorney reviews the final mechanism and prior art.

## Open Questions

- Should group approval require one admin or multiple existing members?
- Should new members get old message history?
- Should group names be encrypted from the relay?
- Should invite links be one-time only by default?
- Should offline messages be queued by relay or avoided in MVP?
- Should identity signing keys be deterministic from seed or randomly generated and backed up?
- Should the app support multiple devices per identity in the first group MVP?

## Recommended Next Step

Implement the MVP closed-circle flow in `web/index.html` and `server.py`:

1. Add circle message types to relay.
2. Add circle creation UI.
3. Add browser-side circle state.
4. Add join request and approval flow.
5. Add epoch key generation and encrypted group messages.
