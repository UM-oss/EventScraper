"""
Nadomestne slike za dogodke brez slik.
Sistem poskuša najti sliko po sledečem vrstnem redu:
  1. og:image / twitter:image iz source_url
  2. Facebook post slika (če je source_url FB povezava)
  3. Največja slika v <article>/<main>/body
  4. Slika prizorišča (source_id → venue image)
  5. Kategorijska simbolna slika (event_type → placeholder)
"""

import logging
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# FB kompatibilni headers - facebookexternalhit user agent dobi OG metadata
FB_HEADERS = {"User-Agent": "facebookexternalhit/1.1"}
DEFAULT_HEADERS = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}

VENUE_IMAGE_MAP = {
    "cd-cc": "https://www.cd-cc.si/themes/custom/cdcc/logo.svg",
    "kinodvor": "https://www.kinodvor.org/wp-content/themes/kinodvor/img/logo.png",
    "kinosiska": "https://www.kinosiska.si/assets/img/logo.png",
    "spanskiborci": "https://www.spanskiborci.si/img/logo.png",
    "mgml": "https://mgml.si/themes/mgml/logo.png",
}

CATEGORY_IMAGE_MAP = {
    "koncert": "https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=800&q=80",
    "gledalisce": "https://images.unsplash.com/photo-1503095396549-807759245b35?w=800&q=80",
    "film": "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=800&q=80",
    "razstava": "https://images.unsplash.com/photo-1531243269054-5ebf6f34081e?w=800&q=80",
    "predavanje": "https://images.unsplash.com/photo-1475721027785-f74eccf877e2?w=800&q=80",
    "delavnica": "https://images.unsplash.com/photo-1552664730-d307ca884978?w=800&q=80",
    "festival": "https://images.unsplash.com/photo-1533174072545-7a4b6ad7a6c3?w=800&q=80",
    "sport": "https://images.unsplash.com/photo-1461896836934-bd45ba8fcf9b?w=800&q=80",
    "sejem": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=800&q=80",
    "otroski": "https://images.unsplash.com/photo-1503454537195-1dcabb73ffb9?w=800&q=80",
    "kulinarika": "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=800&q=80",
    "vodeni-ogled": "https://images.unsplash.com/photo-1569949381669-ecf31ae8e613?w=800&q=80",
    "zabava": "https://images.unsplash.com/photo-1496337589254-7e19d01cec44?w=800&q=80",
    "kultura": "https://images.unsplash.com/photo-1518998053901-5348d3961a04?w=800&q=80",
}

DEFAULT_IMAGE = "https://images.unsplash.com/photo-1501281668745-f7f57925c3b4?w=800&q=80"

# Min. dimenzije slike za objavo (uporabnikova zahteva)
MIN_IMAGE_WIDTH = 520
MIN_IMAGE_HEIGHT = 300


def upgrade_to_larger_image(url):
    """Poskuša pretvoriti thumbnail URL v polno velikost.
    Vrstno preverja različne vzorce; vrne najboljšega.
    """
    if not url:
        return url

    # NetMedia pattern (sobotainfo, mariborinfo, ...)
    url = re.sub(r'/styles/\d+x\d+/public/', '/styles/1024x585/public/', url)

    # WordPress thumbnail pattern: name-WIDTHxHEIGHT.ext
    url = re.sub(r'-(\d{2,4})x(\d{2,4})(\.[a-zA-Z]+)(\?|$)', r'\3\4', url)

    # Drupal image styles: /styles/STYLE/public/... → /sites/default/files/... (original)
    url = re.sub(r'/sites/[^/]+/files/styles/[^/]+/public/', r'/sites/default/files/', url)

    # MGML cache pattern: /media/cache/CC/CC/HASH.jpg — cache je vedno tisti razrez,
    # poskusi zamenjati z 'big' ali pa odstrani (ni vedno mogoče, ker je hash-based)
    if '/media/cache/' in url:
        # Poskusi /media/cache/big/... ali /media/cache/large/...
        for size_name in ('big', 'large', 'full', 'original'):
            new = re.sub(r'/media/cache/[^/]+/', f'/media/cache/{size_name}/', url, count=1)
            if new != url:
                url = new
                break

    # MojaObcina pattern: /uploads/thumbnails/... → /uploads/full/... ali /uploads/...
    url = re.sub(r'/uploads/thumbnails/', '/uploads/', url)
    url = re.sub(r'/uploads/thumbs/', '/uploads/', url)
    url = re.sub(r'/uploads/small/', '/uploads/large/', url)

    # imgresizer / cdn-resize: /thumbs/WIDTHxHEIGHT/...
    url = re.sub(r'/thumbs/\d+x\d+/', '/', url)
    url = re.sub(r'/thumbnail/\d+x\d+/', '/original/', url)

    # Cloudinary: /image/upload/w_400/... → /image/upload/w_1200/...
    url = re.sub(r'(/image/upload/[^/]*?)w_\d+', r'\1w_1200', url)
    url = re.sub(r'(/image/upload/[^/]*?)c_thumb,', r'\1c_fill,', url)

    # Generic ?w=NNN&h=NNN (samo če sta majhna)
    m = re.search(r'[?&](w|width)=(\d+)', url)
    if m and int(m.group(2)) < MIN_IMAGE_WIDTH:
        url = re.sub(r'([?&])(w|width)=\d+', f'\\1\\2={max(int(m.group(2)) * 2, 1024)}', url)
    m = re.search(r'[?&](h|height)=(\d+)', url)
    if m and int(m.group(2)) < MIN_IMAGE_HEIGHT:
        url = re.sub(r'([?&])(h|height)=\d+', f'\\1\\2={max(int(m.group(2)) * 2, 600)}', url)

    return url


