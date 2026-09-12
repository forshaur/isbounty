"""Thin wrapper over stdlib logging so every module gets a consistent
name-spaced logger without repeating config. ponytail: stdlib does this,
no custom logging framework."""
import logging
import sys

_CONFIGURED = False


def _configure_once():
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure_once()
    return logging.getLogger(name)
