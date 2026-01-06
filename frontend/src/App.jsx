import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { 
  Send, Upload, Bot, User, Database, Settings, Layers, 
  Cpu, CheckCircle, AlertCircle, Loader2, Trash2, FileText, FolderOpen 
} from 'lucide-react'
import './index.css'

const API_URL = "http://localhost:8000"

function App() {
  const [tenantId, setTenantId] = useState("demo-corp")
  const [documents, setDocuments] = useState([]) // New State for Docs
  const [query, setQuery] = useState("")
  const [searchType, setSearchType] = useState("hybrid")
  const [chatHistory, setChatHistory] = useState([
    { 
      role: 'ai', 
      content: 'Hello! I am your Enterprise RAG assistant.\n\nI can use strategies like **Multi-Query Expansion** and **Decomposition** to answer complex questions.' 
    }
  ])
  const [isLoading, setIsLoading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState(null)
  
  const messagesEndRef = useRef(null)

  // --- Auto Scroll ---
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }
  useEffect(() => { scrollToBottom() }, [chatHistory])

  // --- 1. Fetch Documents (New) ---
  const fetchDocuments = async () => {
    try {
      const response = await fetch(`${API_URL}/api/v1/documents`, {
        headers: { "X-Tenant-ID": tenantId }
      })
      const data = await response.json()
      setDocuments(data.documents || [])
    } catch (error) {
      console.error("Failed to fetch documents", error)
    }
  }

  // Fetch docs whenever Tenant ID changes
  useEffect(() => {
    fetchDocuments()
  }, [tenantId])

  // --- 2. Upload Document ---
  const handleFileUpload = async (e) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    setUploadStatus({ type: 'loading', msg: 'Uploading...' })
    const formData = new FormData()
    formData.append("file", files[0])

    try {
      const response = await fetch(`${API_URL}/api/v1/ingest`, {
        method: "POST",
        body: formData,
        headers: { "X-Tenant-ID": tenantId }
      })
      if (response.ok) {
        setUploadStatus({ type: 'success', msg: 'Success! Document indexed.' })
        fetchDocuments() // Refresh list immediately after upload
      } else {
        setUploadStatus({ type: 'error', msg: 'Upload failed.' })
      }
    } catch (error) {
      setUploadStatus({ type: 'error', msg: 'Server error.' })
    }
    setTimeout(() => setUploadStatus(null), 3000)
  }

  // --- 3. Delete Document (New) ---
  const handleDeleteDocument = async (docId) => {
    if(!confirm("Are you sure you want to delete this document?")) return;

    try {
      const response = await fetch(`${API_URL}/api/v1/documents/${docId}`, {
        method: "DELETE",
        headers: { "X-Tenant-ID": tenantId }
      })
      if (response.ok) {
        // Remove from UI immediately (Optimistic update)
        setDocuments(prev => prev.filter(d => d.id !== docId)) 
      } else {
        alert("Failed to delete document")
      }
    } catch (error) {
      alert("Error deleting document")
    }
  }

  // --- 4. Chat Handler ---
  const sendMessage = async () => {
    if (!query.trim()) return
    const userMessage = { role: 'user', content: query }
    setChatHistory(prev => [...prev, userMessage])
    setQuery("")
    setIsLoading(true)

    try {
      const response = await fetch(`${API_URL}/api/v1/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: userMessage.content,
          tenant_id: tenantId,
          search_type: searchType
        })
      })
      const data = await response.json()
      
      let botResponse = { 
        role: 'ai', 
        content: "I couldn't find any relevant information.",
        thoughts: data.generated_queries || []
      }

      if (data.results && data.results.length > 0) {
        botResponse.content = data.results
          .slice(0, 3) 
          .map((r, i) => `**Source ${i + 1}** (Score: ${r.score.toFixed(2)})\n\n${r.content}`)
          .join('\n\n---\n\n')
      }
      setChatHistory(prev => [...prev, botResponse])
    } catch (error) {
      setChatHistory(prev => [...prev, { role: 'ai', content: "Error connecting to backend." }])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="app-container">
      {/* --- Left Sidebar (Controls) --- */}
      <aside className="sidebar">
        <div className="brand">
          <Database size={24} />
          <span>Enterprise RAG</span>
        </div>

        <div className="control-group">
          <div className="section-header"><Settings size={14}/> Strategy</div>
          <select 
            className="select-field" 
            value={searchType} 
            onChange={e => setSearchType(e.target.value)}
          >
            <option value="hybrid">Hybrid Search</option>
            <option value="multi_query">Multi-Query</option>
            <option value="decomposition">Decomposition</option>
            <option value="hyde">HyDE</option>
          </select>
        </div>

        <div className="control-group">
          <div className="section-header"><Layers size={14}/> Tenant ID</div>
          <input 
            className="input-field" 
            value={tenantId} 
            onChange={e => setTenantId(e.target.value)} 
          />
        </div>

        <div className="control-group">
          <div className="section-header"><Upload size={14}/> Ingest</div>
          <label className="upload-zone">
            <input type="file" hidden onChange={handleFileUpload} />
            <div style={{display:'flex', flexDirection:'column', alignItems:'center', gap: 5}}>
              <FileText size={20} />
              <span style={{fontSize:'0.8rem'}}>Click to Upload PDF/TXT</span>
            </div>
          </label>
          {uploadStatus && (
            <div className={`status-badge ${uploadStatus.type}`}>
              {uploadStatus.type === 'loading' && <Loader2 size={14} className="animate-spin" />}
              {uploadStatus.type === 'success' && <CheckCircle size={14} />}
              {uploadStatus.type === 'error' && <AlertCircle size={14} />}
              <span>{uploadStatus.msg}</span>
            </div>
          )}
        </div>
      </aside>

      {/* --- Main Chat Area --- */}
      <main className="main-area">
        <div className="messages-list">
          {chatHistory.map((msg, idx) => (
            <div key={idx} className="message-item">
              <div className={`avatar ${msg.role}`}>
                {msg.role === 'ai' ? <Bot size={20} /> : <User size={20} />}
              </div>
              <div className="message-content">
                {msg.thoughts && msg.thoughts.length > 0 && (
                  <div className="thought-process">
                    <div className="section-header" style={{marginBottom: '0.5rem'}}>
                      <Cpu size={14} /> AI Strategy: {searchType.replace('_', ' ').toUpperCase()}
                    </div>
                    <ul style={{margin:0, paddingLeft:20, color:'var(--text-secondary)'}}>
                      {msg.thoughts.map((t, i) => <li key={i}>{t}</li>)}
                    </ul>
                  </div>
                )}
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="message-item">
              <div className="avatar ai"><Bot size={20}/></div>
              <div className="message-content animate-pulse">Thinking...</div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-area">
          <div className="input-wrapper">
            <input 
              value={query} 
              onChange={e => setQuery(e.target.value)} 
              onKeyDown={handleKeyPress}
              placeholder="Ask a question about your documents..."
              disabled={isLoading}
            />
            <button className="send-btn" onClick={sendMessage} disabled={isLoading || !query.trim()}>
              <Send size={18} />
            </button>
          </div>
        </div>
      </main>

      {/* --- Right Sidebar (Documents) --- */}
      <aside className="docs-sidebar">
        <div className="section-header">
          <FolderOpen size={14}/> Knowledge Base
        </div>
        
        {documents.length === 0 ? (
          <div style={{textAlign:'center', color:'var(--text-secondary)', fontSize:'0.85rem', marginTop: 20}}>
            No documents found for this tenant.
          </div>
        ) : (
          documents.map(doc => (
            <div key={doc.id} className="doc-item">
              <div className="doc-info">
                <span className="doc-name" title={doc.filename}>{doc.filename}</span>
                <span className="doc-date">{doc.created_at}</span>
              </div>
              <button 
                className="delete-btn" 
                onClick={() => handleDeleteDocument(doc.id)}
                title="Delete Document"
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))
        )}
      </aside>
    </div>
  )
}

export default App