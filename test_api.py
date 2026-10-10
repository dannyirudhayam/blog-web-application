import json
import unittest

from jmilkfansblog import create_app
from jmilkfansblog.common import config
from jmilkfansblog.db.sqlalchemy.models import db, Role, User


class ApiTestCase(unittest.TestCase):
    """Tests for the token, refresh and roles APIs."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(config.__name__ + '.Config')
        # Use a throwaway in-memory database, never the real MySQL one.
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()

        for name in ('default', 'poster', 'admin'):
            role = Role()
            role.name = name
            db.session.add(role)
        db.session.commit()

        self.make_user('Danny', 'adminpass1', ['admin'])
        self.make_user('ki', 'kipass1234', ['poster'])
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # ---- helpers -------------------------------------------------------

    def make_user(self, username, password, extra_roles):
        user = User(username, password)          # gets the `default` role
        for name in extra_roles:
            user.roles.append(Role.query.filter_by(name=name).one())
        db.session.add(user)
        db.session.commit()
        return user

    def call(self, method, url, token=None, body=None):
        headers = {}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        data = json.dumps(body) if body is not None else None
        resp = getattr(self.client, method)(
            url, data=data, headers=headers, content_type='application/json')
        try:
            payload = json.loads(resp.data.decode('utf-8'))
        except ValueError:
            payload = None
        return resp.status_code, payload

    def login(self, username, password):
        return self.call('post', '/api/auth',
                         body={'username': username, 'password': password})

    def token_for(self, username, password):
        status, payload = self.login(username, password)
        self.assertEqual(status, 200)
        return payload['token']

    # ---- /api/auth -------------------------------------------------------

    def test_login_returns_token(self):
        status, payload = self.login('Danny', 'adminpass1')
        self.assertEqual(status, 200)
        self.assertIn('token', payload)
        self.assertEqual(payload['expires_in'],
                         self.app.config['TOKEN_EXPIRES_IN'])

    def test_login_wrong_password_is_401(self):
        status, _ = self.login('Danny', 'wrong')
        self.assertEqual(status, 401)

    def test_login_unknown_user_is_401(self):
        status, _ = self.login('nobody', 'whatever1')
        self.assertEqual(status, 401)

    # ---- /api/auth/refresh ---------------------------------------------------

    def test_refresh_without_token_is_401(self):
        status, _ = self.call('post', '/api/auth/refresh')
        self.assertEqual(status, 401)

    def test_refresh_with_garbage_token_is_401(self):
        status, _ = self.call('post', '/api/auth/refresh', token='garbage')
        self.assertEqual(status, 401)

    def test_refresh_returns_a_new_token(self):
        token = self.token_for('Danny', 'adminpass1')
        status, payload = self.call('post', '/api/auth/refresh', token=token)
        self.assertEqual(status, 200)
        self.assertIn('token', payload)

    # ---- /api/users/<name>/roles ---------------------------------------

    def test_roles_without_token_is_401(self):
        status, _ = self.call('get', '/api/users/ki/roles')
        self.assertEqual(status, 401)

    def test_roles_for_non_admin_is_403(self):
        token = self.token_for('ki', 'kipass1234')
        status, _ = self.call('get', '/api/users/ki/roles', token=token)
        self.assertEqual(status, 403)

    def test_admin_can_read_roles(self):
        token = self.token_for('Danny', 'adminpass1')
        status, payload = self.call('get', '/api/users/ki/roles', token=token)
        self.assertEqual(status, 200)
        self.assertEqual(payload['roles'], ['default', 'poster'])

    def test_unknown_user_is_404(self):
        token = self.token_for('Danny', 'adminpass1')
        status, _ = self.call('get', '/api/users/nobody/roles', token=token)
        self.assertEqual(status, 404)

    def test_admin_can_change_roles_and_default_is_kept(self):
        token = self.token_for('Danny', 'adminpass1')
        status, payload = self.call('put', '/api/users/ki/roles',
                                    token=token, body={'roles': ['admin']})
        self.assertEqual(status, 200)
        self.assertEqual(payload['roles'], ['admin', 'default'])

    def test_unknown_role_is_400(self):
        token = self.token_for('Danny', 'adminpass1')
        status, _ = self.call('put', '/api/users/ki/roles',
                              token=token, body={'roles': ['nonsense']})
        self.assertEqual(status, 400)

    def test_admin_cannot_remove_own_admin_role(self):
        token = self.token_for('Danny', 'adminpass1')
        status, _ = self.call('put', '/api/users/Danny/roles',
                              token=token, body={'roles': ['poster']})
        self.assertEqual(status, 400)

    # ---- /api/posts ----------------------------------------------------

    def test_created_post_has_a_publish_date(self):
        token = self.token_for('ki', 'kipass1234')
        status, post_id = self.call('post', '/api/posts', token=token,
                                    body={'title': 't', 'text': 'body'})
        self.assertEqual(status, 201)
        status, post = self.call('get', '/api/posts/' + post_id)
        self.assertEqual(status, 200)
        self.assertIsNotNone(post['publish_date'])

    def test_create_post_without_token_is_401(self):
        status, _ = self.call('post', '/api/posts',
                              body={'title': 't', 'text': 'body'})
        self.assertEqual(status, 401)


if __name__ == '__main__':
    unittest.main()