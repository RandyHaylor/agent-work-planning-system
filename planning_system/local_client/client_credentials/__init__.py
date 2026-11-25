"""client_credentials: the install's quote key."""
from .file_client_credentials import FileClientCredentials
from .interface import ClientCredentialsInterface

__all__ = ["ClientCredentialsInterface", "FileClientCredentials"]
