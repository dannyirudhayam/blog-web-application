from flask import abort, request

from jmilkfansblog.db.sqlalchemy.models import User


def get_token_from_request():
    """Return the token from the Authorization header or the JSON body."""

    header = request.headers.get('Authorization', '')
    if header.startswith('Bearer '):
        return header[len('Bearer '):].strip()

    # Backward compatible: the old way, a `token` field in the JSON body.
    body = request.get_json(silent=True) or {}
    return body.get('token')


def authenticated_user():
    """Return the user the token belongs to, or abort with 401."""

    token = get_token_from_request()
    if not token:
        abort(401)

    user = User.verify_auth_token(token)
    if user is None:
        abort(401)

    return user