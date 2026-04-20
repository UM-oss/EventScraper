"""
Parsers paket — vsak vir ima svoj parser modul.
Registry vzorec za registracijo in lookup parserjev.
"""

from scraper.parsers.registry import ParserRegistry, get_parser

__all__ = ["ParserRegistry", "get_parser"]
