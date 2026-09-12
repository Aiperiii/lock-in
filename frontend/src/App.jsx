import { Route, Routes } from 'react-router'
import BookPage from './pages/BookPage'
import LessonPage from './pages/LessonPage'
import LibraryPage from './pages/LibraryPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LibraryPage />} />
      <Route path="/books/:id" element={<BookPage />} />
      <Route path="/lessons/:id" element={<LessonPage />} />
    </Routes>
  )
}
