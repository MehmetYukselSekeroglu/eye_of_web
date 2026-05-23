const express = require('express');
const cors = require('cors');
const { exec, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const { Pool } = require('pg');

const app = express();
const PORT = 5006;

const BASE_PATH = '/home/user/Masaüstü/eye_of_web/src';
// Instagram BOT proje root'undaki güncellemeler/insta_bot/ altında durur
const INSTA_BOT_PATH = '/home/user/Masaüstü/eye_of_web/güncellemeler/insta_bot';
// Face Security v3 — Tkinter desktop uygulaması; subprocess ile launch edilir
const FACE_SECURITY_PATH = '/home/user/Masaüstü/eye_of_web/güncellemeler/face_security_v3';
const IMAGE_PATH = '/home/user/Masaüstü/dnegeharita.png';

app.use(cors());
app.use(express.json());

// ─── POSTGRESQL CONNECTION POOL ───────────────────────────────────────────────
const pgPool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT || '5432', 10),
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD || 'postgres',
  database: process.env.DB_NAME || 'EyeOfWeb',
  max: 5,
});

// ─── IN-MEMORY STATE ───────────────────────────────────────────────────────
let logs = ['>>> EYE OF WEB PANEL READY'];
const cameraProcesses = {}; // { cameraName: childProcess }
let faceSecurityProc = null; // Face Security v3 Tkinter app process (tek instance)

const CAMERA_SCRIPTS = {
  'Giriş Kapısı': 'realtime_search_camera_GIRIS_KAPISI.py',
  'Otopark':      'realtime_search_camera_OTOPARK.py',
  'Ofis 1':       'realtime_search_camera_OFIS_1.py',
  'Ofis 2':       'realtime_search_camera_OFIS_2.py',
  'Eski Ofis':    'realtime_search_camera_ESKI_OFIS.py',
  'S. Odası':     'realtime_search_camera_SODASI.py',
  'Buton 7':      'realtime_search_camera_DEPO_ONU.py',
  'Buton 8':      'realtime_search_camera_ESKI_OFIS.py',
  'Buton 9':      'realtime_search_camera_ESKI_OFIS.py',
  'Buton 10':     'realtime_search_camera_ESKI_OFIS.py',
};

// ─── HELPERS ──────────────────────────────────────────────────────────────
function addLog(message) {
  const ts = new Date().toLocaleTimeString('tr-TR', { hour12: false });
  logs.push(`>>> [${ts}] ${message}`);
  if (logs.length > 1000) logs = logs.slice(-1000);
  console.log(`[LOG] ${message}`);
}