def _get_image_dimensions(url, timeout=5):
    """Vrne (width, height) slike, ali None če nerazlokno.

    Uporablja Pillow z byte-stream-om (samo dovolj za header parse).
    Slika do 100KB se prebere v celoti, večja samo header.
    """
    try:
        resp = requests.get(url, timeout=timeout, stream=True,
                             headers={"User-Agent": USER_AGENT,
                                      "Range": "bytes=0-65536"})
        if resp.status_code not in (200, 206):
            return None
        from io import BytesIO
        try:
            from PIL import Image
        except ImportError:
            return None
        data = resp.raw.read(65536)
        try:
            img = Image.open(BytesIO(data))
            return img.size  # (w, h)
        except Exception:
            return None
    except Exception:
        return None


def _image_meets_min_size(url):
    """Preveri če slika dosega MIN_IMAGE_WIDTH × MIN_IMAGE_HEIGHT.
    Vrne True (dovolj velika), False (premajhna), None (ne moremo preveriti)."""
    dims = _get_image_dimensions(url)
    if dims is None:
        return None  # nezanesljivo
    w, h = dims
    return w >= MIN_IMAGE_WIDTH and h >= MIN_IMAGE_HEIGHT


def _is_valid_image_url(url):
    """Preveri ali URL kaže na sliko (vsaj po končnici/tipu)."""
    if not url or not isinstance(url, str):
        return False
    # Filtriraj tracking pixle, logote ki so verjetno samo ikone, prazne slike
    bad_keywords = ["pixel", "1x1", "blank", "spacer", "transparent", "tracking"]
    url_lower = url.lower()
    if any(b in url_lower for b in bad_keywords):
        return False
    return True


def _fetch_html(url, headers=None, timeout=8):
    """Pridobi HTML iz URL-ja. Default 8s — kompromis med hitrostjo in zanesljivostjo."""
    try:
        resp = requests.get(
            url,
            headers=headers or DEFAULT_HEADERS,
            timeout=(timeout, timeout),  # (connect, read) timeouts
            allow_redirects=True,
        )
        if resp.status_code == 200:
            return resp.text
    except Exception as e:
        logger.debug(f"  Napaka pri pridobivanju {url}: {e}")
    return None


