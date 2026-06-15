// frontend/db.js
// Phase 2: all user-session storage lives in the browser's IndexedDB.
// The server is stateless with respect to user content. This module owns every
// IndexedDB operation; the rest of the app talks only to these functions.
import { openDB } from 'https://cdn.jsdelivr.net/npm/idb@8/build/index.js';

const DB_NAME = 'clauseguard';
const DB_VERSION = 1;

export async function getDB() {
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      // sessions: one entry per analysis run
      if (!db.objectStoreNames.contains('sessions')) {
        const store = db.createObjectStore('sessions', { keyPath: 'id' });
        store.createIndex('by_created', 'created_at');
      }
    },
  });
}

// Session shape:
// {
//   id: string (UUID, client-generated),
//   created_at: ISO string,
//   title: string (e.g. "LOA — EMPLOYER_AT_FAULT"),
//   contract_filenames: string[],
//   context_filenames: string[],
//   analysis: object (full API response),
//   entity_map: object | null,  // placeholder -> real value (for de-redaction)
//   verdict: string | null,
//   chat_context: string,       // Phase 3: raw chat context (client-side only)
//   feedback: object,           // Phase 5: { flagId: {value:'accurate'|'inaccurate', recorded_at} }
// }

export async function saveSession(session) {
  const db = await getDB();
  await db.put('sessions', session);
}

export async function getAllSessions() {
  const db = await getDB();
  return (await db.getAllFromIndex('sessions', 'by_created')).reverse();
}

export async function getSession(id) {
  const db = await getDB();
  return db.get('sessions', id);
}

export async function deleteSession(id) {
  const db = await getDB();
  return db.delete('sessions', id);
}

export async function clearAllSessions() {
  const db = await getDB();
  return db.clear('sessions');
}
