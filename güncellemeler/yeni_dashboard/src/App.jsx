import { useState, useRef, useEffect, useCallback } from 'react'
import { Eye, Power, PowerOff, Camera, Terminal, Map, FileSearch, Search, AlertTriangle, ExternalLink, Image, Clock, Shield, Globe, Hash, Database, AtSign, Users, Play, ShieldCheck, Square, Cpu, Bell, Car, Settings as SettingsIcon } from 'lucide-react'
import Settings from './Settings'
import CamerasPanel from './CamerasPanel'
import './App.css'

const API = 'http://localhost:5006'
const POLL_INTERVAL = 2000 // ms

const CAMERAS = [
  { id: 1, name: 'Giriş Kapısı' },
  { id: 2, name: 'Otopark' },
  { id: 3, name: 'Ofis 1' },
  { id: 4, name: 'Ofis 2' },
  { id: 5, name: 'Eski Ofis' },
  { id: 6, name: 'S. Odası' },
  { id: 7, name: 'Buton 7' },
  { id: 8, name: 'Buton 8' },
  { id: 9, name: 'Buton 9' },
  { id: 10, name: 'Buton 10' },
]

// ─── MAIN APP ─────────────────────────────────────────────────────────────
export default function App() {
  const [systemActive, setSystemActive] = useState(false)
  const [activeCameras, setActiveCameras] = useState({}) // { name: true }
  const [selectedCamera, setSelectedCamera] = useState(null)
  // Kamera launcher toast (PyQt5 masaüstü pencere tetikleme feedback'i)
  const [launchToast, setLaunchToast] = useState(null) // { id, name, kind, msg } | null
  const [logs, setLogs] = useState(['>>> EYE OF WEB PANEL READY'])
  const [terminalInput, setTerminalInput] = useState('')

  // Tab state: 'control' (default) or 'report'
  const [activeTab, setActiveTab] = useState('control')

  // Report tab state
  const [reportQuery, setReportQuery] = useState('')
  const [reportLoading, setReportLoading] = useState(false)
  const [reportError, setReportError] = useState(null)
  const [reportData, setReportData] = useState(null)

  // Web tarama inputs
  const [webUrl, setWebUrl] = useState('')
  const [googleKeyword, setGoogleKeyword] = useState('')
  const [instagramUser, setInstagramUser] = useState('')
  // Instagram çoklu hedef (yeni): textarea — virgül/satır ayraçlı
  const [instagramTargets, setInstagramTargets] = useState('')
  const [instagramMaxPerTarget, setInstagramMaxPerTarget] = useState(20)
  const [instagramHeadless, setInstagramHeadless] = useState(true)

  // Face Security v3 — Flask web app subprocess launcher; iframe gömme
  const [faceSecStatus, setFaceSecStatus] = useState({
    running: false,           // subprocess canlı mı
    httpReady: false,         // Flask /api/status 200 mü → iframe yüklenebilir
    pid: null,
    iframeUrl: 'http://127.0.0.1:5007/',
  })
  const [faceSecBusy, setFaceSecBusy] = useState(false)

  const terminalRef = useRef(null)
  const prevLogCount = useRef(1)

  // ─── LOG POLLING ──────────────────────────────────────────────────────────
  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const res = await fetch(`${API}/api/logs`)
        if (!res.ok) return
        const data = await res.json()
        if (data.logs && data.logs.length !== prevLogCount.current) {
          prevLogCount.current = data.logs.length
          setLogs(data.logs)
        }
      } catch { /* backend henüz hazır değil */ }
    }

    fetchLogs()
    const id = setInterval(fetchLogs, POLL_INTERVAL)
    return () => clearInterval(id)
  }, [])

  // ─── CAMERA COUNT POLLING ─────────────────────────────────────────────────
  useEffect(() => {
    const fetchCameras = async () => {
      try {
        const res = await fetch(`${API}/api/camera/active`)
        if (!res.ok) return
        const data = await res.json()
        setActiveCameras(data.active || {})
      } catch { /* backend henüz hazır değil */ }
    }

    fetchCameras()
    const id = setInterval(fetchCameras, POLL_INTERVAL)
    return () => clearInterval(id)
  }, [])

  // ─── FACE SECURITY STATUS POLLING ─────────────────────────────────────────
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API}/api/face-security/status`)
        if (!res.ok) return
        const data = await res.json()
        setFaceSecStatus({
          running: !!data.running,
          httpReady: !!data.httpReady,
          pid: data.pid || null,
          iframeUrl: data.iframeUrl || 'http://127.0.0.1:5007/',
        })
      } catch { /* backend yok */ }
    }
    fetchStatus()
    const id = setInterval(fetchStatus, POLL_INTERVAL)
    return () => clearInterval(id)
  }, [])

  // ─── AUTO-SCROLL TERMINAL ─────────────────────────────────────────────────
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [logs])

  // ─── API HELPERS ──────────────────────────────────────────────────────────
  const apiPost = useCallback(async (endpoint, body = {}) => {
    try {
      const res = await fetch(`${API}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      return await res.json()
    } catch (err) {
      console.error(`API hatası [${endpoint}]:`, err.message)
      return null
    }
  }, [])

  // ─── SYSTEM ───────────────────────────────────────────────────────────────
  const handleStart = async () => {
    const data = await apiPost('/api/system/start')
    if (data?.success) setSystemActive(true)
  }

  const handleStop = async () => {
    const data = await apiPost('/api/system/stop')
    if (data?.success) {
      setSystemActive(false)
      setActiveCameras({})
      setSelectedCamera(null)
    }
  }

  // ─── FACE SECURITY START/STOP ──────────────────────────────────────────────
  const handleFaceSecStart = async () => {
    setFaceSecBusy(true)
    try {
      const data = await apiPost('/api/face-security/start')
      if (data?.success) setFaceSecStatus({ running: true, pid: data.pid })
      else if (data?.error) alert('Hata: ' + data.error)
    } finally {
      setTimeout(() => setFaceSecBusy(false), 1500)
    }
  }

  const handleFaceSecStop = async () => {
    if (!confirm('Yüz Güvenliği uygulamasını durdurmak istiyor musunuz?')) return
    setFaceSecBusy(true)
    try {
      const data = await apiPost('/api/face-security/stop')
      if (data?.success) setFaceSecStatus({ running: false, pid: null })
    } finally {
      setTimeout(() => setFaceSecBusy(false), 1500)
    }
  }

  // ─── CAMERA TOGGLE ────────────────────────────────────────────────────────
  const handleCameraToggle = async (cam) => {
    const data = await apiPost('/api/camera/toggle', { name: cam.name })
    if (data !== null) {
      setActiveCameras(prev => {
        const next = { ...prev }
        if (data.active) {
          next[cam.name] = true
          setSelectedCamera(cam)
        } else {
          delete next[cam.name]
          if (selectedCamera?.name === cam.name) setSelectedCamera(null)
        }
        return next
      })
    }
  }

  // ─── REPORT SEARCH ─────────────────────────────────────────────────────────
  const handleReportSearch = useCallback(async (e) => {
    e?.preventDefault()
    const id = reportQuery.trim()
    if (!id) return
    if (!/^\d+$/.test(id)) {
      setReportError('Geçersiz ID formatı. Sadece rakam girilmelidir.')
      setReportData(null)
      return
    }

    setReportLoading(true)
    setReportError(null)
    setReportData(null)

    try {
      const res = await fetch(`${API}/api/report/face/${id}`)
      const data = await res.json()
      if (!res.ok) {
        setReportError(data.error || 'Bilinmeyen hata')
      } else {
        setReportData(data)
      }
    } catch (err) {
      setReportError('Sunucuya bağlanılamadı: ' + err.message)
    } finally {
      setReportLoading(false)
    }
  }, [reportQuery])

  // ─── SCAN HANDLERS ────────────────────────────────────────────────────────
  const scan = {
    web: () => {
      if (!webUrl.trim()) {
        alert('Lütfen bir URL girin!')
        return
      }
      return apiPost('/api/scan/web', { url: webUrl.trim() })
    },
    auto:        () => apiPost('/api/scan/auto'),
    bot:         () => apiPost('/api/scan/bot'),
    google: () => {
      if (!googleKeyword.trim()) {
        alert('Lütfen bir anahtar kelime girin!')
        return
      }
      return apiPost('/api/scan/google', { keyword: googleKeyword.trim() })
    },
    instagram: () => {
      // Mevcut yazılım: kullanıcı adını Google üzerinden arar (insta BOT DEĞİL)
      if (!instagramUser.trim()) {
        alert('Lütfen bir kullanıcı adı girin!')
        return
      }
      return apiPost('/api/scan/instagram', { username: instagramUser.trim() })
    },
    instagramBot: () => {
      // YENİ Instagram BOT — Selenium tabanlı takipçi sıyırma
      const multi = instagramTargets.trim()
      if (!multi) {
        alert('Lütfen hedef kullanıcı adlarını girin (textarea)!')
        return
      }
      return apiPost('/api/scan/instagram-bot', {
        targets: multi,
        maxPerTarget: instagramMaxPerTarget,
        headless: instagramHeadless,
      })
    },
    facebook:    () => apiPost('/api/scan/facebook'),
    twitter:     () => apiPost('/api/scan/twitter'),
    twitterDump: () => apiPost('/api/scan/twitter-dump'),
  }

  // ─── TERMINAL INPUT ───────────────────────────────────────────────────────
  const handleTerminalSubmit = (e) => {
    e.preventDefault()
    if (!terminalInput.trim()) return
    // Just echo locally — no shell exec for arbitrary input
    setLogs(prev => [...prev, `>>> CMD: ${terminalInput}`])
    setTerminalInput('')
  }

  const activeCameraCount = Object.keys(activeCameras).length

  return (
    <div className="app-root">
      {/* ─── ÜST BAR ─── */}
      <header className="top-bar">
        <div className="status-col">
          <div className="status-row">
            <span className={`dot ${systemActive ? 'dot-green' : 'dot-red'}`} />
            <span className={systemActive ? 'status-green' : 'status-red'}>
              SİSTEM: {systemActive ? 'AKTİF' : 'KAPALI'}
            </span>
          </div>
          <div className="status-row">
            <span className={`dot ${activeCameraCount > 0 ? 'dot-green pulse' : 'dot-dim'}`} />
            <span className="status-green">AKTİF KAMERA: {activeCameraCount}</span>
          </div>
        </div>

        <div className="top-btns">
          <button
            className={`btn-tab ${activeTab === 'control' ? 'btn-tab-active' : ''}`}
            onClick={() => setActiveTab('control')}
          >
            <Camera size={13} /> KONTROL
          </button>
          <button
            className={`btn-tab ${activeTab === 'face-security' ? 'btn-tab-active' : ''}`}
            onClick={() => setActiveTab('face-security')}
          >
            <ShieldCheck size={13} /> YÜZ GÜVENLİĞİ
          </button>
          <button
            className={`btn-tab ${activeTab === 'instabot' ? 'btn-tab-active' : ''}`}
            onClick={() => setActiveTab('instabot')}
          >
            <AtSign size={13} /> INSTAGRAM BOT
          </button>
          <button
            className={`btn-tab ${activeTab === 'report' ? 'btn-tab-active' : ''}`}
            onClick={() => setActiveTab('report')}
          >
            <FileSearch size={13} /> RAPOR
          </button>
          <button
            className={`btn-tab ${activeTab === 'settings' ? 'btn-tab-active' : ''}`}
            onClick={() => setActiveTab('settings')}
          >
            <SettingsIcon size={13} /> AYARLAR
          </button>
          <button className="btn-stop" onClick={handleStop}>
            <PowerOff size={13} /> KAPAT
          </button>
          <button className="btn-run" onClick={handleStart}>
            <Power size={13} /> BAŞLAT
          </button>
        </div>
      </header>

      {/* ─── ANA İÇERİK ─── */}
      {activeTab === 'control' ? (
      <div className="main-area">

        {/* SOL PANEL */}
        <aside className="left-panel">
          <div className="panel-head">WEB TARAMA</div>

          {/* URL + 3 buton */}
          <section className="scan-block">
            <input
              className="field"
              placeholder="URL girin..."
              value={webUrl}
              onChange={e => setWebUrl(e.target.value)}
            />
            <button className="btn-action" onClick={scan.web}>▶ WEB TARAMA BAŞLAT</button>
            <button className="btn-action" onClick={scan.auto}>▶ OTOMATİK TARAMA</button>
            <button className="btn-action" onClick={scan.bot}>▶ BOT WEB TARAMA</button>
          </section>

          {/* Google */}
          <section className="scan-block">
            <span className="block-label">GOOGLE TARAMA</span>
            <input
              className="field"
              placeholder="Anahtar kelime..."
              value={googleKeyword}
              onChange={e => setGoogleKeyword(e.target.value)}
            />
            <button className="btn-scan" onClick={scan.google}>▶ TARAMAYA BAŞLA</button>
          </section>

          {/* Instagram (Google üzerinden, mevcut yazılım) */}
          <section className="scan-block">
            <span className="block-label">INSTAGRAM TARAMA</span>
            <input
              className="field"
              placeholder="Kullanıcı adı..."
              value={instagramUser}
              onChange={e => setInstagramUser(e.target.value)}
            />
            <button className="btn-scan" onClick={scan.instagram}>▶ TARAMAYA BAŞLA</button>
          </section>

          {/* INSTAGRAM BOT (TAKİPÇİ) bu sol menüden üst navbar sekmesine taşındı —
              Bkz. activeTab === 'instabot' bloğu. */}

          {/* Facebook */}
          <section className="scan-block">
            <span className="block-label">FACEBOOK TARAMA</span>
            <button className="btn-scan" onClick={scan.facebook}>▶ TARAMAYA BAŞLA</button>
          </section>

          {/* Twitter */}
          <section className="scan-block">
            <span className="block-label">TWITTER LİSTE TARAMA</span>
            <button className="btn-scan" onClick={scan.twitter}>▶ TARAMAYA BAŞLA</button>
          </section>

          {/* Twitter Dump */}
          <section className="scan-block">
            <span className="block-label">TWITTER LİSTE KAZIMA</span>
            <button className="btn-scan" onClick={scan.twitterDump}>▶ TARAMAYA BAŞLA</button>
          </section>
        </aside>

        {/* ORTA PANEL — Web MJPEG kaldırıldı; harita sabit. Kamera seçimi
            artık masaüstünde PyQt5 penceresi açar (Express launcher endpoint). */}
        <main className="center-panel">
          <div className="map-view">
            <div className="map-grid" />
            <img
              src={`${API}/api/image/map`}
              alt="Harita"
              className="map-img"
              onError={e => { e.target.style.display = 'none' }}
            />
            <div className="map-overlay">
              <Map size={36} color="#4b5563" />
              <div className="map-label">HARİTA GÖRÜNÜMÜ</div>
              <div className="map-sub">SAĞ PANELDEN KAMERA SEÇİN — masaüstü penceresi açılır</div>
            </div>
          </div>
        </main>

        {/* SAĞ PANEL — 25 kamera tetik buton grid'i.
            Tıklayınca Express /api/control/launch-camera/:id çağrılır →
            kullanıcının makinesinde orijinal PyQt5 masaüstü penceresi açar.
            Bu sayfa SADECE bir uzaktan kumandadır. */}
        <CamerasPanel
          onLaunched={info => {
            setLaunchToast(info)
            // 5sn sonra otomatik temizle
            setTimeout(() => {
              setLaunchToast(prev => (prev && prev.id === info.id ? null : prev))
            }, 5000)
          }}
        />
      </div>
      ) : activeTab === 'report' ? (
      /* ─── RAPOR SEKMESİ ─── */
      <div className="main-area report-area">
        <div className="report-container">
          {/* Arama Başlığı */}
          <div className="report-header">
            <FileSearch size={22} color="#3b82f6" />
            <span>FACE ID METADATA RAPORU</span>
          </div>

          {/* Arama Formu */}
          <form className="report-search-form" onSubmit={handleReportSearch}>
            <div className="report-input-wrap">
              <Search size={16} color="#6b8090" className="report-search-icon" />
              <input
                className="report-input"
                type="text"
                placeholder="Milvus Ref ID girin (örn: 464639026541365632)..."
                value={reportQuery}
                onChange={e => setReportQuery(e.target.value)}
              />
            </div>
            <button className="btn-report-search" type="submit" disabled={reportLoading}>
              {reportLoading ? '⏳ SORGULANYOR...' : '▶ SORGULA'}
            </button>
          </form>

          {/* Hata Mesajı */}
          {reportError && (
            <div className="report-error">
              <AlertTriangle size={16} />
              <span>{reportError}</span>
            </div>
          )}

          {/* Sonuçlar */}
          {reportData && (
            <div className="report-results">
              <div className="report-result-count">
                {reportData.count} kayıt bulundu
              </div>

              {reportData.results.map((row, idx) => (
                <div key={idx} className="report-card">
                  {/* Üst: Görsel + Kimlik Bilgileri */}
                  <div className="report-card-top">
                    {/* Thumbnail */}
                    <div className="report-thumb-wrap">
                      {row.image_binary_id ? (
                        <img
                          className="report-thumb"
                          src={`${API}/api/report/face-image/${row.image_binary_id}`}
                          alt="Yüz Görseli"
                          onError={e => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex' }}
                        />
                      ) : null}
                      <div className="report-thumb-placeholder" style={row.image_binary_id ? { display: 'none' } : {}}>
                        <Image size={32} color="#4b5563" />
                        <span>GÖRSEL YOK</span>
                      </div>
                    </div>

                    {/* Kimlik Bilgileri */}
                    <div className="report-identity">
                      <div className="report-id-row">
                        <Database size={13} color="#60a5fa" />
                        <span className="report-id-label">MILVUS REF ID</span>
                        <span className="report-id-value">{row.milvus_ref_id}</span>
                      </div>
                      <div className="report-id-row">
                        <Database size={13} color="#94a3b8" />
                        <span className="report-id-label">PG FACE ID</span>
                        <span className="report-id-value">{row.face_pg_id}</span>
                      </div>
                      <div className="report-id-row">
                        <Hash size={13} color="#94a3b8" />
                        <span className="report-id-label">IMAGE ID</span>
                        <span className="report-id-value">{row.image_main_id}</span>
                      </div>
                      <div className="report-id-row">
                        <Hash size={13} color="#94a3b8" />
                        <span className="report-id-label">HASH ID</span>
                        <span className="report-id-value">{row.hash_id}</span>
                      </div>
                    </div>
                  </div>

                  {/* Detay Grid */}
                  <div className="report-detail-grid">
                    {/* Kaynak URL */}
                    <div className="report-detail-item report-detail-full">
                      <div className="report-detail-label">
                        <ExternalLink size={12} /> KAYNAK URL
                      </div>
                      <div className="report-detail-value report-url">
                        {row.source_url ? (
                          <a href={row.source_url} target="_blank" rel="noopener noreferrer">{row.source_url}</a>
                        ) : (
                          <span className="report-na">Bilgi yok</span>
                        )}
                      </div>
                    </div>

                    {/* Başlık */}
                    <div className="report-detail-item report-detail-full">
                      <div className="report-detail-label">
                        <FileSearch size={12} /> SAYFA BAŞLIĞI
                      </div>
                      <div className="report-detail-value">
                        {row.image_title || <span className="report-na">Bilgi yok</span>}
                      </div>
                    </div>

                    {/* Domain */}
                    <div className="report-detail-item">
                      <div className="report-detail-label">
                        <Globe size={12} /> DOMAIN
                      </div>
                      <div className="report-detail-value">{row.base_domain || <span className="report-na">—</span>}</div>
                    </div>

                    {/* Tespit Tarihi */}
                    <div className="report-detail-item">
                      <div className="report-detail-label">
                        <Clock size={12} /> TESPİT TARİHİ
                      </div>
                      <div className="report-detail-value">
                        {row.face_detection_date
                          ? new Date(row.face_detection_date).toLocaleString('tr-TR')
                          : <span className="report-na">—</span>}
                      </div>
                    </div>

                    {/* Risk Seviyesi */}
                    <div className="report-detail-item">
                      <div className="report-detail-label">
                        <Shield size={12} /> RİSK SEVİYESİ
                      </div>
                      <div className="report-detail-value">
                        <span className={`report-risk report-risk-${(row.risk_level || 'unknown').toLowerCase()}`}>
                          {(row.risk_level || 'BİLİNMİYOR').toUpperCase()}
                        </span>
                      </div>
                    </div>

                    {/* Kategori */}
                    <div className="report-detail-item">
                      <div className="report-detail-label">
                        <Globe size={12} /> KATEGORİ
                      </div>
                      <div className="report-detail-value">{row.website_category || <span className="report-na">—</span>}</div>
                    </div>

                    {/* Kaynak */}
                    <div className="report-detail-item">
                      <div className="report-detail-label">
                        <Globe size={12} /> KAYNAK
                      </div>
                      <div className="report-detail-value">{(row.source || '—').toUpperCase()}</div>
                    </div>

                    {/* FaceID Array */}
                    <div className="report-detail-item">
                      <div className="report-detail-label">
                        <Database size={12} /> FACE ID ARRAY
                      </div>
                      <div className="report-detail-value report-mono">
                        {row.face_id_array ? `{${row.face_id_array.join(',')}}` : '—'}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Boş durum */}
          {!reportData && !reportError && !reportLoading && (
            <div className="report-empty">
              <Search size={40} color="#374151" />
              <div className="report-empty-title">FACE ID SORGULA</div>
              <div className="report-empty-sub">
                Milvus Ref ID girerek yüz kaydına ait tüm metadata bilgilerine ulaşabilirsiniz.
              </div>
            </div>
          )}
        </div>
      </div>
      ) : activeTab === 'face-security' ? (
      /* ─── YÜZ GÜVENLİĞİ SEKMESİ (Iframe — Flask web_app, port 5007) ─── */
      <div className="main-area face-sec-area" style={{ padding: '12px', display: 'flex', flexDirection: 'column', gap: '10px', height: '100%' }}>
        {/* Üst şerit — başlık + canlı durum + Başlat/Durdur */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '10px 16px',
            background: 'linear-gradient(90deg, rgba(34,197,94,0.18) 0%, rgba(16,185,129,0.08) 100%)',
            border: '1px solid #15803d',
            borderRadius: '8px',
            flexShrink: 0,
          }}
        >
          <ShieldCheck size={22} color="#22c55e" />
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: '14px', fontWeight: 700, color: '#ecfdf5', letterSpacing: '0.5px' }}>
              YÜZ GÜVENLİĞİ
            </span>
            <span style={{ fontSize: '10px', color: '#bbf7d0' }}>
              Flask web · 127.0.0.1:5007 · iframe → tarayıcı içi RTSP + InsightFace + ALPR
            </span>
          </div>

          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span
              style={{
                width: 9, height: 9, borderRadius: '50%',
                background: faceSecStatus.running ? '#22c55e' : '#475569',
                boxShadow: faceSecStatus.running ? '0 0 8px #22c55e' : 'none',
              }}
            />
            <span style={{ fontSize: '11px', color: faceSecStatus.running ? '#22c55e' : '#94a3b8', fontWeight: 600 }}>
              {faceSecStatus.running ? `ÇALIŞIYOR (pid ${faceSecStatus.pid})` : 'KAPALI'}
            </span>

            {faceSecStatus.running ? (
              <button
                onClick={handleFaceSecStop}
                disabled={faceSecBusy}
                style={{
                  background: 'linear-gradient(90deg, #dc2626 0%, #ef4444 100%)',
                  border: 'none', color: 'white',
                  padding: '6px 12px', borderRadius: '4px',
                  fontSize: '11px', fontWeight: 600, letterSpacing: '0.3px',
                  cursor: faceSecBusy ? 'wait' : 'pointer',
                  display: 'flex', alignItems: 'center', gap: '6px',
                  opacity: faceSecBusy ? 0.6 : 1,
                }}
              >
                <Square size={11} /> DURDUR
              </button>
            ) : (
              <button
                onClick={handleFaceSecStart}
                disabled={faceSecBusy}
                style={{
                  background: 'linear-gradient(90deg, #16a34a 0%, #22c55e 100%)',
                  border: 'none', color: 'white',
                  padding: '6px 12px', borderRadius: '4px',
                  fontSize: '11px', fontWeight: 600, letterSpacing: '0.3px',
                  cursor: faceSecBusy ? 'wait' : 'pointer',
                  display: 'flex', alignItems: 'center', gap: '6px',
                  opacity: faceSecBusy ? 0.6 : 1,
                }}
              >
                <Play size={11} /> BAŞLAT
              </button>
            )}
          </div>
        </div>

        {/* IFRAME — Flask web_app (5007) — sadece RUNNING iken render edilir */}
        <div
          style={{
            flex: 1,
            background: '#020617',
            border: '1px solid #1e293b',
            borderRadius: '8px',
            overflow: 'hidden',
            position: 'relative',
            minHeight: '500px',
          }}
        >
          {faceSecStatus.running && faceSecStatus.httpReady ? (
            <iframe
              src={faceSecStatus.iframeUrl}
              title="Yüz Güvenliği — Face Security v3 Web UI"
              style={{
                width: '100%',
                height: '100%',
                border: 'none',
                display: 'block',
              }}
            />
          ) : faceSecStatus.running ? (
            /* Process canlı ama Flask henüz cevap vermiyor → model yükleniyor */
            <div
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '14px',
                textAlign: 'center',
                color: '#94a3b8',
                padding: '32px',
              }}
            >
              <div
                style={{
                  width: 48, height: 48,
                  border: '4px solid #1e293b',
                  borderTopColor: '#22c55e',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite',
                }}
              />
              <div style={{ fontSize: '14px', color: '#cbd5e1', fontWeight: 600 }}>
                Flask sunucusu başlatılıyor…
              </div>
              <div style={{ fontSize: '11px', color: '#64748b', maxWidth: '380px' }}>
                InsightFace modeli yükleniyor (PID {faceSecStatus.pid}).
                127.0.0.1:5007 cevap verdiğinde iframe otomatik açılır.
              </div>
              <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            </div>
          ) : (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '14px',
                textAlign: 'center',
                color: '#94a3b8',
                padding: '32px',
              }}
            >
              <ShieldCheck size={56} color="#1e293b" />
              <div style={{ fontSize: '15px', color: '#cbd5e1', fontWeight: 600 }}>
                Yüz Güvenliği servisi kapalı
              </div>
              <div style={{ fontSize: '12px', color: '#64748b', maxWidth: '420px', lineHeight: 1.6 }}>
                Üstteki <strong style={{ color: '#22c55e' }}>BAŞLAT</strong> butonuna basın.
                Flask sunucusu <code style={{ color: '#fbcfe8' }}>127.0.0.1:5007</code>'de
                ayağa kalktığında bu pencerede RTSP kamera akışı, yüz tanıma sonuçları ve
                ALPR sekmesi tarayıcı içinde gözükecek.
              </div>
              <div
                style={{
                  marginTop: '12px',
                  padding: '10px 14px',
                  background: '#0f172a',
                  border: '1px solid #1e293b',
                  borderRadius: '4px',
                  fontSize: '10px',
                  color: '#fbbf24',
                  maxWidth: '500px',
                  textAlign: 'left',
                  display: 'flex',
                  gap: '8px',
                  alignItems: 'flex-start',
                }}
              >
                <AlertTriangle size={13} color="#fbbf24" style={{ flexShrink: 0, marginTop: 1 }} />
                <span>
                  İlk başlatmada InsightFace modeli yüklenir (~10-20sn).
                  İframe model hazır olduktan sonra otomatik yüklenir.
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Filtreli log şeridi — process lifecycle */}
        <div
          style={{
            background: '#020617',
            border: '1px solid #1e293b',
            borderRadius: '8px',
            padding: '10px 14px',
            flexShrink: 0,
            maxHeight: '140px',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div
            style={{
              color: '#22c55e',
              fontSize: '10px',
              fontWeight: 600,
              marginBottom: '6px',
              flexShrink: 0,
              display: 'flex',
              gap: '6px',
              alignItems: 'center',
              letterSpacing: '0.3px',
            }}
          >
            <Terminal size={11} /> FACE-SEC PROCESS LOG (son 30 satır)
          </div>
          <div
            style={{
              flex: 1,
              overflowY: 'auto',
              fontFamily: 'monospace',
              fontSize: '10px',
              color: '#94a3b8',
              lineHeight: 1.5,
            }}
          >
            {(() => {
              const lines = logs.filter(l => /FACE-SEC|YÜZ GÜVENLİĞİ/i.test(l)).slice(-30)
              if (lines.length === 0) {
                return <span style={{ color: '#475569', fontStyle: 'italic' }}>Henüz işlem yok.</span>
              }
              return lines.map((line, i) => {
                const isErr = /\[stderr\]|ERROR|Traceback|SPAWN HATASI/.test(line)
                const isClose = /KAPANDI|DURDURMA SİNYALİ/.test(line)
                let color = '#94a3b8'
                if (isErr) color = '#f87171'
                else if (isClose) color = '#fbbf24'
                return <div key={i} style={{ color }}>{line}</div>
              })
            })()}
          </div>
        </div>
      </div>
      ) : activeTab === 'settings' ? (
      /* ─── AYARLAR SEKMESİ — 3 alt sekmeli (Settings.jsx) ─── */
      <div className="main-area settings-area">
        <Settings />
      </div>
      ) : (
      /* ─── INSTAGRAM BOT SEKMESİ ─── */
      <div className="main-area instabot-area" style={{ padding: '24px', overflow: 'auto' }}>
        <div
          className="instabot-container"
          style={{
            maxWidth: '1100px',
            margin: '0 auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
          }}
        >
          {/* Başlık */}
          <div
            className="instabot-header"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '16px 20px',
              background: 'linear-gradient(90deg, rgba(192, 38, 211, 0.15) 0%, rgba(244, 114, 182, 0.10) 100%)',
              border: '1px solid #be185d',
              borderRadius: '8px',
            }}
          >
            <AtSign size={26} color="#ec4899" />
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: '16px', fontWeight: 700, color: '#fdf2f8', letterSpacing: '0.5px' }}>
                INSTAGRAM BOT — TAKİPÇİ SIYIRMA
              </span>
              <span style={{ fontSize: '11px', color: '#fbcfe8' }}>
                Selenium tabanlı OSINT aracı · güncellemeler/insta_bot/instagram_crawler.py
              </span>
            </div>
          </div>

          {/* Ana grid: sol = girdiler, sağ = ayarlar/durum */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '2fr 1fr',
              gap: '20px',
            }}
          >
            {/* Sol: hedef listesi */}
            <div
              style={{
                background: '#0f172a',
                border: '1px solid #1e293b',
                borderRadius: '8px',
                padding: '18px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  color: '#60a5fa',
                  fontSize: '12px',
                  fontWeight: 600,
                  letterSpacing: '0.5px',
                }}
              >
                <Users size={14} /> HEDEF KULLANICI LİSTESİ
              </div>
              <textarea
                className="field"
                placeholder={
                  'Hedef Instagram kullanıcı adlarını buraya girin.\n' +
                  'Virgül veya yeni satırla ayırın:\n\n' +
                  'natgeo\n' +
                  'nasa\n' +
                  'bbcnews'
                }
                rows={12}
                style={{
                  width: '100%',
                  resize: 'vertical',
                  fontFamily: 'monospace',
                  fontSize: '13px',
                  minHeight: '220px',
                  background: '#020617',
                  border: '1px solid #1e293b',
                  color: '#e2e8f0',
                  padding: '12px',
                  borderRadius: '6px',
                }}
                value={instagramTargets}
                onChange={e => setInstagramTargets(e.target.value)}
              />
              <div style={{ fontSize: '11px', color: '#64748b' }}>
                {instagramTargets.trim()
                  ? `${instagramTargets.replace(/[\n;]+/g, ',').split(',').map(s => s.trim()).filter(Boolean).length} hedef girildi`
                  : 'Henüz hedef girilmedi'}
              </div>
            </div>

            {/* Sağ: ayarlar + buton */}
            <div
              style={{
                background: '#0f172a',
                border: '1px solid #1e293b',
                borderRadius: '8px',
                padding: '18px',
                display: 'flex',
                flexDirection: 'column',
                gap: '14px',
              }}
            >
              <div
                style={{
                  color: '#60a5fa',
                  fontSize: '12px',
                  fontWeight: 600,
                  letterSpacing: '0.5px',
                }}
              >
                AYARLAR
              </div>

              <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '12px', color: '#94a3b8' }}>
                Hedef başına max takipçi
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={instagramMaxPerTarget}
                  onChange={e => setInstagramMaxPerTarget(parseInt(e.target.value, 10) || 20)}
                  style={{
                    background: '#020617',
                    border: '1px solid #1e293b',
                    color: '#e2e8f0',
                    padding: '8px 10px',
                    borderRadius: '4px',
                    fontSize: '13px',
                  }}
                />
              </label>

              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '12px',
                  color: '#94a3b8',
                  cursor: 'pointer',
                }}
              >
                <input
                  type="checkbox"
                  checked={instagramHeadless}
                  onChange={e => setInstagramHeadless(e.target.checked)}
                  style={{ width: '14px', height: '14px' }}
                />
                Headless (tarayıcı gizli) mod
              </label>

              <div style={{ flex: 1 }} />

              <button
                className="btn-scan"
                onClick={scan.instagramBot}
                style={{
                  background: 'linear-gradient(90deg, #db2777 0%, #ec4899 100%)',
                  border: 'none',
                  color: 'white',
                  padding: '12px 16px',
                  fontWeight: 700,
                  fontSize: '13px',
                  letterSpacing: '0.5px',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                <Play size={14} /> BOTU BAŞLAT
              </button>

              <div style={{ fontSize: '10px', color: '#64748b', lineHeight: 1.5 }}>
                Çıktılar alt konsola canlı akar (INSTABOT tag'iyle). Çıktı dosyası:{' '}
                <code style={{ color: '#fbcfe8' }}>güncellemeler/insta_bot/instagram_takipciler.txt</code>
              </div>
            </div>
          </div>

          {/* Bot konsolu — yalnız INSTABOT etiketli log satırlarını filtreler */}
          <div
            style={{
              background: '#020617',
              border: '1px solid #1e293b',
              borderRadius: '8px',
              padding: '16px',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                marginBottom: '10px',
                color: '#ec4899',
                fontSize: '12px',
                fontWeight: 600,
                letterSpacing: '0.5px',
              }}
            >
              <Terminal size={13} /> BOT KONSOL ÇIKTISI (CANLI)
            </div>
            <div
              style={{
                background: '#000',
                border: '1px solid #1e293b',
                borderRadius: '4px',
                padding: '12px',
                height: '320px',
                overflowY: 'auto',
                fontFamily: 'monospace',
                fontSize: '12px',
                color: '#94a3b8',
                lineHeight: 1.6,
              }}
            >
              {(() => {
                const botLines = logs.filter(l => /INSTABOT|INSTAGRAM BOT/i.test(l))
                if (botLines.length === 0) {
                  return (
                    <div style={{ color: '#475569', fontStyle: 'italic' }}>
                      Henüz bot çıktısı yok. "BOTU BAŞLAT"a basın — Selenium başlatıldığında bu pencere canlı satırlarla dolar.
                    </div>
                  )
                }
                return botLines.map((line, i) => {
                  const isErr = /\[ERR\]|\[FATAL\]|\[stderr\]/.test(line)
                  const isHit = /\[HIT\]/.test(line)
                  const isDone = /\[DONE\]|TAMAMLANDI|\[SUMMARY\]/.test(line)
                  let color = '#94a3b8'
                  if (isErr) color = '#f87171'
                  else if (isHit) color = '#34d399'
                  else if (isDone) color = '#60a5fa'
                  return (
                    <div key={i} style={{ color }}>
                      {line}
                    </div>
                  )
                })
              })()}
            </div>
          </div>
        </div>
      </div>
      )}

      {/* ─── TERMİNAL ─── */}
      <div className="terminal-wrap">
        <div className="terminal-head">
          <Terminal size={12} color="#00ff88" />
          KONSOL / LOG
        </div>
        <div className="terminal-body" ref={terminalRef}>
          {logs.map((line, i) => (
            <div key={i} className="log-line">{line}</div>
          ))}
        </div>
        <form className="terminal-input-row" onSubmit={handleTerminalSubmit}>
          <span className="term-prompt">{'>'}</span>
          <input
            className="term-field"
            value={terminalInput}
            onChange={e => setTerminalInput(e.target.value)}
            placeholder="komut girin..."
          />
        </form>
      </div>

      {/* GLOBAL TOAST — Kamera launcher feedback (her sekmeden görünür) */}
      {launchToast && (
        <div className={`launch-toast launch-toast-${launchToast.kind}`}>
          <div className="launch-toast-icon">
            {launchToast.kind === 'ok' ? '📷' : '⚠️'}
          </div>
          <div className="launch-toast-body">
            <div className="launch-toast-title">
              {launchToast.kind === 'ok'
                ? `Kamera #${launchToast.id} başlatılıyor`
                : `Kamera #${launchToast.id} hatası`}
            </div>
            <div className="launch-toast-msg">
              {launchToast.kind === 'ok'
                ? `${launchToast.name} — masaüstü penceresini kontrol edin.`
                : launchToast.msg}
            </div>
          </div>
          <button
            className="launch-toast-close"
            onClick={() => setLaunchToast(null)}
            aria-label="Kapat"
          >×</button>
        </div>
      )}
    </div>
  )
}
