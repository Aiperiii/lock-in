// Thin fetch wrapper for the backend under /api (proxied by Vite in dev —
// see vite.config.js). One place for request/error handling, per CLAUDE.md's
// "one place" convention for the AI client — the same idea applies here.

async function request(path, options) {
  const res = await fetch(`/api${path}`, options)
  if (!res.ok) {
    throw new Error(`${options?.method ?? 'GET'} ${path} failed: ${res.status}`)
  }
  return res.json()
}

export function getHome() {
  return request('/home')
}

export function getBooks() {
  return request('/books')
}

export function getBook(id) {
  return request(`/books/${id}`)
}