def _extract_og_image(html, base_url):
    """Pridobi og:image / twitter:image iz HTML-ja."""
    if not html:
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")

        # og:image (lahko jih je več - vzemi prvega)
        # Preveri tudi og:image:width hint da preskočimo jasno premajhne
        og_w_tag = soup.find("meta", property="og:image:width")
        og_h_tag = soup.find("meta", property="og:image:height")
        try:
            og_w = int(og_w_tag.get("content")) if og_w_tag else None
            og_h = int(og_h_tag.get("content")) if og_h_tag else None
        except (ValueError, AttributeError):
            og_w = og_h = None

        for prop in ["og:image", "og:image:secure_url", "og:image:url"]:
            tag = soup.find("meta", property=prop)
            if tag and tag.get("content"):
                url = urljoin(base_url, tag["content"])
                if _is_valid_image_url(url):
                    # Če imamo dim hint in je premajhna, poskusi upgrade
                    if og_w and og_h and (og_w < MIN_IMAGE_WIDTH or og_h < MIN_IMAGE_HEIGHT):
                        url = upgrade_to_larger_image(url)
                    else:
                        url = upgrade_to_larger_image(url)
                    return url

        # twitter:image
        for name in ["twitter:image", "twitter:image:src"]:
            tag = soup.find("meta", attrs={"name": name})
            if tag and tag.get("content"):
                url = urljoin(base_url, tag["content"])
                if _is_valid_image_url(url):
                    return upgrade_to_larger_image(url)

        # link rel="image_src"
        link = soup.find("link", rel="image_src")
        if link and link.get("href"):
            url = urljoin(base_url, link["href"])
            if _is_valid_image_url(url):
                return upgrade_to_larger_image(url)

        # JSON-LD schema.org Event.image
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json
                data = json.loads(script.string or "{}")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    img = item.get("image")
                    if isinstance(img, str):
                        url = urljoin(base_url, img)
                        if _is_valid_image_url(url):
                            return upgrade_to_larger_image(url)
                    elif isinstance(img, list) and img:
                        first = img[0]
                        if isinstance(first, str):
                            return upgrade_to_larger_image(urljoin(base_url, first))
                        if isinstance(first, dict) and first.get("url"):
                            return upgrade_to_larger_image(urljoin(base_url, first["url"]))
                    elif isinstance(img, dict) and img.get("url"):
                        return upgrade_to_larger_image(urljoin(base_url, img["url"]))
            except Exception:
                continue

    except Exception as e:
        logger.debug(f"  Parsing error: {e}")
    return None


def _extract_largest_content_image(html, base_url):
    """Najdi največjo sliko v article/main/content."""
    if not html:
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")

        # Iščemo v vsebinskih sekcijah
        containers = (
            soup.find("article")
            or soup.find("main")
            or soup.find(class_=re.compile(r"(content|post|entry|event|detail)", re.I))
            or soup.body
        )
        if not containers:
            return None

        candidates = []
        for img in containers.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            if not src or src.startswith("data:"):
                continue
            url = urljoin(base_url, src)
            if not _is_valid_image_url(url):
                continue
            # Filtriraj očitno majhne ikone
            w = img.get("width", "0")
            h = img.get("height", "0")
            try:
                w_int, h_int = int(str(w).replace("px", "") or 0), int(str(h).replace("px", "") or 0)
                if 0 < w_int < 100 or 0 < h_int < 100:
                    continue
            except ValueError:
                pass
            # Filtriraj logote
            if "logo" in src.lower() or "icon" in src.lower():
                continue
            candidates.append(url)

        if candidates:
            return candidates[0]

    except Exception as e:
        logger.debug(f"  Content image error: {e}")
    return None


def _is_facebook_url(url):
    if not url:
        return False
    parsed = urlparse(url)
    return any(d in parsed.netloc.lower() for d in ["facebook.com", "fb.com", "fb.me"])


def _try_fetch_facebook_image(fb_url):
    """Poskusi pridobiti sliko iz FB posta z facebookexternalhit user agentom."""
    html = _fetch_html(fb_url, headers=FB_HEADERS)
    if html:
        img = _extract_og_image(html, fb_url)
        if img:
            return img
    return None


def find_fallback_image(event, force_fetch=False):
    """
    Poišči nadomestno sliko za dogodek.

    Vrstni red iskanja:
      1. og:image iz source_url ali detail_url
      2. Facebook post slika
      3. Največja vsebinska slika
      4. Slika prizorišča (source_id)
      5. Kategorijska simbolna slika
      6. Privzeta slika

    `force_fetch=True` pomeni vedno poskusi pridobiti od vira (uporabniški klik).
    """
    urls_to_try = []
    if event.source_url:
        urls_to_try.append(event.source_url)
    if event.detail_url and event.detail_url != event.source_url:
        urls_to_try.append(event.detail_url)

    for url in urls_to_try:
        # FB ima poseben handling
        if _is_facebook_url(url):
            img = _try_fetch_facebook_image(url)
            if img:
                logger.debug(f"  FB slika za: {event.title[:40]}")
                return img
            continue

        html = _fetch_html(url)
        if not html:
            continue

        # 1. og:image / twitter:image / JSON-LD
        img = _extract_og_image(html, url)
        if img:
            logger.debug(f"  og:image za: {event.title[:40]}")
            return img

        # 2. Največja vsebinska slika
        img = _extract_largest_content_image(html, url)
        if img:
            logger.debug(f"  content image za: {event.title[:40]}")
            return img

    # 3. Slika prizorišča
    if event.source_id and event.source_id in VENUE_IMAGE_MAP:
        return VENUE_IMAGE_MAP[event.source_id]

    # 4. Kategorijska
    if event.event_type and event.event_type in CATEGORY_IMAGE_MAP:
        return CATEGORY_IMAGE_MAP[event.event_type]

    # 5. Privzeta
    return DEFAULT_IMAGE


