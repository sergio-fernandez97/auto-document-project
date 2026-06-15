"""
user_service.py – reference module (already documented).

This file is used as a style guide by the auto-documentation workflow.
Claude will read the docstrings here and replicate their format, tone,
and section structure when documenting other scripts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class User:
    """Represents an authenticated application user.

    Attributes:
        user_id: Unique numeric identifier assigned at registration.
        username: Display name chosen by the user (3-32 characters).
        email: Verified e-mail address used for login and notifications.
        roles: Set of permission roles granted to this user.
        created_at: UTC timestamp of when the account was created.
    """

    user_id: int
    username: str
    email: str
    roles: set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def has_role(self, role: str) -> bool:
        """Check whether the user holds a specific permission role.

        Args:
            role: The role name to look up (e.g. ``"admin"``).

        Returns:
            True if the role is present, False otherwise.
        """
        return role in self.roles

    def add_role(self, role: str) -> None:
        """Grant a permission role to this user.

        Args:
            role: The role name to add (e.g. ``"editor"``).

        Raises:
            ValueError: If *role* is an empty string.
        """
        if not role:
            raise ValueError("role must be a non-empty string.")
        self.roles.add(role)


class UserRepository:
    """In-memory store for :class:`User` objects.

    Intended for testing and local development. For production use,
    replace with a database-backed implementation that shares the same
    interface.

    Attributes:
        _store: Internal dict mapping user IDs to User instances.
    """

    def __init__(self) -> None:
        """Initialise an empty repository."""
        self._store: dict[int, User] = {}

    def save(self, user: User) -> None:
        """Persist a user object (insert or update).

        Args:
            user: The :class:`User` instance to store.
        """
        self._store[user.user_id] = user

    def find_by_id(self, user_id: int) -> User | None:
        """Retrieve a user by their unique identifier.

        Args:
            user_id: The numeric ID to look up.

        Returns:
            The matching :class:`User`, or ``None`` if not found.
        """
        return self._store.get(user_id)

    def delete(self, user_id: int) -> bool:
        """Remove a user from the repository.

        Args:
            user_id: ID of the user to delete.

        Returns:
            True if the user existed and was removed, False if not found.
        """
        if user_id in self._store:
            del self._store[user_id]
            return True
        return False


def hash_password(plain: str, salt: str) -> str:
    """Return a deterministic salted hash of *plain* for demonstration purposes.

    .. warning::
        This is **not** a production-safe hashing scheme. Use
        ``bcrypt`` or ``argon2`` for real applications.

    Args:
        plain: The raw password string supplied by the user.
        salt: A random string appended before hashing.

    Returns:
        A hex-encoded SHA-256-like hash string (mocked here for clarity).

    Raises:
        ValueError: If either *plain* or *salt* is empty.
    """
    if not plain or not salt:
        raise ValueError("Both plain and salt must be non-empty strings.")
    # Mock implementation – replace with a real hasher in production
    return f"hashed::{salt}::{hash(plain + salt) & 0xFFFFFFFF:08x}"