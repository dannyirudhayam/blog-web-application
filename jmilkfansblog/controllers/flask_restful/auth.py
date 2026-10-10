from itsdangerous import TimedJSONWebSignatureSerializer as Serializer

from flask import abort, current_app
from flask.ext.restful import Resource

from jmilkfansblog.controllers.flask_restful import parsers
from jmilkfansblog.controllers.flask_restful.token_auth import (
    authenticated_user)
from jmilkfansblog.db.sqlalchemy.models import User


def issue_token(user):
    """Create a signed token for `user` that expires after the configured time.

    Returns the dict that the auth endpoints send back to the client.
    """

    expires_in = current_app.config.get('TOKEN_EXPIRES_IN', 600)
    serializer = Serializer(
        current_app.config['SECRET_KEY'],
        expires_in=expires_in)
    # dumps() returns bytes on Python 3; JSON needs a str.
    token = serializer.dumps({'id': user.id}).decode('utf-8')
    return {'token': token, 'expires_in': expires_in}


class AuthApi(Resource):
    """Login: exchange a username and password for a token."""

    def post(self):
        args = parsers.user_post_parser.parse_args()
        user = User.query.filter_by(username=args['username']).first()

        # Unknown user or wrong password: always answer 401.
        if user is None or not user.check_password(args['password']):
            abort(401)

        return issue_token(user)


class TokenRefreshApi(Resource):
    """Exchange a still-valid token for a fresh one (new expiry time)."""

    def post(self):
        # 401 if the token is missing, invalid or already expired.
        user = authenticated_user()
        return issue_token(user)