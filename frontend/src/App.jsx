import { Route, Routes } from 'react-router'
import LibraryPage from './pages/LibraryPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LibraryPage />} />
    </Routes>
  )
}