def _is_junk_description(text):
    """Prepoznaj smetje (FB statistika, navigacija, itd.) namesto opisa."""
    if not text or len(text.strip()) < 50:
        return True
    t = text.lower()
    # FB-tipične fraze ki niso opis
    junk_phrases = [
        "ljudi udeležilo", "ljudi je zainteresiranih",
        "people responded", "people interested", "people went",
        "udeleženci", "zainteresirani",
        "log in or sign up", "prijavi se ali se registriraj",
        "see more on facebook", "see more posts",
        "ogled več objav",
        "all reactions", "vse reakcije",
        "comments", "shares", "komentarji", "deli",
    ]
    junk_hits = sum(1 for p in junk_phrases if p in t)
    if junk_hits >= 2:
        return True
    # Zelo malo besed (verjetno statistika ali navigacija)
    word_count = len(text.split())
    if word_count < 10:
        return True
    # Vsebuje samo številke + besede kot "ljudi"
    import re as _re
    if _re.match(r"^[\d\s,.\-]+(ljudi|people|attended|going|interested)", t):
        return True
    return False


def normalize_description(text):
    """Pomerja in normalizira besedilo opisa.

    - \\xa0 (NBSP) → navadni presledek
    - \\r\\n / \\r → \\n
    - Stripa whitespace na začetku/koncu vsake vrstice
    - Združi >2 zaporedne nove vrstice v 2
    - Združi >1 zaporedna presledka v 1 (znotraj vrstice)
    - Vstavi presledek za piko/vejico/dvopičjem če zlepljen z besedo
      (popravlja "končnice«.Sreča" → "končnice«. Sreča")
    """
    import re as _re
    if not text:
        return text
    # NBSP & ostali invisible whitespace
    text = text.replace("\xa0", " ").replace("\u200b", "")
    # CRLF / CR
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Trim every line
    lines = [ln.strip() for ln in text.split("\n")]
    # Collapse 3+ blank lines → max 1 blank
    out = []
    blank_run = 0
    for ln in lines:
        if not ln:
            blank_run += 1
            if blank_run <= 1:
                out.append("")
        else:
            blank_run = 0
            # Collapse internal multiple spaces
            ln = _re.sub(r"[ \t]{2,}", " ", ln)
            out.append(ln)
    text = "\n".join(out).strip()
    # Vstavi presledek če je punctuation zlepljen z naslednjo besedo (vélika črka)
    # Npr. "končnice«.Sreča" → "končnice«. Sreča"
    text = _re.sub(r"([.!?»\"\']+)([A-ZČŠŽĆĐ])", r"\1 \2", text)
    text = _re.sub(r"([:,;])([A-Za-zČŠŽčšž])", r"\1 \2", text)
    return text


