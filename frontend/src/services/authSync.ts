/**
 * Cross-tab authentication state synchronization using BroadcastChannel.
 * Coordinates LOGIN, LOGOUT, and SESSION_INVALIDATED events across tabs in
 * the same browser profile and origin.
 *
 * NOTE: Sensitive access tokens are NEVER transmitted over the channel.
 */

export type AuthSyncMessage =
  | { type: 'LOGIN'; userId: string }
  | { type: 'LOGOUT' }
  | { type: 'SESSION_INVALIDATED' }

const CHANNEL_NAME = 'portfoliomind_auth'

let channel: BroadcastChannel | null = null

function getChannel(): BroadcastChannel | null {
  if (typeof window === 'undefined' || !('BroadcastChannel' in window)) {
    return null
  }

  if (!channel) {
    try {
      channel = new BroadcastChannel(CHANNEL_NAME)
    } catch {
      channel = null
    }
  }
  return channel
}

export function broadcastAuthEvent(message: AuthSyncMessage): void {
  try {
    const ch = getChannel()
    if (ch) {
      ch.postMessage(message)
    }
  } catch {
    // Ignore errors in environments where postMessage fails
  }
}

export function initAuthSync(onMessage: (message: AuthSyncMessage) => void): () => void {
  const ch = getChannel()
  if (!ch) return () => {}

  const handler = (event: MessageEvent<AuthSyncMessage>) => {
    if (event.data && typeof event.data.type === 'string') {
      onMessage(event.data)
    }
  }

  ch.addEventListener('message', handler)

  return () => {
    ch.removeEventListener('message', handler)
  }
}
