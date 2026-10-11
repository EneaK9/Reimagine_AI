"""
ReimagineAI - Password hashing tests (PBKDF2 + legacy SHA-256 upgrade path)
No database needed: a tiny fake session stands in for SQLAlchemy.
"""
import base64
import hashlib
import secrets
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.models import User  # noqa: E402
from app.services import user_service as user_service_module  # noqa: E402
from app.services.user_service import user_service  # noqa: E402

PASSWORD = "correct horse battery staple"


class FakeSession:
    """Just enough of sqlalchemy.orm.Session for UserService.login/signup."""

    def __init__(self, user=None):
        self.user = user
        self.added = []
        self.commits = 0

    def scalar(self, stmt):
        return self.user

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        pass


def _legacy_hash(password: str):
    """Exact pre-upgrade format: sha256(password + hex salt) hex digest."""
    salt = secrets.token_hex(16)
    return hashlib.sha256(f"{password}{salt}".encode()).hexdigest(), salt


def _user(password_hash: str, salt: str) -> User:
    return User(
        id="user_test123456",
        username="tester",
        email="tester@example.com",
        password_hash=password_hash,
        salt=salt,
        token="old-token",
        created_at=datetime(2025, 1, 1),
        updated_at=datetime(2025, 1, 1),
    )


def test_new_hash_format_and_verify():
    encoded, salt_col = user_service._hash_password(PASSWORD)
    algorithm, iterations, salt_b64, hash_b64 = encoded.split("$")

    assert algorithm == "pbkdf2_sha256"
    assert int(iterations) == user_service_module.PBKDF2_ITERATIONS >= 310_000
    assert len(base64.b64decode(salt_b64)) == 16
    assert len(base64.b64decode(hash_b64)) == 32
    assert salt_col == salt_b64
    # Must fit the existing columns: password_hash VARCHAR(128), salt VARCHAR(64)
    assert len(encoded) <= 128 and len(salt_col) <= 64

    assert user_service._verify_password(PASSWORD, encoded, salt_col)
    assert not user_service._verify_password("wrong password", encoded, salt_col)
    assert not user_service._needs_rehash(encoded)


def test_hashes_are_salted():
    first, _ = user_service._hash_password(PASSWORD)
    second, _ = user_service._hash_password(PASSWORD)
    assert first != second


def test_legacy_hash_still_verifies():
    legacy, salt = _legacy_hash(PASSWORD)
    assert user_service._verify_password(PASSWORD, legacy, salt)
    assert not user_service._verify_password("wrong password", legacy, salt)
    assert not user_service._verify_password(PASSWORD, legacy, secrets.token_hex(16))
    assert user_service._needs_rehash(legacy)


@pytest.mark.parametrize(
    "stored",
    [
        "",
        "pbkdf2_sha256$",
        "pbkdf2_sha256$abc$AAAA$AAAA",
        "pbkdf2_sha256$1000$not-base64!$AAAA",
        "pbkdf2_sha256$0$AAAAAAAAAAAAAAAAAAAAAA==$AAAA",
        "pbkdf2_sha256$1000$AAAA$AAAA$extra",
    ],
)
def test_malformed_hashes_fail_closed(stored):
    assert user_service._verify_password(PASSWORD, stored, "salt") is False


def test_login_upgrades_legacy_hash():
    legacy, salt = _legacy_hash(PASSWORD)
    user = _user(legacy, salt)
    db = FakeSession(user)

    result = user_service.login(db, email="Tester@Example.com ", password=PASSWORD)

    assert result["id"] == user.id and result["token"] != "old-token"
    assert db.commits == 1  # upgrade persisted with the same commit as the token
    assert user.password_hash.startswith("pbkdf2_sha256$")
    assert user.salt == user.password_hash.split("$")[2]
    assert user_service._verify_password(PASSWORD, user.password_hash, user.salt)
    assert not user_service._verify_password("wrong password", user.password_hash, user.salt)

    # A second login keeps the (already current) hash
    upgraded = user.password_hash
    user_service.login(db, email=user.email, password=PASSWORD)
    assert user.password_hash == upgraded


def test_login_wrong_password_rejected_and_not_upgraded():
    legacy, salt = _legacy_hash(PASSWORD)
    user = _user(legacy, salt)
    db = FakeSession(user)

    with pytest.raises(ValueError, match="Invalid email or password"):
        user_service.login(db, email=user.email, password="wrong password")

    assert user.password_hash == legacy and user.salt == salt
    assert user.token == "old-token"
    assert db.commits == 0


def test_login_unknown_email_rejected():
    with pytest.raises(ValueError, match="Invalid email or password"):
        user_service.login(FakeSession(None), email="nobody@example.com", password=PASSWORD)


def test_login_rehashes_lower_iteration_count(monkeypatch):
    monkeypatch.setattr(user_service_module, "PBKDF2_ITERATIONS", 1_000)
    weak, weak_salt = user_service._hash_password(PASSWORD)
    monkeypatch.undo()

    assert user_service._needs_rehash(weak)
    user = _user(weak, weak_salt)
    user_service.login(FakeSession(user), email=user.email, password=PASSWORD)

    assert user.password_hash.split("$")[1] == str(user_service_module.PBKDF2_ITERATIONS)
    assert user_service._verify_password(PASSWORD, user.password_hash, user.salt)


def test_signup_stores_pbkdf2_hash():
    db = FakeSession(None)
    user_service.signup(db, username="newuser", email="New@Example.com", password=PASSWORD)

    (created,) = db.added
    assert created.email == "new@example.com"
    assert created.password_hash.startswith("pbkdf2_sha256$")
    assert user_service._verify_password(PASSWORD, created.password_hash, created.salt)
