from flask import request
from flask.ext.restful import Resource, abort

from jmilkfansblog.controllers.flask_restful.token_auth import (
    authenticated_user)
from jmilkfansblog.db.sqlalchemy.models import db, Role, User


def user_has_role(user, role_name):
    """Return True if `user` has the role called `role_name`.

    NOTE: We can't use Flask-Principal's `admin_permission.can()` here.
    It reads the browser session, and a token request has no session.
    So we look at the roles of the user that the token identified.
    """

    return any(role.name == role_name for role in user.roles)


def require_admin():
    """Return the calling user, or stop the request.

    401 -> missing/invalid/expired token (raised by authenticated_user)
    403 -> valid token, but the user is not an admin
    """

    caller = authenticated_user()
    if not user_has_role(caller, 'admin'):
        abort(403, message='Admin role required.')
    return caller


def find_user_or_404(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        abort(404, message='User %s not found.' % username)
    return user


def serialize(user):
    return {'username': user.username,
            'roles': sorted(role.name for role in user.roles)}


class UserRolesApi(Resource):
    """Read and change the roles of one user. Admin only."""

    def get(self, username):
        require_admin()
        return serialize(find_user_or_404(username))

    def put(self, username):
        """Replace the user's roles with the list in the JSON body.

        Body example: {"roles": ["default", "poster"]}
        """

        caller = require_admin()
        target = find_user_or_404(username)

        body = request.get_json(silent=True) or {}
        names = body.get('roles')
        if not isinstance(names, list) or not all(
                isinstance(name, str) for name in names):
            abort(400, message='"roles" must be a list of role names.')

        # Every user must keep the `default` role (User.__init__ gives it
        # to everyone). Also remove duplicates but keep the order.
        names = list(dict.fromkeys(names + ['default']))

        # Safety rule: an admin can't remove their own admin role,
        # otherwise the last admin could lock everybody out.
        if target.id == caller.id and 'admin' not in names:
            abort(400, message='You cannot remove your own admin role.')

        roles = []
        for name in names:
            role = Role.query.filter_by(name=name).first()
            if role is None:
                abort(400, message='Unknown role: %s' % name)
            roles.append(role)

        target.roles = roles
        db.session.add(target)
        db.session.commit()

        return serialize(target)