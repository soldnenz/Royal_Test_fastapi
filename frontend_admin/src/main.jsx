import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import './shared/Toast.css'
import App from './App.jsx'
import { BrowserRouter } from 'react-router-dom'
import { LoaderProvider } from './shared/LoaderContext'
import { ToastProvider } from './shared/ToastContext'
import ProtectedRoute from './components/ProtectedRoute'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <LoaderProvider>
      <ToastProvider>
        <BrowserRouter basename="/UDKeZNwbGVdH2iXEjkUFCkAuQb4Z1bbz">
          <ProtectedRoute>
            <App />
          </ProtectedRoute>
        </BrowserRouter>
      </ToastProvider>
    </LoaderProvider>
  </React.StrictMode>,
)
