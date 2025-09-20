# Django Full Auth Template (JWT, Email Verify, Password Reset, TOTP 2FA, Magic Links, Social via allauth)

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations accounts organizations --settings=config.settings.dev
python manage.py migrate --settings=config.settings.dev
python manage.py createsuperuser --email admin@example.com --settings=config.settings.dev 
python manage.py runserver --settings=config.settings.dev

Then go to:
    http://127.0.0.1:8000/admin/ → Django admin
    http://127.0.0.1:8000/api/auth/ → your REST endpoints (login, register, etc.)

Test flows:
    Register a new user at /api/auth/register/.
    Check email verification (console email backend for now).
    Try login with JWT.
    Enable TOTP at /api/auth/mfa/totp/setup-begin/.
    Test lockouts via Axes (multiple failed logins).

```

## Env (.env)
```
DEBUG=True
SECRET_KEY=dev-secret-change-me
ALLOWED_HOSTS=127.0.0.1,localhost
JWT_SIGNING_KEY=dev-secret-change-me
```

## Endpoints
- `POST /api/auth/register/` {email, password}
- `POST /api/auth/login/` {email, password, org_id?} → {access, refresh, user} or {mfa_required}
- `POST /api/auth/logout/`
- `GET  /api/auth/me/`
- `POST /api/auth/email/verify/` {uid, token}
- `POST /api/auth/password/forgot/` {email}
- `POST /api/auth/password/reset/` {uid, token, new_password}
- `POST /api/auth/magic/request/` {email}
- `POST /api/auth/magic/consume/` {uid, token}
- `POST /api/auth/mfa/totp/setup-begin/`
- `POST /api/auth/mfa/totp/confirm/` {code} -> returns backup codes
- `POST /api/auth/mfa/verify/` {uid, type: TOTP|BACKUP, code}

## Social (via dj-rest-auth + allauth)
- `GET  /api/dj-auth/login/` etc.
- Configure provider keys in admin; enable Google provider for OIDC.

## Policies per org/user
- Create a `Policy` and attach it to an `Organization`. Membership determines effective policy.
- Controls: require_email_verification, allow_magic_link, allow_totp, allow_webauthn, etc.

## WebAuthn (Passkeys) Scaffold
- Add endpoints for register/authenticate begin/complete using the `webauthn` lib.
- Store credentials in `WebAuthnCredential`.
- Enforce per policy (allow_webauthn).

## Notes
- Emails are printed to console in dev. Swap to Anymail in prod.
- Tighten CORS, cookies, HSTS in `config/settings/security.py` for production.
- Rate limits & brute-force lockout via DRF throttles and django-axes.


## Final Setup Recap
- Start Django backend: python manage.py runserver
- Start React frontend: npm run dev
- Visit http://localhost:5173/ → try register/login flows
- Admin at http://localhost:8000/admin/



## GIT 
- Step 5: Initialize Git in Your Project
    🔹 git init
    🔹 git add .
    🔹 git commit -m "Initial commit"

- Step 6: Link Local Project to GitHub
    🔹 git remote add origin https://github.com/username/my-project.git
    🔹 git branch -M main
    🔹 git push -u origin main

- Step 7: Using Git & VSCode Together
    🔹 git add .
    🔹 git commit -m "Updated feature"
    🔹 git push

- Step 8: To pull changes from GitHub:
    🔹 git pull
    🔹 If There’s a Conflict
        👉 git add <file>
        👉 git rebase --continue




