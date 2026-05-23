import { useEffect, useState, useCallback, useRef } from 'react'
import { Camera as CameraIcon, RefreshCw, Monitor } from 'lucide-react'

const FACE_SEC_API = 'http://127.0.0.1:5007'
const EXPRESS_API = 'http://localhost:5006'

/**
 * KONTROL sağ paneli — 25 kamera için tetik buton grid'i.
 *
 * AKIŞ DEĞİŞİKLİĞİ (2026-05-22):
 *   Önceki sürümde butona tıklayınca orta panele MJPEG <img> yerleşiyordu.
 *   Artık tıklama: Express `/api/control/launch-camera/:id` çağırır →
 *   kullanıcının makinesinde orijinal PyQt5 masaüstü penceresini açar
 *   (Milvus + PostgreSQL + Cyber HUD tüm özellikleri korunur).
 *
 * Bu bileşen artık SADECE BİR TETİKLEYİCİDİR; React state'inde "seçili
 * kamera" yok, orta panel her zaman harita.
 *
 * Veri kaynağı: Flask 5007 /api/settings/cameras (sadece id+name+url
 * listesi için; URL boş olanlar disabled gösterilir).
 *
 * Geri bildirim: butona tıklayınca `onLaunched({cam_id, name})` callback'i
 * çağırılır → App.jsx toast banner gösterir.
 */
export default function CamerasPanel({ onLaunched }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // Son tetiklenen cam_id — buton highlight (3sn flash)
  const [lastTriggered, setLastTriggered] = useState(null)
  const flashTimer = useRef(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${FACE_SEC_API}/api/settings/cameras`)
      if (!res.ok) throw new Error('HTTP ' + res.status)
      const data = await res.json()
      setRows(data.cameras || [])
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
  useEffect(() => {
    const id = setInterval(refresh, 15000)
    return () => clearInterval(id)
  }, [refresh])

  // Buton click → Express launch endpoint
  const handleLaunch = async (cam) => {
    setLastTriggered(cam.id)
    clearTimeout(flashTimer.current)
    flashTimer.current = setTimeout(() => setLastTriggered(null), 3000)
    try {
      const res = await fetch(`${EXPRESS_API}/api/control/launch-camera/${cam.id}`, {
        method: 'POST',
      })
      const data = await res.json()
      if (res.ok && data.success) {
        onLaunched?.({ id: cam.id, name: cam.name, kind: 'ok',
                        msg: data.message || `Kamera #${cam.id} başlatılıyor` })
      } else {
        onLaunched?.({ id: cam.id, name: cam.name, kind: 'err',
                        msg: data.error || `Başlatılamadı (${res.status})` })
      }
    } catch (err) {
      onLaunched?.({ id: cam.id, name: cam.name, kind: 'err',
                      msg: 'Express backend (5006) erişilemez: ' + err.message })
    }
  }

  return (
    <aside className="right-panel cameras-panel">
      <div className="panel-head">
        KAMERA SİSTEMİ
        <button
          type="button"
          className="cameras-refresh"
          onClick={refresh}
          title="Listeyi tazele"
          aria-label="Tazele"
        >
          <RefreshCw size={11} />
        </button>
      </div>

      <div className="cameras-info-bar">
        <Monitor size={11} color="#60a5fa" />
        <span>Masaüstü penceresi (PyQt5 + Milvus)</span>
      </div>

      {error && <div className="cameras-err">{error}</div>}

      <div className="cameras-grid">
        {loading && rows.length === 0 ? (
          <div className="cameras-loading">Yükleniyor…</div>
        ) : rows.length === 0 && !error ? (
          <div className="cameras-loading">Kamera tanımlı değil</div>
        ) : (
          rows.map(c => {
            const configured = !!c.url
            const flashing = lastTriggered === c.id
            const cls = [
              'cam-tile',
              configured ? 'cam-tile-on' : 'cam-tile-off',
              flashing ? 'cam-tile-launching' : '',
            ].filter(Boolean).join(' ')
            return (
              <button
                key={c.id}
                type="button"
                className={cls}
                disabled={!configured}
                onClick={() => configured && handleLaunch(c)}
                title={configured
                  ? `Masaüstü penceresini aç — ${c.name}`
                  : `${c.name} — .env'de URL tanımlı değil`}
              >
                <span className="cam-tile-id">#{c.id}</span>
                <CameraIcon
                  size={14}
                  color={flashing ? '#fbbf24' : (configured ? '#22c55e' : '#475569')}
                />
                <span className="cam-tile-name">{c.name}</span>
                {flashing && <span className="cam-tile-spinner" />}
              </button>
            )
          })
        )}
      </div>
    </aside>
  )
}
