// Vitest alias: replaces `server-only` so unit tests can import
// server-side modules (lib/api/client.ts, lib/api/index.ts) without
// the runtime guard throwing. The actual guard is enforced by Next.js
// at build time; this file is only resolved during `npm test`.
export {};
