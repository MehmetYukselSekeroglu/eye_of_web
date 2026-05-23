import { useEffect, useState, useCallback, useRef } from 'react'

// Face Security v3 Flask sunucusu
const FACE_SEC_API = 'http://127.0.0.1:5007'

/**
 * 25 kameranın RTSP URL'sini düzenleme + test + .env atomic save için
 * React bileşeni. Eski Flask `web_templates/index.html` Ayarlar sekmesindeki
 * `#camTableBody` tablosunun JSX karşılığı.
 *
 * - GET /api/settings/cameras → satırları doldur
 * - POST /api/settings/cameras/test → satır bazında ✓/✗ rozet
 * - POST /api/settings/cameras → bulk URL kaydet (.env atomic)
 * - POST /api/settings/cam_enabled → checkbox auto-save
 * - POST /api/settings/startup_cam → radio auto-save
 *
 * Tema: var(--accent) yeşil + dark slate paletini kullanır; tüm renkler
 * inline style ile App.css değişkenleri üzerinden referans alır (mevcut
 * cam-btn paleti — değişken tanımları App.css'de tüm dashboard için ortak).
 */
export default function CameraSettings() {
  const [rows, setRows] = useState([])           // { id, name, url, enabled, is_startup, is_active }
  const [startupId, setStartupId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [msg, setMsg] = useState(null)          // { kind: 'ok'|'err', text: '...' }
  const [testStates, setTestStates] = useState({}) // { camId: 'wait'|'ok'|'fail' }
  const msgTimer = useRef(null)

  // İlk yükleme + tazeleme
  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${FACE_SEC_API}/api/settings/cameras`)
      if (!res.ok) throw new Error('HTTP ' + res.status)
      const data = await res.json()
      setRows(data.cameras || [])
      setStartupId(data.startup_id ?? null)
    } catch (err) {
      setError(
        'Yüz Güvenliği servisine bağlanılamadı (5007). ' +
        'Üst menüden ▶ BAŞLAT ile servisi açın.'
      )
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const showMsg = (kind, text) => {
    setMsg({ kind, text })
    clearTimeout(msgTimer.current)
    msgTimer.current = setTimeout(() => setMsg(null), 4500)
  }

  const updateRow = (id, patch) =>
    setRows(prev => prev.map(r => r.id === id ? { ...r, ...patch } : r))

  // Tekil URL Test
  const handleTest = async (id, url) => {
    if (!url) {
      setTestStates(s => ({ ...s, [id]: 'fail' }))
      return
    }
    setTestStates(s => ({ ...s, [id]: 'wait' }))
    try {
      const res = await fetch(`${FACE_SEC_API}/api/settings/cameras/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })
      const data = await res.json()
      setTestStates(s => ({ ...s, [id]: data.ok ? 'ok' : 'fail' }))
    } catch {
      setTestStates(s => ({ ...s, [id]: 'fail' }))
    }
  }

  // Enabled checkbox auto-save
  const handleEnabledToggle = async (id, enabled) => {
    updateRow(id, { enabled })
    try {
      await fetch(`${FACE_SEC_API}/api/settings/cam_enabled`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cam_id: id, enabled }),
      })
    } catch {
      showMsg('err', 'Etkinlik kaydedilemedi (servis kapalı?)')
    }
  }

  // Startup radio auto-save
  const handleStartupSelect = async (id) => {
    setStartupId(id)
    try {
      await fetch(`${FACE_SEC_API}/api/settings/startup_cam`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ startup_id: id }),
      })
    } catch {
      showMsg('err', 'Startup kamerası kaydedilemedi')
    }
  }

  // Tümünü kaydet (.env atomic)
  const handleSaveAll = async () => {
    const urls = {}
    rows.forEach(r => { urls[r.id] = (r.url || '').trim() })
    try {
      const res = await fetch(`${FACE_SEC_API}/api/settings/cameras`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ urls }),
      })
      const data = await res.json()
      if (res.ok && data.success) {
        showMsg('ok', `${data.count} kamera .env'e yazıldı.`)
        refresh()
      } else {
        showMsg('err', data.error || 'Bilinmeyen hata')
      }
    } catch (err) {
      showMsg('err', 'Sunucu hatası: ' + err.message)
    }
  }

  return (
    <aside className="right-panel cam-settings-panel">
      <div className="panel-head">
        KAMERA AYARLARI
        <button
          type="button"
          onClick={refresh}
          title="Tazele"
          style={{
            float: 'right',
            background: 'transparent',
            border: '1px solid #1e293b',
            color: '#60a5fa',
            padding: '2px 8px',
            borderRadius: 3,
            fontSize: 10,
            cursor: 'pointer',
          }}
        >↻</button>
      </div>

      {error && (
        <div className="cs-msg cs-msg-err" style={{ margin: '8px' }}>
          {error}
        </div>
      )}

      <div className="cs-table-wrap">
        {loading ? (
          <div className="cs-loading">Yükleniyor…</div>
        ) : rows.length === 0 && !error ? (
          <div className="cs-loading">Veri yok</div>
        ) : (
          <table className="cs-table">
            <thead>
              <tr>
                <th>#</th>
                <th>İsim</th>
                <th>RTSP URL</th>
                <th title="Etkin">E</th>
                <th title="Başlangıç">B</th>
                <th>Test</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id}>
                  <td className="cs-cell-id">
                    {r.id}
                    {r.is_active && (
                      <span className="cs-active-dot" title="Aktif kamera">●</span>
                    )}
                  </td>
                  <td className="cs-cell-name" title={r.name}>{r.name}</td>
                  <td>
                    <input
                      type="text"
                      className="cs-url-input"
                      value={r.url}
                      onChange={e => updateRow(r.id, { url: e.target.value })}
                      placeholder="rtsp://..."
                      spellCheck={false}
                    />
                  </td>
                  <td className="cs-cell-cb">
                    <input
                      type="checkbox"
                      checked={r.enabled}
                      onChange={e => handleEnabledToggle(r.id, e.target.checked)}
                    />
                  </td>
                  <td className="cs-cell-cb">
                    <input
                      type="radio"
                      name="cs-startup"
                      checked={startupId === r.id}
                      onChange={() => handleStartupSelect(r.id)}
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      className={`cs-test-btn cs-test-${testStates[r.id] || 'idle'}`}
                      onClick={() => handleTest(r.id, r.url)}
                      title="3sn timeout ile RTSP probe"
                    >
                      {testStates[r.id] === 'wait' ? '‥'
                        : testStates[r.id] === 'ok' ? '✓'
                          : testStates[r.id] === 'fail' ? '✗' : 'Test'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="cs-footer">
        <button
          type="button"
          className="cs-save-btn"
          onClick={handleSaveAll}
          disabled={loading || rows.length === 0}
        >
          💾 TÜMÜNÜ KAYDET (.env)
        </button>
        {msg && (
          <div className={`cs-msg cs-msg-${msg.kind}`}>
            {msg.text}
          </div>
        )}
      </div>
    </aside>
  )
}
