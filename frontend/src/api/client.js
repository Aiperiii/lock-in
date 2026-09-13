// Thin fetch wrapper for the backend under /api (proxied by Vite in dev —
// see vite.config.js). One place for request/error handling, per CLAUDE.md's
// "one place" convention for the AI client — the same idea applies here.

async function request(path, options) {
  const res = await fetch(`/api${path}`, options)
  if (!res.ok) {
    // FastAPI's HTTPException body is {"detail": "..."} — surface it when
    // present so callers can show the actual reason (e.g. "Only PDF uploads
    // are supported"), not just a status code.
    let detail
    try {
      detail = (await res.json()).detail
    } catch {
      // response wasn't JSON (or had no body) — fall through to the generic message
    }
    throw new Error(detail || `${options?.method ?? 'GET'} ${path} failed: ${res.status}`)
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

export function getBookStatus(id) {
  return request(`/books/${id}/status`)
}

export function uploadBook(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request('/books/upload', { method: 'POST', body: formData })
}

export function getLesson(id) {
  return request(`/lessons/${id}`)
}

export function answerQuestion(questionId, answer) {
  return request(`/questions/${questionId}/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answer }),
  })
}

export function generateQuiz({ bookId, chapterIds, difficulty, count }) {
  return request('/quizzes/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ book_id: bookId, chapter_ids: chapterIds, difficulty, count }),
  })
}

export function getQuiz(id) {
  return request(`/quizzes/${id}`)
}

export function askAI({ lessonId, selectedText, message, conversationId }) {
  return request('/ai/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      lesson_id: lessonId,
      selected_text: selectedText,
      message,
      conversation_id: conversationId,
    }),
  })
}
