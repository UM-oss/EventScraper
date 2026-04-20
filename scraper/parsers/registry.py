"""
Parser registry — registrira parserje po imenu in vrne ustrezni parser.
"""

import logging

logger = logging.getLogger("scraper")

_PARSER_REGISTRY = {}


class ParserRegistry:
    """Registracija in lookup parserjev."""

    @staticmethod
    def register(name):
        """Dekorator za registracijo parserja."""
        def decorator(cls):
            _PARSER_REGISTRY[name] = cls
            return cls
        return decorator

    @staticmethod
    def get(name):
        """Vrni razred parserja za podano ime."""
        return _PARSER_REGISTRY.get(name)

    @staticmethod
    def list_parsers():
        """Vrni seznam registriranih parserjev."""
        return list(_PARSER_REGISTRY.keys())


def get_parser(parser_type, source_id=None, fetcher=None):
    """
    Vrni instanco parserja za dani parser_type.
    Za specialne source-e (mgml, kinosiska) preveri tudi po source_id.

    Args:
        parser_type: tip parserja iz YAML config (html, rss, ical, ...)
        source_id: ID vira (za specialne parserje)
        fetcher: objekt z fetch_page() za prenos strani

    Returns:
        BaseParser instanca ali None
    """
    # Najprej preveri po source_id (za specialne parserje)
    if source_id:
        cls = _PARSER_REGISTRY.get(source_id)
        if cls:
            return cls(fetcher=fetcher)

    # Nato po parser_type
    cls = _PARSER_REGISTRY.get(parser_type)
    if cls:
        return cls(fetcher=fetcher)

    logger.warning(f"Parser za tip '{parser_type}' (source: {source_id}) ni registriran")
    return None
