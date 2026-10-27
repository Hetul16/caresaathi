"""Errors the API turns into problem+json. Services raise these; they never build HTTP responses."""
from __future__ import annotations


class ServiceError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