function runInTerminal(command) {
  // Escape double quotes inside the command for the shell wrapper
  const escaped = command.replace(/"/g, '\\"');
  const termCmd = `x-terminal-emulator -e bash -c "${escaped}; exec bash"`;
  exec(termCmd, (err) => {
    if (err) {
      console.error('Terminal launch error:', err.message);
    }
  });
}

/**
 * Python script'i spawn ile çalıştır, stdout/stderr'i SATIR SATIR `addLog`'a
 * akıt. Frontend `/api/logs` polling'iyle bu satırları canlı görür —
 * runInTerminal'in aksine yeni bir terminal penceresi açmaz.
 *
 * @param {string}   prettyName  Log prefix'i (örn. "INSTABOT")
 * @param {string[]} args        Python script'in argv'i (ilk eleman script yolu)
 * @param {object}   opts
 * @param {string}   opts.cwd    Çalıştırma dizini (default: BASE_PATH = src/)
 * @param {string}   opts.venvActivate  Virtualenv activate komutu;
 *                                       null → venv kullanma
 */
function runStreaming(prettyName, args, opts = {}) {
  const cwd = opts.cwd || BASE_PATH;
  // Default: src/WorkEnv. Bot src/ dışındaysa (örn. güncellemeler/insta_bot)
  // src/WorkEnv'u absolute olarak aktive et.
  const venvActivate = opts.venvActivate !== undefined
    ? opts.venvActivate
    : `source ${BASE_PATH}/WorkEnv/bin/activate`;
  const pyCmd = `python3 ${args.map(a => `"${a.replace(/"/g, '\\"')}"`).join(' ')}`;
  const cmd = venvActivate ? `${venvActivate} && ${pyCmd}` : pyCmd;

  addLog(`${prettyName}: BAŞLATILIYOR -> ${args[0]}  (cwd=${cwd})`);

  const proc = spawn('bash', ['-c', cmd], {
    cwd,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  let lineBuf = '';
  let errBuf = '';

  const flushLines = (chunk, buf, tag) => {
    buf += chunk.toString();
    const lines = buf.split('\n');
    const remainder = lines.pop();
    for (const line of lines) {
      const trimmed = line.replace(/\s+$/, '');
      if (trimmed) addLog(`${prettyName} ${tag}: ${trimmed}`);
    }
    return remainder;
  };

  proc.stdout.on('data', (chunk) => { lineBuf = flushLines(chunk, lineBuf, ''); });
  proc.stderr.on('data', (chunk) => { errBuf  = flushLines(chunk, errBuf, '[stderr]'); });

  proc.on('error', (err) => {
    addLog(`${prettyName}: SPAWN HATASI - ${err.message}`);
  });
  proc.on('close', (code) => {
    if (lineBuf) addLog(`${prettyName}: ${lineBuf}`);
    if (errBuf)  addLog(`${prettyName} [stderr]: ${errBuf}`);
    addLog(`${prettyName}: TAMAMLANDI (exit=${code})`);
  });

  return proc;
}

// ─── SYSTEM ───────────────────────────────────────────────────────────────
app.post('/api/system/start', (req, res) => {
  runInTerminal(`cd ${BASE_PATH} && sudo docker compose up -d`);
  addLog('SİSTEM BAŞLATILDI');
  res.json({ success: true });
});

app.post('/api/system/stop', (req, res) => {
  runInTerminal(`cd ${BASE_PATH} && sudo docker compose down`);
  addLog('SİSTEM DURDURULDU');
  res.json({ success: true });
});

// ─── SCAN ENDPOINTS ────────────────────────────────────────────────────────
app.post('/api/scan/web', (req, res) => {
  const { url } = req.body || {};
  if (!url || !url.trim()) {
    return res.status(400).json({ error: 'URL boş olamaz' });
  }
  const cleanUrl = url.trim();
  runInTerminal(
    `cd ${BASE_PATH} && source WorkEnv/bin/activate && python3 single_domain.py --url "${cleanUrl}" --max-depth 10 --risk-level "normal" --category "news"`
  );
  addLog(`WEB TARAMA BAŞLADI: ${cleanUrl}`);
  res.json({ success: true });
});

app.post('/api/scan/auto', (req, res) => {
  runInTerminal(
    `cd ${BASE_PATH} && source WorkEnv/bin/activate && python3 single_domain.py --file dosya.txt --max-depth 3 --risk-level "normal" --category "news"`
  );
  addLog('OTOMATİK TARAMA BAŞLADI');
  res.json({ success: true });
});

app.post('/api/scan/bot', (req, res) => {
  runInTerminal(
    `cd ${BASE_PATH} && source WorkEnv/bin/activate && python3 single_domain_selenium.py --file liste.txt --risk-level "normal" --category "web"`
  );
  addLog('BOT WEB TARAMA BAŞLADI');
  res.json({ success: true });
});

app.post('/api/scan/google', (req, res) => {
  const { keyword } = req.body || {};
  if (!keyword || !keyword.trim()) {
    return res.status(400).json({ error: 'Anahtar kelime boş olamaz' });
  }
  const cleanKeyword = keyword.trim();
  runInTerminal(
    `cd ${BASE_PATH} && source WorkEnv/bin/activate && python3 google_search_crawler.py --keyword "${cleanKeyword}" --risk-level "normal" --category "google search" --num_results 30 --backend playwright`
  );
  addLog(`GOOGLE TARAMA BAŞLADI: ${cleanKeyword}`);
  res.json({ success: true });
});

// MEVCUT YAZILIM — "INSTAGRAM TARAMA": kullanıcı adını Google üzerinden arar.
// Bu Instagram BOT'tan AYRI bir araçtır; davranış değiştirilmemiştir.
app.post('/api/scan/instagram', (req, res) => {
  const { username } = req.body || {};
  if (!username || !username.trim()) {
    return res.status(400).json({ error: 'Kullanıcı adı boş olamaz' });
  }
  const cleanUsername = username.trim();
  runInTerminal(
    `cd ${BASE_PATH} && source WorkEnv/bin/activate && python3 google_search_crawler.py --keyword "${cleanUsername}" --risk-level "normal" --category "google search" --num_results 30 --backend playwright`
  );
  addLog(`INSTAGRAM TARAMA BAŞLADI: ${cleanUsername}`);
  res.json({ success: true });
});

// YENİ ARAÇ — "INSTAGRAM BOT": user/insta_bot/worker.py'dan adapt edilmiş
// Selenium tabanlı takipçi sıyırıcı. Yukarıdaki INSTAGRAM TARAMA'dan AYRI
// bir araçtır; ikisi karıştırılmamalıdır.
app.post('/api/scan/instagram-bot', (req, res) => {
  const { username, targets, maxPerTarget, headless } = req.body || {};

  let raw = '';
  if (typeof targets === 'string' && targets.trim()) {
    raw = targets;
  } else if (typeof username === 'string' && username.trim()) {
    raw = username;
  } else {
    return res.status(400).json({ error: 'Hedef kullanıcı listesi boş olamaz' });
  }

  // Satır/noktalı virgül/virgül normalize → virgül listesi
  const parsed = raw
    .replace(/[\n;]+/g, ',')
    .split(',')
    .map(s => s.trim().replace(/^@/, ''))
    .filter(Boolean);

  if (parsed.length === 0) {
    return res.status(400).json({ error: 'Geçerli kullanıcı adı bulunamadı' });
  }
  const targetList = parsed.join(',');

  const args = ['instagram_crawler.py', '--targets', targetList];
  const max = parseInt(maxPerTarget, 10);
  if (Number.isInteger(max) && max > 0 && max <= 500) {
    args.push('--max-per-target', String(max));
  }
  if (headless === true) args.push('--headless');

  addLog(`INSTAGRAM BOT BAŞLADI: [${parsed.length} hedef] ${parsed.slice(0, 3).join(', ')}${parsed.length > 3 ? ', ...' : ''}`);
  // Canlı stdout akışı → in-app log paneli (runInTerminal değil)
  // Bot güncellemeler/insta_bot/ altında; src/WorkEnv venv'ini aktive et.
  runStreaming('INSTABOT', args, { cwd: INSTA_BOT_PATH });
  res.json({ success: true, targets: parsed });
});

// ─── FACE SECURITY v3 ──────────────────────────────────────────────────────
// Tkinter UI'ı İPTAL EDİLDİ — Flask web sunucusuna refactor edildi.
// `launch.sh` artık `web_app.py`'i çalıştırıyor; uygulama
// http://127.0.0.1:5007/ üzerinde HTTP olarak ayakta. React dashboard
// bu URL'i iframe ile gömüyor.
//
// Bu endpoint'ler subprocess yaşam döngüsünü (start/stop) yönetir;
// status endpoint'i hem subprocess PID'i hem de gerçek HTTP /api/status'ü
// probe ederek "hazır mı?" sorusunu daha doğru yanıtlar.
const FACE_SEC_PORT = 5007; // web_app.py default; .env ile FACE_SEC_PORT override edilebilir

app.post('/api/face-security/start', (req, res) => {
  if (faceSecurityProc && !faceSecurityProc.killed && faceSecurityProc.exitCode === null) {
    return res.status(409).json({
      error: 'Face Security zaten çalışıyor',
      pid: faceSecurityProc.pid,
    });
  }

  const launchScript = path.join(FACE_SECURITY_PATH, 'launch.sh');
  if (!fs.existsSync(launchScript)) {
    return res.status(500).json({ error: `launch.sh bulunamadı: ${launchScript}` });
  }

  try {
    // bash launch.sh — kendi cwd'sini ayarlıyor, sistem Python3 ile çalışıyor
    faceSecurityProc = spawn('bash', [launchScript], {
      cwd: FACE_SECURITY_PATH,
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: false,
      env: { ...process.env, DISPLAY: process.env.DISPLAY || ':0' },
    });

    let outBuf = '';
    let errBuf = '';
    const flushLines = (chunk, buf, tag) => {
      buf += chunk.toString();
      const lines = buf.split('\n');
      const remainder = lines.pop();
      for (const line of lines) {
        const trimmed = line.replace(/\s+$/, '');
        if (trimmed) addLog(`FACE-SEC${tag}: ${trimmed}`);
      }
      return remainder;
    };

    faceSecurityProc.stdout.on('data', (chunk) => { outBuf = flushLines(chunk, outBuf, ''); });
    faceSecurityProc.stderr.on('data', (chunk) => { errBuf = flushLines(chunk, errBuf, ' [stderr]'); });

    faceSecurityProc.on('error', (err) => {
      addLog(`FACE-SEC: SPAWN HATASI - ${err.message}`);
    });
    faceSecurityProc.on('close', (code) => {
      if (outBuf) addLog(`FACE-SEC: ${outBuf}`);
      if (errBuf) addLog(`FACE-SEC [stderr]: ${errBuf}`);
      addLog(`FACE-SEC: KAPANDI (exit=${code})`);
      faceSecurityProc = null;
    });

    addLog(`YÜZ GÜVENLİĞİ BAŞLATILDI (pid=${faceSecurityProc.pid})`);
    res.json({ success: true, pid: faceSecurityProc.pid });
  } catch (err) {
    addLog(`FACE-SEC: BAŞLATMA HATASI - ${err.message}`);
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/face-security/stop', (req, res) => {
  if (!faceSecurityProc || faceSecurityProc.exitCode !== null) {
    return res.json({ success: true, running: false, msg: 'Zaten kapalı' });
  }
  try {
    // SIGTERM önce, gerekirse SIGKILL
    process.kill(faceSecurityProc.pid, 'SIGTERM');
    addLog(`YÜZ GÜVENLİĞİ DURDURMA SİNYALİ (pid=${faceSecurityProc.pid})`);
    // 3sn sonra hâlâ canlıysa zorla öldür
    setTimeout(() => {
      if (faceSecurityProc && faceSecurityProc.exitCode === null) {
        try { process.kill(faceSecurityProc.pid, 'SIGKILL'); } catch (_) { /* zaten ölmüş */ }
      }
    }, 3000);
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/face-security/status', async (req, res) => {
  const procAlive =
    faceSecurityProc !== null &&
    !faceSecurityProc.killed &&
    faceSecurityProc.exitCode === null;

  // Flask web_app HTTP probe — process var ama henüz model yüklemediyse
  // /api/status 503 vs 200 dönebilir; biz sadece "bağlanılabiliyor mu"
  // kontrolü yapıyoruz. fetch native Node 18+'da; eski sürümler için
  // http.get fallback kullanabiliriz ama compose 18+ varsayıyoruz.
  let httpReady = false;
  if (procAlive) {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 800);
      const r = await fetch(`http://127.0.0.1:${FACE_SEC_PORT}/api/status`, { signal: ctrl.signal });
      clearTimeout(t);
      httpReady = r.ok;
    } catch (_) {
      httpReady = false;
    }
  }

  res.json({
    running: procAlive,         // subprocess canlı mı
    httpReady,                   // Flask hazır mı (iframe yüklenebilir mi)
    pid: procAlive ? faceSecurityProc.pid : null,
    port: FACE_SEC_PORT,
    iframeUrl: `http://127.0.0.1:${FACE_SEC_PORT}/`,
    path: FACE_SECURITY_PATH,
  });
});

// ─── CONTROL: KAMERA LAUNCHER ──────────────────────────────────────────────
// React KONTROL sağ panelindeki butonlar bu endpoint'i tetikler.
// Orijinal PyQt5 masaüstü penceresini (Milvus eşleşmeleri + Cyber HUD)
// kullanıcının makinesinde detached olarak başlatır.
//
// Komut:
//   cd /home/user/Masaüstü/eye_of_web/src
//   source WorkEnv/bin/activate
//   python3 realtime_search_camera_launcher.py --cam-id <id>
//
// Notlar:
//   - spawn detached=true → backend kapansa bile pencere açık kalır
//   - stdio: ignore → backend stdout'u Qt log'larıyla kirlenmez
//   - unref() → child Node event loop'u tutmaz
app.post('/api/control/launch-camera/:id', (req, res) => {
  const camId = parseInt(req.params.id, 10);
  if (!Number.isInteger(camId) || camId < 1 || camId > 25) {
    return res.status(400).json({ error: 'cam_id 1-25 aralığında olmalı' });
  }

  const cmd = `cd ${BASE_PATH} && source WorkEnv/bin/activate && python3 realtime_search_camera_launcher.py --cam-id ${camId}`;
  addLog(`KAMERA #${camId} LAUNCHER TETİKLENDİ`);

  try {
    const proc = spawn('bash', ['-c', cmd], {
      cwd: BASE_PATH,
      detached: true,
      stdio: 'ignore',
      env: { ...process.env, DISPLAY: process.env.DISPLAY || ':0' },
    });
    proc.on('error', (err) => {
      addLog(`KAMERA #${camId} SPAWN HATASI: ${err.message}`);
    });
    proc.unref();   // Node event loop'u tutmasın

    res.json({
      success: true,
      cam_id: camId,
      message: `Kamera #${camId} masaüstü penceresi başlatılıyor (PyQt5 + Milvus).`,
      pid: proc.pid,
    });
  } catch (err) {
    addLog(`KAMERA #${camId} BAŞLATMA HATASI: ${err.message}`);
    res.status(500).json({ error: err.message });
  }
});


app.post('/api/scan/facebook', (req, res) => {
  runInTerminal(
    `cd ${BASE_PATH} && source WorkEnv/bin/activate && python3 facebook_crawler.py --file facebook.txt --scroll_count 40 --headless --backend playwright`
  );
  addLog('FACEBOOK TARAMA BAŞLADI');
  res.json({ success: true });
});

app.post('/api/scan/twitter', (req, res) => {
  runInTerminal(
    `cd ${BASE_PATH} && source WorkEnv/bin/activate && python3 twitter_crawler_file_based.py --threads 4 twitter_usernames.txt`
  );
  addLog('TWITTER LİSTE TARAMA BAŞLADI');
  res.json({ success: true });
});

app.post('/api/scan/twitter-dump', (req, res) => {
  runInTerminal(
    `cd ${BASE_PATH} && source WorkEnv/bin/activate && python3 twitter_username_dumper.py --namelist example_namelist.txt`
  );
  addLog('TWITTER LİSTE KAZIMA BAŞLADI');
  res.json({ success: true });
});

// ─── CAMERA TOGGLE ─────────────────────────────────────────────────────────
app.post('/api/camera/toggle', (req, res) => {
  const { name } = req.body || {};
  const script = CAMERA_SCRIPTS[name];

  if (!name || !script) {
    return res.status(400).json({ error: 'Geçersiz kamera adı' });
  }

  if (cameraProcesses[name]) {
    // Kill running process
    const proc = cameraProcesses[name];
    try {
      process.kill(proc.pid, 'SIGTERM');
    } catch (e) {
      console.error(`Kill error for ${name}:`, e.message);
    }
    delete cameraProcesses[name];
    addLog(`${name.toUpperCase()} DURDURULDU`);
    return res.json({ active: false, count: Object.keys(cameraProcesses).length });
  }

  // Start new process
  const cmd = `source ${BASE_PATH}/WorkEnv/bin/activate && python3 ${BASE_PATH}/${script}`;
  const proc = spawn('bash', ['-c', cmd], {
    cwd: BASE_PATH,
    detached: false,
    stdio: 'pipe',
  });

  proc.on('error', (err) => {
    console.error(`Camera process error [${name}]:`, err.message);
    delete cameraProcesses[name];
  });

  proc.on('exit', (code) => {
    console.log(`Camera [${name}] exited with code ${code}`);
    delete cameraProcesses[name];
  });

  proc.stdout.on('data', (data) => {
    addLog(`[${name}] ${data.toString().trim()}`);
  });

  proc.stderr.on('data', (data) => {
    addLog(`[${name} ERR] ${data.toString().trim()}`);
  });

  cameraProcesses[name] = proc;
  addLog(`${name.toUpperCase()} BAŞLATILDI (PID: ${proc.pid})`);
  res.json({ active: true, pid: proc.pid, count: Object.keys(cameraProcesses).length });
});

// ─── STATUS ENDPOINTS ──────────────────────────────────────────────────────
app.get('/api/camera/count', (req, res) => {
  res.json({ count: Object.keys(cameraProcesses).length });
});

app.get('/api/camera/active', (req, res) => {
  const active = {};
  for (const name of Object.keys(cameraProcesses)) {
    active[name] = true;
  }
  res.json({ active });
});

app.get('/api/logs', (req, res) => {
  res.json({ logs });
});

// ─── MAP IMAGE ─────────────────────────────────────────────────────────────
app.get('/api/image/map', (req, res) => {
  if (fs.existsSync(IMAGE_PATH)) {
    res.sendFile(IMAGE_PATH);
  } else {
    // Return a 1x1 transparent PNG placeholder
    res.status(404).json({ error: 'Harita görseli bulunamadı: ' + IMAGE_PATH });
  }
});

// ─── REPORT: FACE METADATA LOOKUP ─────────────────────────────────────────
app.get('/api/report/face/:milvusId', async (req, res) => {
  const { milvusId } = req.params;

  // Validate: must be a numeric string (bigint)
  if (!/^\d+$/.test(milvusId)) {
    return res.status(400).json({ error: 'Geçersiz ID formatı. Sadece rakam girilmelidir.' });
  }

  try {
    const query = `
      SELECT
        f."ID"              AS face_pg_id,
        f."MilvusRefID"     AS milvus_ref_id,
        f."DetectionDate"   AS face_detection_date,
        i."ID"              AS image_main_id,
        i."Protocol"        AS protocol,
        bd."Domain"         AS base_domain,
        up."Path"           AS url_path,
        ue."Etc"            AS url_etc,
        i."ImageProtocol"   AS image_protocol,
        ibd."Domain"        AS image_domain,
        iup."Path"          AS image_path,
        iue."Etc"           AS image_url_etc,
        it."Title"          AS image_title,
        i."ImageID"         AS image_binary_id,
        i."FaceID"          AS face_id_array,
        i."RiskLevel"       AS risk_level,
        wc."Category"       AS website_category,
        ih."ImageHash"      AS image_hash,
        i."HashID"          AS hash_id,
        i."Source"           AS source,
        i."DetectionDate"   AS image_detection_date
      FROM "EyeOfWebFaceID" f
      JOIN "ImageBasedMain" i ON i."FaceID" @> ARRAY[f."ID"]
      LEFT JOIN "BaseDomainID"      bd  ON i."BaseDomainID"  = bd."ID"
      LEFT JOIN "UrlPathID"         up  ON i."UrlPathID"     = up."ID"
      LEFT JOIN "UrlEtcID"          ue  ON i."UrlEtcID"      = ue."ID"
      LEFT JOIN "BaseDomainID"      ibd ON i."ImageDomainID" = ibd."ID"
      LEFT JOIN "ImageUrlPathID"    iup ON i."ImagePathID"   = iup."ID"
      LEFT JOIN "ImageUrlEtcID"     iue ON i."ImageUrlEtcID" = iue."ID"
      LEFT JOIN "ImageTitleID"      it  ON i."ImageTitleID"  = it."ID"
      LEFT JOIN "WebSiteCategoryID" wc  ON i."CategoryID"    = wc."ID"
      LEFT JOIN "ImageHashID"       ih  ON i."HashID"        = ih."ID"
      WHERE f."MilvusRefID" = $1
      LIMIT 20
    `;

    const result = await pgPool.query(query, [milvusId]);

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Kayıt bulunamadı. Girilen Milvus ID ile eşleşen yüz verisi yok.' });
    }

    // Build a full source URL from parts
    const rows = result.rows.map(row => {
      let sourceUrl = null;
      if (row.protocol && row.base_domain) {
        const path = row.url_path ? (row.url_path.startsWith('/') ? row.url_path : '/' + row.url_path) : '';
        sourceUrl = `${row.protocol}://${row.base_domain}${path}${row.url_etc || ''}`;
      }

      let imageUrl = null;
      if (row.image_protocol && row.image_domain) {
        const imgPath = row.image_path ? (row.image_path.startsWith('/') ? row.image_path : '/' + row.image_path) : '';
        imageUrl = `${row.image_protocol}://${row.image_domain}${imgPath}${row.image_url_etc || ''}`;
      }

      return { ...row, source_url: sourceUrl, image_url: imageUrl };
    });

    res.json({ count: rows.length, results: rows });
  } catch (err) {
    console.error('Report query error:', err.message);
    res.status(500).json({ error: 'Veritabanı sorgu hatası: ' + err.message });
  }
});

// Serve face thumbnail as base64 from ImageID table
app.get('/api/report/face-image/:imageId', async (req, res) => {
  const { imageId } = req.params;
  if (!/^\d+$/.test(imageId)) {
    return res.status(400).json({ error: 'Geçersiz Image ID' });
  }

  try {
    const result = await pgPool.query(
      'SELECT "BinaryImage" FROM "ImageID" WHERE "ID" = $1',
      [imageId]
    );
    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Görsel bulunamadı' });
    }
    const buf = result.rows[0].BinaryImage;
    res.set('Content-Type', 'image/jpeg');
    res.send(buf);
  } catch (err) {
    console.error('Image query error:', err.message);
    res.status(500).json({ error: 'Görsel sorgu hatası' });
  }
});

// ─── START ─────────────────────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(`[EyeOfWeb Backend] Port ${PORT} üzerinde çalışıyor`);
  console.log(`[EyeOfWeb Backend] BASE_PATH: ${BASE_PATH}`);
});
