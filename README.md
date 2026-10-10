# JmilkFan's Blog (Flask) - Python 3 / Windows / MySQL 8 port with extensions

This is a fork of [JmilkFan/blog-web-application](https://github.com/JmilkFan/blog-web-application),
a Flask blog with login, posts, comments, roles and a REST API.

The original project was written in 2016-17. This fork:

1. **Runs on Python 3.8, Windows and MySQL 8** (see *Compatibility fixes*).
2. **Adds new features** for the assignment (see *My changes*).

---

## Quick start (Windows)

Requirements: Python 3.8, MySQL 8, Git.

```bat
git clone <your-fork-url>
cd blog-web-application
py -3.8 -m venv blog_env
blog_env\Scripts\activate
python -m pip install "pip<24.1" "setuptools<58" wheel
pip install -r requirements.txt
pip install -e . --no-deps
```

> `pip<24.1` is needed because Celery 4.0.1 has old-style package metadata
> that newer pip versions reject.

### Database

Create the database with the **utf8mb4** character set (needed for emoji in posts):

```sql
CREATE DATABASE myblog CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Configuration

```bat
copy etc\jmilkfansblog.conf.example etc\jmilkfansblog.conf
```

Edit `etc\jmilkfansblog.conf`:

* `connection` - your MySQL user and password. If the password contains `@`,
  write it as `%40`. End the URL with `?charset=utf8mb4`.
* `recaptcha_*` - not used locally (reCAPTCHA is disabled, see *Known limitations*).
* `token_expires_in` - optional, API token lifetime in seconds (default 600).

`etc\jmilkfansblog.conf` is in `.gitignore` because it contains secrets.

### Create the tables and roles

```bat
jmilkfansblog-manager db upgrade -d jmilkfansblog/db/sqlalchemy/alembic
```

```sql
USE myblog;
INSERT INTO roles (id, name, description) VALUES
  (UUID(), 'default', 'Default user role'),
  (UUID(), 'poster',  'Can create and edit own posts'),
  (UUID(), 'admin',   'Administrator');
```

### Run

```bat
jmilkfansblog-manager server
```

The site and the REST API are served at <http://127.0.0.1:8080>
(blog home: `/blog/`, register: `/register`, login: `/login`).

The first admin has to be created in the database, because only an admin can
grant roles through the API:

```sql
INSERT INTO users_roles (user_id, role_id)
SELECT u.id, r.id FROM users u, roles r
WHERE u.username = 'YOUR_USERNAME' AND r.name IN ('poster', 'admin');
```

---

## My changes

### 1. Role-based access (web pages)

The original code had two contradictory checks on `/blog/edit/<id>` (admins only,
*and* author only), so normal authors could never edit their own posts, and the
`poster` role was never checked anywhere.

| Role | Create post | Edit own post | Edit someone else's post |
|------|:-----------:|:-------------:|:------------------------:|
| `default` | 403 | - | 403 |
| `poster`  | yes | yes | 403 |
| `admin`   | yes | yes | yes |

* `extensions.py`: new `poster_or_admin_permission` (a Flask-Principal
  `Permission` with two `RoleNeed`s; any one matching need is enough).
* `controllers/blog/__init__.py`: `new_post` requires it; `edit_post` allows the
  post's author (`UserNeed(post.user_id)`) or an admin, and returns 403 otherwise.

### 2. New API: manage user roles (admin only)

| Request | Description |
|---------|-------------|
| `GET /api/users/<username>/roles` | List the user's roles |
| `PUT /api/users/<username>/roles` | Replace the user's roles |

```bat
curl -X PUT http://127.0.0.1:8080/api/users/ki/roles ^
  -H "Authorization: Bearer <admin token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"roles\":[\"default\",\"poster\"]}"
```

| Status | Meaning |
|--------|---------|
| 200 | Success, returns `{"username": ..., "roles": [...]}` |
| 400 | `roles` is not a list, an unknown role name, or an admin tried to remove their own `admin` role |
| 401 | Missing, invalid or expired token |
| 403 | Valid token, but the user is not an admin |
| 404 | No such user |

Design notes:

* Every user always keeps the `default` role.
* An admin cannot remove their own `admin` role (prevents locking everyone out).
* The role check uses the user object from the token, not Flask-Principal's
  `admin_permission.can()`, because that reads the browser session and an API
  request has no session.

Code: `controllers/flask_restful/users.py`.

### 3. Token handling

* **`Authorization: Bearer <token>` header** is now accepted. The old `token`
  field in the JSON body still works. Shared helper:
  `controllers/flask_restful/token_auth.py` (`authenticated_user()`).
* **Refresh endpoint:** `POST /api/auth/refresh` with a still-valid token returns
  a new token with a fresh expiry.
* **Configurable lifetime:** `token_expires_in` in the config file
  (default 600 seconds). Login and refresh responses include `expires_in`.
* **Bug fixes:** the token was `bytes` on Python 3 and could not be sent as JSON;
  an unknown username crashed with a 500 instead of returning 401.

```bat
curl -X POST http://127.0.0.1:8080/api/auth ^
  -H "Content-Type: application/json" ^
  -d "{\"username\":\"Danny\",\"password\":\"...\"}"
```

Response: `{"token": "...", "expires_in": 600}`

### 4. Other fixes

* Posts created through the API had no `publish_date` (the code set a
  non-existent `date` attribute), which broke ordering.
* `HTMLStripper` did not call its parent constructor, which crashed
  `GET /api/posts` on Python 3.

---

## Tests

```bat
python -m unittest test_api -v
```

15 tests for login, refresh, the roles API, status codes and the `publish_date`
fix. They run against an in-memory SQLite database, so MySQL is not touched.

---

## Compatibility fixes (Python 2 era code on Python 3.8 / Windows / MySQL 8)

| Problem | Fix |
|---------|-----|
| Old packages needed a C compiler (cffi, bcrypt, netifaces, ...) | Newer versions that ship Windows wheels |
| Python 2-only packages (`futures`, `flower`, `tornado`, `python-openid`) | Removed or replaced by `python3-openid` |
| `time.clock` removed in 3.8 | SQLAlchemy 1.3.24, Flask-SQLAlchemy 2.5.1, and a `sitecustomize.py` shim in the venv for old libraries |
| `async` is a reserved word (Celery 4.0.1 / kombu) | Celery 4.4.7 |
| `ForkingMixIn` missing on Windows (Werkzeug 0.11) | Werkzeug 0.16.1 |
| `sqlparse` generator error in the debug toolbar | sqlparse 0.4.4 |
| Python 2 syntax: `reload(sys)`, `except X, e`, `HTMLParser`, `unicode()` | Ported to Python 3 |
| Flask-OAuth is Python 2 only | Facebook/Twitter login disabled with stand-in objects in `extensions.py` |
| PyMySQL 0.7.9 crashes on the MySQL 8 handshake (`KeyError: 255`) | PyMySQL 0.9.3 + `cryptography` |
| `%` in the DB URL breaks Alembic's config parser | Escaped as `%%` in `alembic/env.py` |
| MySQL `utf8` cannot store emoji | `utf8mb4` for the database, tables and connection string |
| `order_by('total DESC')` rejected by SQLAlchemy 1.3 | Wrapped in `text()` |

---

## Known limitations and future work

* **Tokens cannot be revoked.** They are stateless, so a refreshed token does not
  invalidate the old one; it simply expires. Real revocation needs a stored
  blacklist (e.g. in Redis).
* **Local development shortcuts:** reCAPTCHA is turned off on the register form;
  Facebook, Twitter and OpenID login are not functional; Celery/RabbitMQ is not
  required (reminder and digest emails will not be sent).
* **Security issues in the original code (not fixed here):**
  * A Facebook app key and secret are hardcoded in `extensions.py`.
  * Users created through OpenID or Facebook get the fixed password `jmilkfan`.
  * `GET /v1/users` on the separate Pecan API returns password hashes.
  * The Pecan API (`jmilkfansblog-api`, `controllers/v1/`) still contains Python 2
    code (`print user`) and was not ported or tested.
* The `downgrade()` of the `reminders` migration has a typo (`reminbers`).
