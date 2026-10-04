import { useState, useRef, useEffect } from 'react'
import Icon from '../Icon.jsx'
import './assistant.css'
import { API_BASE } from '../../services/apiBase.js'

const SUGGESTIONS = [
  "Explain a legal provision in simple language.",
  "Find Indian Supreme Court judgments related to freedom of speech.",
  "What legal remedies are available in a property dispute?",
  "Analyze a case scenario and identify relevant laws."
]

function ChatMessage({ msg, onSuggestionClick }) {
  const isUser = msg.role === 'user'
  
  return (
    <div className={`assistant-msg-wrapper ${isUser ? 'user' : 'ai'}`}>
      <div className="assistant-msg">
        {msg.content === '' && !isUser ? (
          <div className="typing-indicator">
            <div className="typing-dot"></div>
            <div className="typing-dot"></div>
            <div className="typing-dot"></div>
          </div>
        ) : (
          <div dangerouslySetInnerHTML={{ 
            __html: msg.content
              .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
              .replace(/\n/g, '<br/>') 
          }} />
        )}
      </div>
      
      {msg.sources && msg.sources.length > 0 && (
        <div className="assistant-sources">
          <h4>Sources & References</h4>
          {msg.sources.map((s, i) => (
            <div key={i} className="assistant-source-item">
              <strong>[{i + 1}] {s.case_name || s.title || 'Document'}</strong>
              {s.court && <span>Court: {s.court}</span>}
              {s.year && <span>Year: {s.year}</span>}
              {s.citation && <span>Citation: {s.citation}</span>}
            </div>
          ))}
        </div>
      )}

      {msg.showSuggestions && (
        <div className="assistant-suggestions">
          {SUGGESTIONS.map((s, i) => (
            <button 
              key={i} 
              className="assistant-suggestion-btn"
              onClick={() => onSuggestionClick(s)}
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function AssistantBubble() {
  const [isOpen, setIsOpen] = useState(false)
  const [isClosing, setIsClosing] = useState(false)
  
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Hello! I'm VIDHIVEDA AI, your legal research assistant. I can help you explore Indian laws, understand judicial decisions, discover relevant precedents, and summarize legal documents.",
      showSuggestions: true
    }
  ])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const bodyRef = useRef(null)

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight
    }
  }, [messages])

  const toggleOpen = () => {
    if (isOpen) {
      setIsClosing(true)
      setTimeout(() => {
        setIsOpen(false)
        setIsClosing(false)
      }, 200) // matches animation duration
    } else {
      setIsOpen(true)
    }
  }

  const sendMessage = async (text) => {
    if (!text.trim() || isLoading) return

    const newMsgs = [...messages]
    // hide suggestions on the welcome message
    if (newMsgs.length > 0 && newMsgs[0].showSuggestions) {
      newMsgs[0].showSuggestions = false
    }

    const userMsg = { role: 'user', content: text }
    const placeholderMsg = { role: 'assistant', content: '' }
    
    setMessages([...newMsgs, userMsg, placeholderMsg])
    setInputValue('')
    setIsLoading(true)

    try {
      const history = newMsgs.filter(m => !m.showSuggestions).map(m => ({ role: m.role, content: m.content }))
      
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          history: history,
          top_k: 5
        })
      })
      
      const data = await res.json()
      
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: 'assistant',
          content: data.answer || "Sorry, I couldn't process that.",
          sources: data.sources || []
        }
        return updated
      })
    } catch (err) {
      console.error(err)
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: 'assistant',
          content: "There was an error connecting to the server. Please try again later."
        }
        return updated
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(inputValue)
    }
  }

  return (
    <div className="assistant-bubble-container">
      {!isOpen && !isClosing && (
        <button 
          className="assistant-bubble-btn" 
          onClick={toggleOpen}
          aria-label="Open VIDHIVEDA AI"
        >
          <Icon name="sparkles" size={24} />
          <div className="assistant-tooltip">Ask VIDHIVEDA</div>
        </button>
      )}

      {(isOpen || isClosing) && (
        <div className={`assistant-window ${isClosing ? 'closing' : ''}`}>
          <header className="assistant-header">
            <div className="assistant-header-title">
              <div className="status-dot"></div>
              <div>
                <h3>VIDHIVEDA AI</h3>
                <small>Legal Research Assistant</small>
              </div>
            </div>
            <div className="assistant-header-actions">
              <button 
                className="assistant-icon-btn" 
                title="Clear Chat"
                onClick={() => setMessages([messages[0]])}
              >
                <Icon name="refresh" size={16} />
              </button>
              <button 
                className="assistant-icon-btn" 
                onClick={toggleOpen}
                title="Close"
              >
                <Icon name="close" size={18} />
              </button>
            </div>
          </header>

          <div className="assistant-body" ref={bodyRef}>
            {messages.map((msg, i) => (
              <ChatMessage 
                key={i} 
                msg={msg} 
                onSuggestionClick={(text) => sendMessage(text)} 
              />
            ))}
          </div>

          <footer className="assistant-footer">
            <div className="assistant-input-form">
              <textarea 
                className="assistant-input"
                placeholder="Ask anything about Indian laws, judgments..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
                rows={1}
              />
              <button 
                className="assistant-send-btn"
                onClick={() => sendMessage(inputValue)}
                disabled={!inputValue.trim() || isLoading}
              >
                <Icon name="arrow" size={16} />
              </button>
            </div>
            <p className="assistant-disclaimer">
              VIDHIVEDA AI provides research assistance, not legal advice.
            </p>
          </footer>
        </div>
      )}
    </div>
  )
}
