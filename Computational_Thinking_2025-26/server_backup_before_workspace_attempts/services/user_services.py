from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

from database.db import db
from database.models import User


password_hasher = PasswordHasher()


def create_user(username, password):
    # Check if username already exists
    try:
        existing_user = User.query.filter_by(
            username=username
        ).first()
    except Exception:
        return None, "Database query failed"

    if existing_user:
        return None, "Username already exists"

    # Hash password before storing it
    try:
        password_hash = password_hasher.hash(password)
    except Exception:
        return None, "Failed to hash password"

    user = User(
        username=username,
        password=password_hash
    )

    try:
        db.session.add(user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return None, "Failed to create user"

    return user, None


def login_user(username, password):
    # Find user
    try:
        existing_user = User.query.filter_by(
            username=username
        ).first()
    except Exception:
        return None, "Database query failed"

    # User doesn't exist
    if not existing_user:
        return None, "Username not found"

    # Verify Argon2 password hash
    try:
        password_hasher.verify(
            existing_user.password,
            password
        )
    except VerifyMismatchError:
        return None, "Incorrect password"
    except VerificationError:
        return None, "Invalid password hash"
    except Exception:
        return None, "Password verification failed"

    # Rehash if Argon2 parameters have been upgraded
    try:
        if password_hasher.check_needs_rehash(existing_user.password):
            existing_user.password = password_hasher.hash(password)
            db.session.commit()
    except Exception:
        db.session.rollback()

    return existing_user, None