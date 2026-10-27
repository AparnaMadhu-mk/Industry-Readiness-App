"""Friendly, specific exceptions so the UI can show helpful messages."""


class AppError(Exception):
    """Base error. `message` is safe to show to the user."""

    status_code = 400

    def __init__(self, message, hint=None):
        super().__init__(message)
        self.message = message
        self.hint = hint


class UnsupportedFormatError(AppError):
    pass


class FileTooLargeError(AppError):
    status_code = 413


class UnreadableDocumentError(AppError):
    status_code = 422


class AnalysisError(AppError):
    status_code = 500
