import os

from itsdangerous import BadSignature, SignatureExpired
from itsdangerous import URLSafeTimedSerializer

from database.models import User


TOKEN_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def _get_serializer():
    secret_key = os.getenv("SECRET_KEY")

    if not secret_key:
        raise RuntimeError(
            "SECRET_KEY is not configured."
        )

    return URLSafeTimedSerializer(
        secret_key,
        salt="nova-ai-auth",
    )


def create_auth_token(user: User):
    serializer = _get_serializer()

    return serializer.dumps({
        "user_id": user.id,
        "username": user.username,
    })


def verify_auth_token(token: str):
    if not token:
        return None, "Missing authentication token"

    try:
        serializer = _get_serializer()

        data = serializer.loads(
            token,
            max_age=TOKEN_MAX_AGE,
        )

    except SignatureExpired:
        return None, "Authentication token has expired"

    except BadSignature:
        return None, "Invalid authentication token"

    except Exception:
        return None, "Failed to verify authentication token"

    user_id = data.get("user_id")

    if not isinstance(user_id, int):
        return None, "Invalid authentication token"

    user = User.query.get(user_id)

    if not user:
        return None, "User no longer exists"

    return user, None


def get_bearer_token(request):
    authorization = request.headers.get(
        "Authorization",
        "",
    )

    if not authorization.startswith("Bearer "):
        return None

    token = authorization[7:].strip()

    if not token:
        return None

    return token