def extract_description(html, base_url=None):
    """Pridobi opis iz HTML-ja (og:description, meta description, JSON-LD, article body)."""
    if not html:
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")
        candidates = []

        # 1. JSON-LD schema.org Event.description (najboljši strukturirani vir)
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json
                data = json.loads(script.string or "{}")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict) and item.get("description"):
                        d = item["description"]
                        if isinstance(d, str):
                            candidates.append(("json-ld", d.strip()))
            except Exception:
                continue

        # 2. og:description
        for prop in ["og:description"]:
            tag = soup.find("meta", property=prop)
            if tag and tag.get("content"):
                candidates.append(("og:description", tag["content"].strip()))

        # 3. twitter:description / meta description
        for name in ["twitter:description", "description"]:
            tag = soup.find("meta", attrs={"name": name})
            if tag and tag.get("content"):
                candidates.append((name, tag["content"].strip()))

        # 4. Glavni vsebinski element - prvih nekaj odstavkov
        # Uporabi separator=' ' za get_text da prepreči zlepljanje besed
        article = soup.find("article") or soup.find("main")
        if article:
            paragraphs = []
            for p in article.find_all("p", limit=10):
                text = p.get_text(separator=" ", strip=True)
                if len(text) > 30:
                    paragraphs.append(text)
                if sum(len(t) for t in paragraphs) > 500:
                    break
            if paragraphs:
                candidates.append(("article", "\n\n".join(paragraphs)))

        # Izberi NAJBOLJŠEGA kandidata: najdaljši nesmetni opis
        # (raje daljši, ker je bolj informativen)
        valid = []
        for source, desc in candidates:
            if not _is_junk_description(desc):
                normalized = normalize_description(desc)
                if normalized:
                    valid.append((source, normalized, len(normalized)))
        if valid:
            # Sortiraj po dolžini — daljši najprej, ampak preferiraj JSON-LD/og če sta dovolj dolga
            # Pravilo: če je article > 200 znakov, vzemi tega. Sicer vzemi prvega meta tag.
            article_candidates = [v for v in valid if v[0] == "article" and v[2] > 200]
            if article_candidates:
                article_candidates.sort(key=lambda x: x[2], reverse=True)
                logger.debug(f"  Opis iz article (dolžina {article_candidates[0][2]}): {article_candidates[0][1][:60]}...")
                return article_candidates[0][1]
            # Sicer izberi najdaljšega meta opisa
            valid.sort(key=lambda x: x[2], reverse=True)
            logger.debug(f"  Opis iz {valid[0][0]} (dolžina {valid[0][2]}): {valid[0][1][:60]}...")
            return valid[0][1]

    except Exception as e:
        logger.debug(f"  Description extraction error: {e}")
    return None


def find_fallback_description(event):
    """Poišči opis dogodka iz source_url ali detail_url."""
    urls = [u for u in [event.source_url, event.detail_url] if u]
    for url in urls:
        if _is_facebook_url(url):
            html = _fetch_html(url, headers=FB_HEADERS)
        else:
            html = _fetch_html(url)
        if html:
            desc = extract_description(html, url)
            if desc:
                return desc
    return None


