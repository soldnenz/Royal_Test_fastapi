import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import './shared/Toast.css'
import App from './App.jsx'
import { BrowserRouter } from 'react-router-dom'
import { LoaderProvider } from './shared/LoaderContext'
import { ToastProvider } from './shared/ToastContext'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <LoaderProvider>
      <ToastProvider>
        <BrowserRouter basename="/admin">
          <App />
        </BrowserRouter>
      </ToastProvider>
    </LoaderProvider>
  </React.StrictMode>,
)
