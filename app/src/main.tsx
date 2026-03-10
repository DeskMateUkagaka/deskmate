import { StrictMode, lazy, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/global.css'

const params = new URLSearchParams(window.location.search)
const windowType = params.get('window')

// Lazy import popup windows so their module-level code only runs in the correct window
const App = lazy(() => import('./App'))
const SettingsWindow = lazy(() => import('./windows/SettingsWindow').then(m => ({ default: m.SettingsWindow })))
const SkinPickerWindow = lazy(() => import('./windows/SkinPickerWindow').then(m => ({ default: m.SkinPickerWindow })))
const ChatInputWindow = lazy(() => import('./windows/ChatInputWindow').then(m => ({ default: m.ChatInputWindow })))

let content
switch (windowType) {
  case 'settings':
    content = <SettingsWindow />
    break
  case 'skin-picker':
    content = <SkinPickerWindow />
    break
  case 'chat-input':
    content = <ChatInputWindow />
    break
  default:
    content = <App />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Suspense fallback={null}>
      {content}
    </Suspense>
  </StrictMode>,
)
