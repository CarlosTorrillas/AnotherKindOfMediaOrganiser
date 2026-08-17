"""Application factory for the read-only browser interface."""

from typing import Any

from flask import Flask


def create_app(config: dict[str, Any] | None = None) -> Flask:
    """Create the local, read-only Flask presentation adapter."""
    app = Flask(__name__)
    if config:
        app.config.from_mapping(config)

    from another_kind_of_media_organiser.presentation.web.routes import browser

    app.register_blueprint(browser)
    return app


__all__ = ["create_app"]
