"""
Monitoring zdravja virov dogodkov.

Periodično preverja:
- Ali vir vrača podatke (HTTP status, število dogodkov)
- Ali se je struktura spremenila (0 dogodkov ko prej ni bilo 0)
- Ali so feedi dosegljivi
- Beleži neobdelane URL-je za prihodnje reševanje

Uporaba:
    python3 -m scraper.health_check          # preveri vse vire
    python3 -m scraper.health_check --report # izpiši poročilo
"""

import os
import sys
import time
import logging
from datetime import datetime, date, timedelta

import requests
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import (
    Session, Event, ScrapeLog, SourceHealth, UnprocessedUrl, init_db
)
from scraper.engine import ScraperEngine, SourceConfig

logger = logging.getLogger("health_check")


class SourceHealthChecker:
    """Preverja zdravje vseh virov"""

    def __init__(self):
        self.engine = ScraperEngine()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "EventScraper/1.0 (health-check)"
        })

    def check_all(self):
        """Preveri vse vire in posodobi health tabelo"""
        init_db()
        sources = self.engine.load_sources()
        results = []

        for source in sources:
            result = self.check_source(source)
            results.append(result)
            time.sleep(0.5)  # Ne obremenjuj strežnikov

        # Zapiši neobdelane URL-je za manual vire
        self._record_unprocessed_urls(sources)

        return results

    def check_source(self, config):
        """Preveri en vir in posodobi health status"""
        db = Session()
        result = {
            "source_id": config.id,
            "name": config.name,
            "parser_type": config.parser_type,
        }

        try:
            # Najdi ali ustvari health zapis
            health = db.query(SourceHealth).get(config.id)
            if not health:
                health = SourceHealth(
                    source_id=config.id,
                    source_name=config.name,
                    parser_type=config.parser_type,
                    list_url=config.list_url,
                    feed_url=getattr(config, 'feed_url', ''),
                )
                db.add(health)

            health.last_check = datetime.utcnow()
            health.parser_type = config.parser_type
            health.list_url = config.list_url
            health.feed_url = getattr(config, 'feed_url', '')

            # Manual vire samo registriraj, ne preverjaj
            if config.parser_type == "manual":
                health.status = "manual"
                health.notes = f"Ročni vir — URL: {config.list_url}"
                db.commit()
                result["status"] = "manual"
                result["message"] = "Ročni vir, preskočen"
                return result

            # Preveri dostopnost URL-ja
            check_url = getattr(config, 'feed_url', '') or config.list_url
            try:
                resp = self.session.head(check_url, timeout=10, allow_redirects=True)
                result["http_status"] = resp.status_code

                if resp.status_code >= 400:
                    health.last_error = datetime.utcnow()
                    health.last_error_msg = f"HTTP {resp.status_code}"
                    health.consecutive_errors += 1
                    health.error_count += 1

                    # Zapiši neobdelan URL
                    self._record_failed_url(
                        db, config.id, check_url,
                        reason=f"http-{resp.status_code}",
                        response_code=resp.status_code
                    )

                    if health.consecutive_errors >= 3:
                        health.status = "broken"
                    else:
                        health.status = "degraded"

                    result["status"] = health.status
                    result["message"] = f"HTTP {resp.status_code}"
                    db.commit()
                    return result

            except requests.RequestException as e:
                health.last_error = datetime.utcnow()
                health.last_error_msg = str(e)[:500]
                health.consecutive_errors += 1
                health.error_count += 1

                self._record_failed_url(
                    db, config.id, check_url,
                    reason="timeout" if "timeout" in str(e).lower() else "connection-error",
                    response_code=None
                )

                if health.consecutive_errors >= 3:
                    health.status = "broken"
                else:
                    health.status = "degraded"

                result["status"] = health.status
                result["message"] = str(e)[:100]
                db.commit()
                return result

            # Preveri zadnji scrape iz logov
            recent_log = db.query(ScrapeLog).filter(
                ScrapeLog.source_id == config.id,
                ScrapeLog.status.in_(["success", "running"]),
            ).order_by(ScrapeLog.started_at.desc()).first()

            if recent_log:
                health.last_events_found = recent_log.events_found or 0
                result["last_events"] = health.last_events_found
            else:
                result["last_events"] = 0

            # Preveri koliko prihodnjih dogodkov imamo iz tega vira
            future_count = db.query(Event).filter(
                Event.source_id == config.id,
                Event.date_start >= date.today()
            ).count()
            result["future_events"] = future_count

            # Trend iz zadnjih 7 dni
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_logs = db.query(ScrapeLog).filter(
                ScrapeLog.source_id == config.id,
                ScrapeLog.started_at >= week_ago,
            ).all()

            success_logs = [l for l in recent_logs if l.status == "success"]
            error_logs = [l for l in recent_logs if l.status == "error"]
            health.success_count = len(success_logs)
            health.error_count = len(error_logs)

            if success_logs:
                health.total_events_7d = sum(l.events_found or 0 for l in success_logs)
                health.avg_events = health.total_events_7d / len(success_logs)

            # Določi status
            if future_count > 0 and health.consecutive_errors == 0:
                health.status = "healthy"
                health.consecutive_errors = 0
                health.last_success = datetime.utcnow()
            elif future_count == 0 and health.last_events_found == 0:
                health.status = "degraded"
                health.notes = "0 prihodnjih dogodkov"
            else:
                health.status = "healthy"
                health.consecutive_errors = 0
                health.last_success = datetime.utcnow()

            result["status"] = health.status
            result["message"] = f"{future_count} prihodnjih dogodkov"

            db.commit()

        except Exception as e:
            result["status"] = "error"
            result["message"] = str(e)[:200]
            logger.error(f"Napaka pri preverjanju {config.id}: {e}")
        finally:
            db.close()

        return result

    def _record_failed_url(self, db, source_id, url, reason, response_code=None):
        """Zapiši neuspel URL v bazo"""
        # Preveri ali že obstaja
        existing = db.query(UnprocessedUrl).filter(
            UnprocessedUrl.source_id == source_id,
            UnprocessedUrl.url == url,
            UnprocessedUrl.status == "pending",
        ).first()

        if not existing:
            record = UnprocessedUrl(
                source_id=source_id,
                url=url,
                reason=reason,
                response_code=response_code,
                status="pending",
            )
            db.add(record)

    def _record_unprocessed_urls(self, sources):
        """Zapiši URL-je manual virov kot neobdelane"""
        db = Session()
        for source in sources:
            if source.parser_type == "manual":
                existing = db.query(UnprocessedUrl).filter(
                    UnprocessedUrl.source_id == source.id,
                    UnprocessedUrl.url == source.list_url,
                ).first()

                if not existing:
                    record = UnprocessedUrl(
                        source_id=source.id,
                        url=source.list_url,
                        reason="no-parser",
                        content_type="html",
                        status="pending",
                    )
                    db.add(record)
        db.commit()
        db.close()

    def get_report(self):
        """Generiraj poročilo o zdravju virov"""
        db = Session()
        try:
            healths = db.query(SourceHealth).order_by(SourceHealth.status).all()

            report = {
                "checked_at": datetime.utcnow().isoformat(),
                "total_sources": len(healths),
                "by_status": {},
                "sources": [],
                "unprocessed_urls": [],
            }

            for h in healths:
                status = h.status or "unknown"
                report["by_status"][status] = report["by_status"].get(status, 0) + 1

                source_info = {
                    "id": h.source_id,
                    "name": h.source_name,
                    "parser_type": h.parser_type,
                    "status": status,
                    "last_check": h.last_check.isoformat() if h.last_check else None,
                    "last_success": h.last_success.isoformat() if h.last_success else None,
                    "last_events_found": h.last_events_found or 0,
                    "consecutive_errors": h.consecutive_errors or 0,
                    "url": h.feed_url or h.list_url,
                }

                if h.last_error_msg:
                    source_info["last_error"] = h.last_error_msg[:200]

                report["sources"].append(source_info)

            # Neobdelani URL-ji
            unprocessed = db.query(UnprocessedUrl).filter(
                UnprocessedUrl.status == "pending"
            ).all()

            for u in unprocessed:
                report["unprocessed_urls"].append({
                    "source_id": u.source_id,
                    "url": u.url,
                    "reason": u.reason,
                    "discovered_at": u.discovered_at.isoformat() if u.discovered_at else None,
                })

            return report

        finally:
            db.close()

    def print_report(self):
        """Izpiši berljivo poročilo"""
        report = self.get_report()

        print("=" * 70)
        print(f"  ZDRAVJE VIROV — {report['checked_at'][:19]}")
        print(f"  Skupaj virov: {report['total_sources']}")
        print("=" * 70)

        # Po statusih
        print("\nSTATUS:")
        status_icons = {
            "healthy": "✅",
            "degraded": "⚠️ ",
            "broken": "❌",
            "manual": "📝",
            "unknown": "❓",
        }
        for status, count in sorted(report["by_status"].items()):
            icon = status_icons.get(status, "?")
            print(f"  {icon} {status:12s}: {count}")

        # Problematični viri
        problems = [s for s in report["sources"] if s["status"] in ("broken", "degraded")]
        if problems:
            print(f"\n{'─' * 70}")
            print("PROBLEMI:")
            for s in problems:
                print(f"  ❌ {s['id']:30s} [{s['parser_type']:15s}] {s.get('last_error', 'ni podatkov')[:50]}")
                print(f"     URL: {s['url'][:70]}")

        # Zdravi avtomatizirani viri
        healthy = [s for s in report["sources"]
                   if s["status"] == "healthy" and s["parser_type"] != "manual"]
        if healthy:
            print(f"\n{'─' * 70}")
            print(f"ZDRAVI AVTOMATIZIRANI ({len(healthy)}):")
            for s in healthy:
                print(f"  ✅ {s['id']:30s} [{s['parser_type']:15s}] {s['last_events_found']:3d} dogodkov")

        # Ročni viri brez parserja
        manual = [s for s in report["sources"] if s["status"] == "manual"]
        if manual:
            print(f"\n{'─' * 70}")
            print(f"ROČNI VIRI — BREZ PARSERJA ({len(manual)}):")
            for s in manual:
                print(f"  📝 {s['id']:30s} {s['url'][:50]}")

        # Neobdelani URL-ji
        if report["unprocessed_urls"]:
            print(f"\n{'─' * 70}")
            print(f"NEOBDELANI URL-JI ({len(report['unprocessed_urls'])}):")
            for u in report["unprocessed_urls"][:20]:
                print(f"  📋 {u['source_id']:30s} [{u['reason']:15s}] {u['url'][:50]}")

        print(f"\n{'=' * 70}")


def main():
    """CLI vstopna točka"""
    import argparse
    parser = argparse.ArgumentParser(description="Preveri zdravje virov dogodkov")
    parser.add_argument("--report", action="store_true", help="Samo izpiši poročilo (brez preverjanja)")
    parser.add_argument("--json", action="store_true", help="Izpiši JSON poročilo")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    checker = SourceHealthChecker()

    if not args.report:
        print("Preverjam zdravje virov...")
        results = checker.check_all()
        print(f"Preverjenih: {len(results)} virov\n")

    if args.json:
        import json
        print(json.dumps(checker.get_report(), indent=2, ensure_ascii=False))
    else:
        checker.print_report()


if __name__ == "__main__":
    main()