def fill_missing_descriptions(db, limit=None, progress=None, max_seconds=180,
                              event_ids=None, percent_range=None,
                              parallel_workers=8):
    """Bulk fill manjkajočih opisov — z parallelnim fetchanjem.

    `parallel_workers`: število hkratnih HTTP zahtevkov (default 8).
                        Z 8 workerji obdelamo 200 dogodkov v ~3 min namesto 26.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from database.models import Event
    from datetime import date as date_cls, datetime as _dt
    from sqlalchemy import or_

    q = db.query(Event).filter(
        Event.date_start >= date_cls.today(),
        or_(Event.description == None, Event.description == "")
    )
    if event_ids is not None:
        if not event_ids:
            return 0, 0
        q = q.filter(Event.id.in_(event_ids))
    if limit:
        q = q.limit(limit)
    events = q.all()
    total = len(events)

    if progress is not None:
        progress.update({"enrich_phase": "descriptions",
                         "enrich_total": total, "enrich_index": 0})
    if total == 0:
        return 0, 0

    # Pripravi parallelne podatke (samo to kar workerji potrebujejo)
    work_items = [(e.id, e.source_url, e.detail_url) for e in events]

    def _worker(item):
        eid, source_url, detail_url = item
        for url in [u for u in (source_url, detail_url) if u]:
            try:
                if _is_facebook_url(url):
                    html = _fetch_html(url, headers=FB_HEADERS, timeout=8)
                else:
                    html = _fetch_html(url, timeout=8)
                if html:
                    desc = extract_description(html, url)
                    if desc:
                        return (eid, desc)
            except Exception:
                continue
        return (eid, None)

    started = _dt.utcnow()
    results_map = {}
    completed = 0

    with ThreadPoolExecutor(max_workers=parallel_workers) as pool:
        futures = {pool.submit(_worker, it): it for it in work_items}
        for fut in as_completed(futures):
            completed += 1
            if (_dt.utcnow() - started).total_seconds() > max_seconds:
                logger.warning(f"Enrichment opisov ustavljen po {max_seconds}s ({completed}/{total})")
                break
            try:
                eid, desc = fut.result(timeout=15)
                if desc:
                    results_map[eid] = desc
            except Exception:
                pass
            if progress is not None:
                progress["enrich_index"] = completed
                if percent_range and total > 0:
                    start_pct, end_pct = percent_range
                    progress["percent"] = int(start_pct + (end_pct - start_pct) * completed / total)

    # Apliciraj rezultate v DB v eni transakciji
    filled = 0
    for event in events:
        if event.id in results_map:
            event.description = results_map[event.id]
            event.description_source = "scraped"
            filled += 1
    db.commit()
    return total, filled


def fill_missing_images(db, limit=100, progress=None, max_seconds=180,
                        event_ids=None, percent_range=None,
                        parallel_workers=8):
    """Bulk fill nadomestnih slik — parallelno."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from database.models import Event
    from datetime import date as date_cls, datetime as _dt

    q = db.query(Event).filter(
        Event.date_start >= date_cls.today(),
        (Event.image_url == None) | (Event.image_url == "")
    )
    if event_ids is not None:
        if not event_ids:
            return 0, 0, 0
        q = q.filter(Event.id.in_(event_ids))
    events = q.limit(limit).all()
    total = len(events)

    if progress is not None:
        progress.update({"enrich_phase": "images",
                         "enrich_total": total, "enrich_index": 0})
    if total == 0:
        return 0, 0, 0

    # Snapshot vseh potrebnih atributov (workerji ne dobijo SQLAlchemy objektov)
    work_items = [{
        "id": e.id,
        "source_url": e.source_url,
        "detail_url": e.detail_url,
        "source_id": e.source_id,
        "event_type": e.event_type,
        "title": e.title,
    } for e in events]

    def _worker(item):
        # Mini-event surrogate za find_fallback_image
        class _E:
            pass
        e = _E()
        e.id = item["id"]
        e.source_url = item["source_url"]
        e.detail_url = item["detail_url"]
        e.source_id = item["source_id"]
        e.event_type = item["event_type"]
        e.title = item["title"]
        try:
            url = find_fallback_image(e)
            if not url:
                return (item["id"], None, None, None)
            # Pridobi dimenzije
            dims = _get_image_dimensions(url) or (None, None)
            w, h = dims
            # Če je premajhna in URL ni že "upgraded", poskusi upgrade
            if w and h and (w < MIN_IMAGE_WIDTH or h < MIN_IMAGE_HEIGHT):
                bigger = upgrade_to_larger_image(url)
                if bigger and bigger != url:
                    new_dims = _get_image_dimensions(bigger) or (None, None)
                    if new_dims[0] and new_dims[0] >= w:  # vsaj enako velika
                        url = bigger
                        w, h = new_dims
            return (item["id"], url, w, h)
        except Exception:
            return (item["id"], None, None, None)

    started = _dt.utcnow()
    results_map = {}
    completed = 0

    with ThreadPoolExecutor(max_workers=parallel_workers) as pool:
        futures = {pool.submit(_worker, it): it for it in work_items}
        for fut in as_completed(futures):
            completed += 1
            if (_dt.utcnow() - started).total_seconds() > max_seconds:
                logger.warning(f"Enrichment slik ustavljen po {max_seconds}s ({completed}/{total})")
                break
            try:
                result = fut.result(timeout=15)
                eid, img_url = result[0], result[1]
                w, h = (result[2], result[3]) if len(result) >= 4 else (None, None)
                if img_url:
                    results_map[eid] = (img_url, w, h)
            except Exception:
                pass
            if progress is not None:
                progress["enrich_index"] = completed
                if percent_range and total > 0:
                    start_pct, end_pct = percent_range
                    progress["percent"] = int(start_pct + (end_pct - start_pct) * completed / total)

    real_count = 0
    fallback_count = 0
    for event in events:
        if event.id not in results_map:
            continue
        image_url, w, h = results_map[event.id]
        event.image_url = image_url
        event.image_width = w
        event.image_height = h
        if (image_url == DEFAULT_IMAGE
                or image_url in CATEGORY_IMAGE_MAP.values()
                or image_url in VENUE_IMAGE_MAP.values()):
            event.image_source = "fallback"
            fallback_count += 1
        else:
            event.image_source = "original"
            real_count += 1
    db.commit()
    return total, real_count, fallback_count
