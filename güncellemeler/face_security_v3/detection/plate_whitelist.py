"""
Plaka Whitelist Modülü — PLAKA-2.H

Bilinen plakaları (aile, tanıdıklar) fuzzy match ile tanıyan modül.
Stabil tanıma için 4 güvenlik katmanı:

1. Fuzzy eşik = 2 karakter (Levenshtein mesafesi)
2. Şehir kodu fuzzy eşleşme (Levenshtein ≤1) — OCR şehir hatasını tolere
3. OYLAMA mekanizması (mevcut, çağıran kod tarafında)
4. Ambiguity reddi (birden fazla whitelist plaka aynı OCR'a uyarsa)

Kullanım:
    from detection.plate_whitelist import load_whitelist, match_plate

    whitelist = load_whitelist("config/plate_whitelist.txt")
    matched = match_plate("14MNF012", whitelist)
    if matched:
        # bilinen plaka
    else:
        # bilinmeyen plaka
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = 2
CITY_CODE_LENGTH = 2
CITY_FUZZY_THRESHOLD = 1  # OCR sistematik şehir kodu hatası için (örn. 3↔0/1/2)

# UI yönetim alanı ayracı — bu satırın altındakiler UI tarafından yönetilir
UI_SECTION_MARKER = "# === UI YÖNETİMİ (otomatik) ==="
UI_SECTION_HELP = "# UI ile ekleyip silinen plakalar — manuel düzenlemeyin"


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Pure Python Levenshtein distance — paket bağımlılığı yok."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def _normalize_plate(plate: str) -> str:
    """Plakayı karşılaştırma için normalize et — büyük harf, sadece A-Z0-9."""
    if not plate:
        return ""
    return re.sub(r'[^A-Z0-9]', '', plate.upper())


# Public alias for UI use
normalize_plate = _normalize_plate


def load_whitelist(filepath: str) -> list[str]:
    """
    Whitelist dosyasını oku, normalize edilmiş plaka listesi döndür.

    Format: her satır bir plaka, # ile başlayan satırlar yorum,
    satır içinde # sonrası yorum, boş satırlar atlanır.
    """
    path = Path(filepath)
    if not path.exists():
        logger.warning("[Whitelist] Dosya yok: %s — whitelist devre dışı", filepath)
        return []

    plates = []
    try:
        with path.open('r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if '#' in line:
                    line = line[:line.index('#')]

                line = line.strip()
                if not line:
                    continue

                normalized = _normalize_plate(line)
                if not normalized:
                    continue

                if len(normalized) < 5 or len(normalized) > 9:
                    logger.warning(
                        "[Whitelist] Satır %d geçersiz uzunluk (%d): %r",
                        line_num, len(normalized), line,
                    )
                    continue

                plates.append(normalized)
    except Exception as e:
        logger.error("[Whitelist] Okuma hatası: %s", e)
        return []

    logger.info("[Whitelist] %d plaka yüklendi: %s", len(plates), plates)
    return plates


def match_plate(ocr_output: str, whitelist: list[str]) -> Optional[str]:
    """
    OCR çıktısını whitelist'le fuzzy match et.

    Returns:
        - Whitelist'teki plaka (eşleşme varsa)
        - None (eşleşme yok, ambiguity, veya geçersiz)
    """
    if not ocr_output or not whitelist:
        return None

    normalized = _normalize_plate(ocr_output)
    if len(normalized) < 5:
        return None

    candidates = []

    ocr_city = normalized[:CITY_CODE_LENGTH]
    ocr_rest = normalized[CITY_CODE_LENGTH:]

    for wl_plate in whitelist:
        if len(wl_plate) < CITY_CODE_LENGTH + 1:
            continue

        wl_city = wl_plate[:CITY_CODE_LENGTH]
        wl_rest = wl_plate[CITY_CODE_LENGTH:]

        # KATMAN 1: Şehir kodu fuzzy eşleşmeli (≤1 karakter fark)
        # OCR sistematik şehir kodu hatası tolere edilir (örn. 34 → 14/04/24)
        # Cross-city false positive riski: aynı harf+rakam kombinasyonlu farklı şehir
        # — KATMAN 3 (ambiguity) + KATMAN 4 (OYLAMA) ek koruma sağlar
        if _levenshtein_distance(ocr_city, wl_city) > CITY_FUZZY_THRESHOLD:
            continue

        # KATMAN 2: Geri kalanda Levenshtein
        distance = _levenshtein_distance(ocr_rest, wl_rest)
        if distance <= FUZZY_THRESHOLD:
            candidates.append((wl_plate, distance))

    if not candidates:
        return None

    # KATMAN 3: Ambiguity reddi
    candidates.sort(key=lambda x: x[1])
    min_distance = candidates[0][1]
    best_matches = [p for p, d in candidates if d == min_distance]

    if len(best_matches) > 1:
        logger.warning(
            "[Whitelist] Ambiguity — %r için %d aday eşit mesafe (%d): %s — REDDEDİLDİ",
            normalized, len(best_matches), min_distance, best_matches,
        )
        return None

    matched = best_matches[0]
    logger.info(
        "[Whitelist] Eşleşme: %r → %s (mesafe=%d)",
        ocr_output, matched, min_distance,
    )
    return matched


def save_whitelist(filepath: str, ui_plates: list[tuple[str, str]]) -> bool:
    """
    UI tarafından yönetilen plakaları kaydet.

    Dosyayı iki bölüme ayırır:
    - Marker üstü: kullanıcının manuel yorumları (dokunulmaz)
    - Marker altı: ui_plates ile yeniden yazılır

    Args:
        filepath: whitelist dosya yolu
        ui_plates: [(plate, comment), ...] — UI'dan gelen liste
                    plate: "34NNF012" formatında string
                    comment: "Anne araba" gibi yorum, boş olabilir

    Returns:
        True if başarılı, False if I/O hatası
    """
    path = Path(filepath)

    # Mevcut dosyayı oku (varsa) — marker üstü kullanıcı bölümü korunacak
    user_section = ""
    if path.exists():
        try:
            content = path.read_text(encoding='utf-8')
            if UI_SECTION_MARKER in content:
                user_section = content.split(UI_SECTION_MARKER)[0].rstrip() + "\n\n"
            else:
                user_section = content.rstrip() + "\n\n"
        except Exception as e:
            logger.error("[Whitelist] save_whitelist okuma hatası: %s", e)
            return False

    # UI bölümünü oluştur
    ui_section_lines = [UI_SECTION_MARKER, UI_SECTION_HELP, ""]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    for plate, comment in ui_plates:
        normalized = _normalize_plate(plate)
        if not normalized:
            continue
        if comment:
            line = f"{normalized}    # {comment}"
        else:
            line = f"{normalized}    # UI eklendi {ts}"
        ui_section_lines.append(line)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        new_content = user_section + "\n".join(ui_section_lines) + "\n"
        path.write_text(new_content, encoding='utf-8')
        logger.info(
            "[Whitelist] Dosyaya kaydedildi: %s (%d UI plaka)",
            filepath, len(ui_plates),
        )
        return True
    except Exception as e:
        logger.error("[Whitelist] save_whitelist yazma hatası: %s", e)
        return False


def get_ui_plates(filepath: str) -> list[tuple[str, str]]:
    """
    Whitelist dosyasından SADECE UI bölümündeki plakaları oku.

    UI dialog'unda göstermek için. Kullanıcı alanı plakaları gösterilmez
    (onlar dokunulmaz, UI'da editable olmaz).

    Returns:
        [(plate, comment), ...] — UI bölümündeki plakalar
    """
    path = Path(filepath)
    if not path.exists():
        return []

    try:
        content = path.read_text(encoding='utf-8')
    except Exception as e:
        logger.error("[Whitelist] get_ui_plates okuma hatası: %s", e)
        return []

    if UI_SECTION_MARKER not in content:
        return []

    ui_section = content.split(UI_SECTION_MARKER, 1)[1]
    plates = []
    for line in ui_section.split('\n'):
        comment = ""
        if '#' in line:
            line_text, _, comment_part = line.partition('#')
            comment = comment_part.strip()
            line = line_text

        line = line.strip()
        if not line:
            continue

        normalized = _normalize_plate(line)
        if not normalized or len(normalized) < 5 or len(normalized) > 9:
            continue

        plates.append((normalized, comment))

    return plates


# ==============================================================
# Unit Testler — python3 detection/plate_whitelist.py ile çalıştır
# ==============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("PLAKA-2.H-1 Unit Testler")
    print("=" * 60)

    print("\n[1] Levenshtein distance:")
    assert _levenshtein_distance("kitten", "sitting") == 3
    assert _levenshtein_distance("abc", "abc") == 0
    assert _levenshtein_distance("", "abc") == 3
    assert _levenshtein_distance("NNF012", "MNF012") == 1
    assert _levenshtein_distance("NNF012", "MNF013") == 2
    print("    ✓ 5 case")

    print("\n[2] Normalize:")
    assert _normalize_plate("34 NNF 012") == "34NNF012"
    assert _normalize_plate("34-NNF-012") == "34NNF012"
    assert _normalize_plate("  34nnf012  ") == "34NNF012"
    assert _normalize_plate("") == ""
    print("    ✓ 4 case")

    print("\n[3] Match — gerçek senaryolar:")
    whitelist = ["34NNF012", "06ABC123", "07XYZ456"]

    assert match_plate("34NNF012", whitelist) == "34NNF012", "Tam eşleşme fail"
    print("    ✓ Tam eşleşme: 34NNF012 → 34NNF012")

    assert match_plate("34MNF012", whitelist) == "34NNF012", "1 char fark fail"
    print("    ✓ 1 char fark: 34MNF012 → 34NNF012")

    assert match_plate("34MNF015", whitelist) == "34NNF012", "2 char fark fail"
    print("    ✓ 2 char fark: 34MNF015 → 34NNF012")

    # KATMAN 1: Şehir kodu fuzzy ≤1 → kabul (OCR hatası tolere)
    assert match_plate("14NNF012", whitelist) == "34NNF012", "City fuzzy 1 fail"
    print("    ✓ City fuzzy ≤1 kabul: 14NNF012 → 34NNF012 (OCR şehir hatası)")

    assert match_plate("04NNF012", whitelist) == "34NNF012", "City fuzzy 1 fail (04)"
    print("    ✓ City fuzzy ≤1 kabul: 04NNF012 → 34NNF012")

    # KATMAN 1: Şehir kodu fuzzy >1 → reddet
    result = match_plate("76NNF012", whitelist)
    assert result is None, f"City fuzzy 2 kabul edildi: {result}"
    print("    ✓ City fuzzy >1 reddi: 76NNF012 → None (her iki hane farklı)")

    result = match_plate("34ABC999", whitelist)
    assert result is None, f"3+ char fark kabul edildi: {result}"
    print("    ✓ Fazla fark reddi: 34ABC999 → None")

    assert match_plate("", whitelist) is None
    assert match_plate("AB", whitelist) is None
    print("    ✓ Boş/kısa girdi reddi")

    print("\n[4] Ambiguity (KATMAN 3):")
    ambig_whitelist = ["34NNF012", "34NNG012"]
    result = match_plate("34NNX012", ambig_whitelist)
    assert result is None, f"Ambiguity geçti: {result}"
    print("    ✓ Ambiguity reddi: 34NNX012 → None")

    # KATMAN 1 + KATMAN 3: City fuzzy ambiguity
    # 14NNF012 hem 34NNF012'ye (city distance 1, rest 0) hem 04NNF012'ye
    # eşit yakınlıkta → ambiguity reddi
    city_ambig_whitelist = ["34NNF012", "04NNF012"]
    result = match_plate("14NNF012", city_ambig_whitelist)
    assert result is None, f"City ambiguity geçti: {result}"
    print("    ✓ City ambiguity reddi: 14NNF012 → None (34 ve 04'e eşit mesafe)")

    print("\n[5] Load whitelist:")
    test_path = Path("/tmp/test_whitelist.txt")
    test_path.write_text("""# Test whitelist
34NNF012  # Aile
06ABC123  # Tanıdık

# Boş satırlar atlanmalı
07XYZ456
# 99XXX999  # Tamamen yorum, alınmamalı
""", encoding='utf-8')

    loaded = load_whitelist(str(test_path))
    expected = ["34NNF012", "06ABC123", "07XYZ456"]
    assert loaded == expected, f"Beklenen {expected}, geldi {loaded}"
    print(f"    ✓ Loaded: {loaded}")

    none_loaded = load_whitelist("/tmp/nonexistent_whitelist.txt")
    assert none_loaded == []
    print("    ✓ Olmayan dosya → boş liste")

    print("\n[6] save_whitelist + get_ui_plates:")

    # Senaryo 1: yeni dosya (kullanıcı alanı yok)
    test_path2 = Path("/tmp/test_save_whitelist_new.txt")
    if test_path2.exists():
        test_path2.unlink()

    ui_plates_in = [("34NNF012", "Test 1"), ("06ABC123", "")]
    assert save_whitelist(str(test_path2), ui_plates_in) is True
    content = test_path2.read_text(encoding='utf-8')
    assert UI_SECTION_MARKER in content
    assert "34NNF012" in content
    assert "Test 1" in content
    assert "06ABC123" in content
    assert "UI eklendi" in content
    print("    ✓ Yeni dosya save_whitelist")

    read_back = get_ui_plates(str(test_path2))
    assert len(read_back) == 2
    assert read_back[0] == ("34NNF012", "Test 1")
    assert read_back[1][0] == "06ABC123"
    assert "UI eklendi" in read_back[1][1]
    print(f"    ✓ get_ui_plates: {read_back}")

    # Senaryo 2: kullanıcı bölümü var
    test_path3 = Path("/tmp/test_save_whitelist_existing.txt")
    test_path3.write_text(
        "# Kullanıcı yorumu\n# Önemli not\n99XXX999    # Kullanıcı plakası\n\n",
        encoding='utf-8',
    )

    assert save_whitelist(str(test_path3), [("34NNF012", "Yeni")]) is True
    content3 = test_path3.read_text(encoding='utf-8')
    assert "99XXX999" in content3
    assert "Önemli not" in content3
    assert "34NNF012" in content3
    assert UI_SECTION_MARKER in content3
    print("    ✓ Kullanıcı bölümü korundu, UI bölümü eklendi")

    read_back3 = get_ui_plates(str(test_path3))
    assert len(read_back3) == 1
    assert read_back3[0] == ("34NNF012", "Yeni")
    plates_only = [p for p, c in read_back3]
    assert "99XXX999" not in plates_only
    print("    ✓ get_ui_plates kullanıcı bölümünü gizliyor")

    all_plates = load_whitelist(str(test_path3))
    assert "99XXX999" in all_plates
    assert "34NNF012" in all_plates
    print(f"    ✓ load_whitelist tüm plakaları okur: {all_plates}")

    assert normalize_plate("34 NNF 012") == "34NNF012"
    print("    ✓ normalize_plate public alias")

    print("\n" + "=" * 60)
    print("TÜM TESTLER GEÇTİ ✓")
    print("=" * 60)
