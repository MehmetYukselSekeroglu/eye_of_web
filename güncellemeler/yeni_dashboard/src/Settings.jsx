import { useState } from 'react'
import { Settings as SettingsIcon, ShieldCheck, Camera, Sliders } from 'lucide-react'
import CameraSettings from './CameraSettings'

/**
 * Ana AYARLAR sayfası — üst navbar'dan ulaşılır, kendi içinde 3 alt sekmeli.
 *
 * Alt sekmeler:
 *   - Genel Ayarlar: yer tutucu (ileride global app ayarları)
 *   - Yüz Güvenliği: placeholder — Flask 5007 runtime config buraya bağlanacak
 *   - Kamera: KONTROL sayfasından taşınan <CameraSettings />
 *
 * Tasarım: dark/green tema, App.css'teki .settings-page-* class'larıyla.
 */
export default function Settings() {
  const [subTab, setSubTab] = useState('camera')   // default açılış: Kamera

  return (
    <div className="settings-page">
      {/* Üst başlık + alt sekme hap butonları */}
      <header className="settings-page-head">
        <div className="settings-page-title">
          <SettingsIcon size={20} color="#22c55e" />
          <span>AYARLAR</span>
        </div>

        <nav className="settings-subtabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={subTab === 'general'}
            className={`settings-subtab ${subTab === 'general' ? 'is-active' : ''}`}
            onClick={() => setSubTab('general')}
          >
            <Sliders size={13} /> Genel Ayarlar
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={subTab === 'face'}
            className={`settings-subtab ${subTab === 'face' ? 'is-active' : ''}`}
            onClick={() => setSubTab('face')}
          >
            <ShieldCheck size={13} /> Yüz Güvenliği
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={subTab === 'camera'}
            className={`settings-subtab ${subTab === 'camera' ? 'is-active' : ''}`}
            onClick={() => setSubTab('camera')}
          >
            <Camera size={13} /> Kamera
          </button>
        </nav>
      </header>

      {/* Alt sekme içerikleri */}
      <div className="settings-page-body" role="tabpanel">
        {subTab === 'general' && (
          <div className="settings-pane settings-pane-placeholder">
            <Sliders size={48} color="#1e293b" />
            <h3>Genel Ayarlar</h3>
            <p>
              Sistem geneli için ayarlar bu bölüme eklenecektir.
              <br />
              (Tema, polling süreleri, log seviyesi, vb.)
            </p>
          </div>
        )}

        {subTab === 'face' && (
          <div className="settings-pane settings-pane-placeholder">
            <ShieldCheck size={48} color="#1e293b" />
            <h3>Yüz Güvenliği Ayarları</h3>
            <p>
              Yüz güvenliği ayarları buraya taşınacaktır.
              <br />
              <small>
                (Flask 5007 — <code>/api/settings/runtime</code> endpoint'i:
                threshold, inference FPS, snapshot cooldown, patrol süreleri)
              </small>
            </p>
          </div>
        )}

        {subTab === 'camera' && (
          <div className="settings-pane settings-pane-camera">
            <CameraSettings />
          </div>
        )}
      </div>
    </div>
  )
}
