import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import './index.css'
import { Layout } from './components/Layout'
import { SummaryPage } from './pages/SummaryPage'
import { PostsPage } from './pages/PostsPage'
import { SearchPage } from './pages/SearchPage'
import { PostDetailsPage } from './pages/PostDetailsPage'
import { DetectPage } from './pages/DetectPage'

const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <SummaryPage /> },
      { path: 'posts', element: <PostsPage /> },
      { path: 'posts/:postId', element: <PostDetailsPage /> },
      { path: 'search', element: <SearchPage /> },
      { path: 'detect', element: <DetectPage /> },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
)
