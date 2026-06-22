import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { 
  Send, Upload, Bot, User, Database, Layers, 
  Cpu, CheckCircle, AlertCircle, Loader2, Trash2, FolderOpen, FileText, PlusCircle, MessageSquare, Edit 
} from 'lucide-react'
import './index.css'

const API_URL = "http://localhost:8000"

// Native browser UUID generator
const generateUUID = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
};

function App() {
  const [tenantId, setTenantId] = useState("demo-corp")
  const [sessionId, setSessionId] = useState(generateUUID()) 
  const [chatList, setChatList] = useState([]) 
  
  const [documents, setDocuments] = useState([]) 
  const [query, setQuery] = useState("")
  const [chatHistory, setChatHistory] = useState([{ role: 'ai', content: 'Hello! I am your AI Assistant.' }])
  const [isLoading, setIsLoading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState(null)
  
  const [contextMenu, setContextMenu] = useState(null) 

  const messagesEndRef = useRef(null)
  useEffect(() => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }), [chatHistory])

  // --- 1. DEFINE HELPERS FIRST (To avoid hoisting issues) ---

  const handleNewChat = () => {
    setSessionId(generateUUID())
    setChatHistory([{ role: 'ai', content: 'Hello! New session started.' }])
  }

  const loadChat = async (id) => {
    setSessionId(id)
    try {
        const res = await fetch(`${API_URL}/api/v1/chats/${id}`, { headers: { "X-Tenant-ID": tenantId } })
        const data = await res.json()
        if (data.history) {
            const formatted = data.history.map(m => ({
                role: m.role, content: m.content, strategy_used: m.strategy
            }))
            setChatHistory(formatted)
        }
    } catch (e) { console.error(e) }
  }

  // --- 2. FETCH DATA (With Auto-Restore Logic) ---
  const fetchData = async () => {
    try {
        // Fetch Docs
        const docRes = await fetch(`${API_URL}/api/v1/documents`, { headers: { "X-Tenant-ID": tenantId } });
        const docData = await docRes.json();
        setDocuments(docData.documents || []);
        
        // Fetch Chats
        const chatRes = await fetch(`${API_URL}/api/v1/chats`, { headers: { "X-Tenant-ID": tenantId } });
        const chatData = await chatRes.json();
        setChatList(chatData || []);

        // --- NEW: AUTO-RESTORE LAST CHAT ---
        // If we have history, load the most recent one (index 0)
        // If not, start a new chat.
        if (chatData && chatData.length > 0) {
            // Check if we are already on a valid session, if not (e.g. refresh), load the top one
            // We simply force load the top one to be safe and consistent on refresh
            await loadChat(chatData[0].id)
        } else {
            handleNewChat()
        }

    } catch (e) { console.error(e); }
  }

  // --- 3. USE EFFECT ---
  useEffect(() => { fetchData() }, [tenantId])


  // --- 4. ACTIONS (Rename, Delete, Send) ---

  const deleteChat = async (id) => {
    if(!confirm("Are you sure you want to delete this chat?")) return;
    await fetch(`${API_URL}/api/v1/chats/${id}`, { method: "DELETE", headers: { "X-Tenant-ID": tenantId } })
    
    // Optimistic Update
    const remainingChats = chatList.filter(c => c.id !== id)
    setChatList(remainingChats)
    
    // If we deleted the active chat, switch to another or new
    if (sessionId === id) {
        if (remainingChats.length > 0) {
            loadChat(remainingChats[0].id)
        } else {
            handleNewChat()
        }
    }
    setContextMenu(null)
  }

  const renameChat = async (id, currentTitle) => {
    const newTitle = prompt("Enter new chat name:", currentTitle);
    if (!newTitle || !newTitle.trim()) return;

    try {
        const res = await fetch(`${API_URL}/api/v1/chats/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json", "X-Tenant-ID": tenantId },
            body: JSON.stringify({ title: newTitle })
        });
        
        if (res.ok) {
            setChatList(prev => prev.map(c => c.id === id ? { ...c, title: newTitle } : c));
        }
    } catch (e) { console.error(e) }
    setContextMenu(null)
  }

  const handleContextMenu = (e, chat) => {
    e.preventDefault()
    setContextMenu({ x: e.clientX, y: e.clientY, chat })
  }

  useEffect(() => {
    const handleClick = () => setContextMenu(null)
    window.addEventListener('click', handleClick)
    return () => window.removeEventListener('click', handleClick)
  }, [])

  const sendMessage = async () => {
    if (!query.trim()) return
    const userMessage = { role: 'user', content: query }
    const newHistory = [...chatHistory, userMessage]
    setChatHistory(newHistory)
    setQuery("")
    setIsLoading(true)

    try {
      const cleanHistory = newHistory.map(m => ({ role: m.role, content: m.content }))
      const response = await fetch(`${API_URL}/api/v1/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: userMessage.content,
          tenant_id: tenantId,
          session_id: sessionId, 
          chat_history: cleanHistory
        })
      })
      const data = await response.json()
      
      let botResponse = {
        role: 'ai',
        content: data.answer || "No info found.",
        strategy_used: data.strategy_used || data.mode,
        confidence: data.confidence,
        latency_ms: data.latency_ms,
        sources: data.sources || []
      }

      if (data.results?.length > 0 && !data.answer) {
         botResponse.content = data.results.map((r,i) => `**Src ${i+1}:** ${r.content}`).join('\n\n')
      }

      setChatHistory(prev => [...prev, botResponse])
      
      // Update chat list (to show new title or bump position)
      // We manually re-fetch chat list to see the update 'updated_at'
      const chatRes = await fetch(`${API_URL}/api/v1/chats`, { headers: { "X-Tenant-ID": tenantId } });
      const chatData = await chatRes.json();
      setChatList(chatData || []);

    } catch (e) { console.error(e) } 
    finally { setIsLoading(false) }
  }

  const handleFileUpload = async (e) => {
    const files = e.target.files
    if (!files.length) return
    setUploadStatus({type:'loading', msg:'Uploading'})
    const fd = new FormData(); fd.append("file", files[0])
    await fetch(`${API_URL}/api/v1/ingest`, { method: "POST", body: fd, headers: { "X-Tenant-ID": tenantId } })
    setUploadStatus({type:'success', msg:'Done'})
    
    // Refresh Docs
    const docRes = await fetch(`${API_URL}/api/v1/documents`, { headers: { "X-Tenant-ID": tenantId } });
    const docData = await docRes.json();
    setDocuments(docData.documents || []);
  }

  const handleDeleteDoc = async (id) => {
    if(!confirm("Delete?")) return
    await fetch(`${API_URL}/api/v1/documents/${id}`, { method: "DELETE", headers: { "X-Tenant-ID": tenantId } })
    const docRes = await fetch(`${API_URL}/api/v1/documents`, { headers: { "X-Tenant-ID": tenantId } });
    const docData = await docRes.json();
    setDocuments(docData.documents || []);
  }

  return (
    <div className="app-container">
      <aside className="sidebar">
        <div className="brand"><Database size={24}/> <span>Enterprise RAG</span></div>
        <button className="new-chat-btn" onClick={handleNewChat}><PlusCircle size={16}/> New Chat</button>

        <div className="chat-list-section">
            <div className="section-header" style={{marginTop:'1.5rem'}}><MessageSquare size={14}/> Recent Chats</div>
            <div className="chat-history-list">
                {chatList.map(chat => (
                    <div 
                        key={chat.id} 
                        className={`chat-row ${chat.id === sessionId ? 'active' : ''}`}
                        onClick={() => loadChat(chat.id)}
                        onContextMenu={(e) => handleContextMenu(e, chat)} 
                    >
                        {chat.title}
                    </div>
                ))}
            </div>
        </div>

        <div style={{marginTop:'auto'}}>
          <div className="control-group"><div className="section-header"><Layers size={14}/> Tenant ID</div><input className="input-field" value={tenantId} onChange={e => setTenantId(e.target.value)} /></div>
          <div className="control-group"><label className="upload-zone"><input type="file" hidden onChange={handleFileUpload} />Upload File</label></div>
        </div>
      </aside>

      <main className="main-area">
        <div className="messages-list">
          {chatHistory.map((msg, i) => (
             <div key={i} className="message-item">
                <div className={`avatar ${msg.role}`}>{msg.role==='ai'?<Bot size={20}/>:<User size={20}/>}</div>
                <div className="message-content">
                    {msg.role === 'ai' && (msg.strategy_used || msg.confidence != null) && (
                      <div className="answer-meta">
                        {msg.strategy_used && <span className="meta-badge">Mode: {msg.strategy_used}</span>}
                        {msg.confidence != null && (
                          <span className={`meta-badge confidence ${msg.confidence >= 0.55 ? 'high' : 'low'}`}>
                            Confidence: {(msg.confidence * 100).toFixed(0)}%
                          </span>
                        )}
                        {msg.latency_ms != null && <span className="meta-badge">{msg.latency_ms} ms</span>}
                      </div>
                    )}
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                    {msg.sources?.length > 0 && (
                      <div className="citations">
                        <div className="citations-title"><FileText size={13}/> Sources</div>
                        {msg.sources.map((s, idx) => (
                          <div key={s.chunk_id || idx} className="citation-item">
                            <span className="citation-index">[{idx + 1}]</span>
                            <span className="citation-file">{s.filename}</span>
                            <span className="citation-score">score {(s.retrieval_score ?? s.combined_score ?? 0).toFixed(3)}</span>
                            <div className="citation-snippet">{s.text_snippet}</div>
                          </div>
                        ))}
                      </div>
                    )}
                </div>
             </div>
          ))}
          {isLoading && <div className="message-item"><div className="avatar ai"><Bot size={20}/></div><div className="message-content">Thinking...</div></div>}
          <div ref={messagesEndRef} />
        </div>
        <div className="input-area">
          <div className="input-wrapper"><input value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>e.key==='Enter'&&sendMessage()}/><button className="send-btn" onClick={sendMessage}><Send size={18}/></button></div>
        </div>
      </main>

      <aside className="docs-sidebar">
        <div className="section-header"><FolderOpen size={14}/> Knowledge Base</div>
        {documents.map(d => (
            <div key={d.id} className="doc-item">
                <span className="doc-name">{d.filename}</span>
                <button className="delete-btn" onClick={() => handleDeleteDoc(d.id)}><Trash2 size={16}/></button>
            </div>
        ))}
      </aside>

      {contextMenu && (
        <div className="context-menu" style={{top: contextMenu.y, left: contextMenu.x}}>
            <div onClick={() => renameChat(contextMenu.chat.id, contextMenu.chat.title)} style={{display:'flex', alignItems:'center', gap:5}}>
                <Edit size={14}/> Rename
            </div>
            <div onClick={() => deleteChat(contextMenu.chat.id)} style={{color:'var(--danger)', display:'flex', alignItems:'center', gap:5}}>
                <Trash2 size={14}/> Delete
            </div>
        </div>
      )}
    </div>
  )
}
export default App