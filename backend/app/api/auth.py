from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response

from .. import runtime

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/csrf")
def get_csrf_token(response: Response):
    token = runtime.secrets.token_urlsafe(32)
    response.set_cookie(
        runtime.CSRF_COOKIE_NAME,
        token,
        max_age=60 * 60,
        httponly=True,
        secure=runtime.SESSION_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"csrf_token": token}


@router.post("/register", status_code=201)
def register(request: Request, response: Response, payload: runtime.SignupRequest, x_csrf_token: str = Header()):
    runtime.require_csrf(request, x_csrf_token)
    if not runtime.verification_configured():
        raise HTTPException(status_code=503, detail="Email verification is not configured on the server.")
    address_hash = runtime.client_address_hash(request)
    with runtime.psycopg.connect(**runtime.DB_CONFIG) as connection:
        signup_allowed = runtime.consume_rate_limit(
            connection,
            f"signup:{address_hash}",
            runtime.SIGNUPS_PER_HOUR,
            60 * 60,
        )
    if not signup_allowed:
        raise HTTPException(status_code=429, detail="Too many sign-up attempts. Try again later.")

    try:
        with runtime.psycopg.connect(**runtime.DB_CONFIG, row_factory=runtime.dict_row) as connection:
            user = connection.execute(
                """
                INSERT INTO app_users (name, email, password_hash)
                VALUES (%s, %s, NULL)
                RETURNING id, name, email
                """,
                (payload.name, payload.email),
            ).fetchone()
            code = runtime.new_verification_code()
            connection.execute(
                """
                INSERT INTO email_verification_codes (user_id, code_hash, expires_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP + INTERVAL '10 minutes')
                """,
                (user["id"], runtime.hash_verification_code(code)),
            )
    except runtime.psycopg.errors.UniqueViolation as error:
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from error

    try:
        runtime.send_verification_email(user["email"], code)
    except (runtime.smtplib.SMTPException, OSError) as error:
        raise HTTPException(status_code=502, detail="Could not send the verification email. Check the mail settings and try again.") from error

    response.headers["Cache-Control"] = "no-store"
    return {
        "message": "Enter the verification code sent to your email.",
        "email": user["email"],
        "verification_required": True,
    }


@router.post("/verify-email")
def verify_email(request: Request, response: Response, payload: runtime.VerificationRequest, x_csrf_token: str = Header()):
    runtime.require_csrf(request, x_csrf_token)
    if len(runtime.OTP_HASH_SECRET) < 32:
        raise HTTPException(status_code=503, detail="Email verification is not configured on the server.")
    address_hash = runtime.client_address_hash(request)
    email_hash = runtime.hash_email_identifier(payload.email)
    session_token = csrf_token = None
    invalid_code = False
    blocked = False

    with runtime.psycopg.connect(**runtime.DB_CONFIG, row_factory=runtime.dict_row) as connection:
        blocked = not runtime.consume_rate_limit(
            connection, f"otp-verify:{address_hash}:{email_hash}", 10, 60 * 60
        )
        if not blocked:
            connection.execute("SELECT pg_advisory_xact_lock(739104221)")
            row = connection.execute(
                """
                SELECT users.id, users.name, users.email, codes.code_hash,
                       codes.expires_at > CURRENT_TIMESTAMP AS is_valid,
                       codes.failed_attempts
                FROM app_users AS users
                JOIN email_verification_codes AS codes ON codes.user_id = users.id
                WHERE users.email = %s AND users.email_verified_at IS NULL
                FOR UPDATE OF codes
                """,
                (payload.email,),
            ).fetchone()
            if row is None or not row["is_valid"] or row["failed_attempts"] >= 5:
                invalid_code = True
            elif not runtime.hmac.compare_digest(
                row["code_hash"], runtime.hash_verification_code(payload.code)
            ):
                connection.execute(
                    "UPDATE email_verification_codes SET failed_attempts = failed_attempts + 1 WHERE user_id = %s",
                    (row["id"],),
                )
                invalid_code = True
            else:
                connection.execute(
                    "UPDATE app_users SET password_hash = %s, email_verified_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (runtime.password_hasher.hash(payload.password), row["id"]),
                )
                first_verified_user = connection.execute(
                    "SELECT NOT EXISTS (SELECT 1 FROM app_users WHERE email_verified_at IS NOT NULL AND id <> %s) AS is_first",
                    (row["id"],),
                ).fetchone()["is_first"]
                if first_verified_user:
                    connection.execute(
                        """
                        WITH claimable AS (
                            SELECT id,
                                   ROW_NUMBER() OVER (ORDER BY created_at ASC, id ASC) AS session_number
                            FROM meetings
                            WHERE user_id IS NULL
                        )
                        UPDATE meetings AS meeting
                        SET user_id = %s, session_number = claimable.session_number
                        FROM claimable
                        WHERE meeting.id = claimable.id AND meeting.user_id IS NULL
                        """,
                        (row["id"],),
                    )
                    connection.execute(
                        """
                        UPDATE app_users
                        SET next_session_number = GREATEST(
                            next_session_number,
                            COALESCE((SELECT MAX(session_number) + 1 FROM meetings WHERE user_id = %s), 1)
                        )
                        WHERE id = %s
                        """,
                        (row["id"], row["id"]),
                    )
                connection.execute("DELETE FROM email_verification_codes WHERE user_id = %s", (row["id"],))
                session_token, csrf_token = runtime.create_session(connection, row["id"])

    if blocked:
        raise HTTPException(status_code=429, detail="Too many verification attempts. Try again later.")
    if invalid_code:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")

    runtime.set_auth_cookies(response, session_token, csrf_token)
    return {
        "message": "Email verified.",
        "user": {"id": row["id"], "name": row["name"], "email": row["email"]},
        "csrf_token": csrf_token,
    }


@router.post("/resend-verification")
def resend_verification(request: Request, response: Response, payload: runtime.ResendVerificationRequest, x_csrf_token: str = Header()):
    runtime.require_csrf(request, x_csrf_token)
    if not runtime.verification_configured():
        raise HTTPException(status_code=503, detail="Email verification is not configured on the server.")
    address_hash = runtime.client_address_hash(request)
    email_hash = runtime.hash_email_identifier(payload.email)
    code = None
    with runtime.psycopg.connect(**runtime.DB_CONFIG, row_factory=runtime.dict_row) as connection:
        allowed = runtime.consume_rate_limit(
            connection, f"otp-resend:{address_hash}:{email_hash}", 5, 60 * 60, 60
        )
        if not allowed:
            raise HTTPException(status_code=429, detail="Please wait before requesting another code.")
        connection.execute("SELECT pg_advisory_xact_lock(739104221)")
        user = connection.execute(
            "SELECT id, email FROM app_users WHERE email = %s AND email_verified_at IS NULL",
            (payload.email,),
        ).fetchone()
        if user:
            code = runtime.new_verification_code()
            connection.execute(
                """
                INSERT INTO email_verification_codes (user_id, code_hash, expires_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP + INTERVAL '10 minutes')
                ON CONFLICT (user_id) DO UPDATE SET
                    code_hash = EXCLUDED.code_hash,
                    expires_at = EXCLUDED.expires_at,
                    failed_attempts = 0,
                    sent_at = CURRENT_TIMESTAMP
                """,
                (user["id"], runtime.hash_verification_code(code)),
            )

    if code:
        try:
            runtime.send_verification_email(user["email"], code)
        except (runtime.smtplib.SMTPException, OSError) as error:
            raise HTTPException(status_code=502, detail="Could not send the verification email. Try again later.") from error
    response.headers["Cache-Control"] = "no-store"
    return {"message": "If the address has an unverified account, a code has been sent."}


@router.post("/request-password-reset")
def request_password_reset(
    request: Request,
    response: Response,
    payload: runtime.ResendVerificationRequest,
    x_csrf_token: str = Header(),
):
    runtime.require_csrf(request, x_csrf_token)
    if not runtime.verification_configured():
        raise HTTPException(status_code=503, detail="Password reset email is not configured on the server.")

    address_hash = runtime.client_address_hash(request)
    email_hash = runtime.hash_email_identifier(payload.email)
    code = None
    with runtime.psycopg.connect(**runtime.DB_CONFIG, row_factory=runtime.dict_row) as connection:
        allowed = runtime.consume_rate_limit(
            connection, f"password-reset-request:{address_hash}:{email_hash}", 5, 60 * 60, 60
        )
        if not allowed:
            raise HTTPException(status_code=429, detail="Please wait before requesting another password reset code.")

        connection.execute("SELECT pg_advisory_xact_lock(739104221)")
        user = connection.execute(
            "SELECT id, email FROM app_users WHERE email = %s AND email_verified_at IS NOT NULL",
            (payload.email,),
        ).fetchone()
        if user:
            code = runtime.new_verification_code()
            connection.execute(
                """
                INSERT INTO password_reset_codes (user_id, code_hash, expires_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP + INTERVAL '10 minutes')
                ON CONFLICT (user_id) DO UPDATE SET
                    code_hash = EXCLUDED.code_hash,
                    expires_at = EXCLUDED.expires_at,
                    failed_attempts = 0,
                    sent_at = CURRENT_TIMESTAMP
                """,
                (user["id"], runtime.hash_verification_code(code)),
            )

    if code:
        try:
            runtime.send_password_reset_email(user["email"], code)
        except (runtime.smtplib.SMTPException, OSError) as error:
            raise HTTPException(status_code=502, detail="Could not send the password reset email. Check the mail settings and try again.") from error

    response.headers["Cache-Control"] = "no-store"
    return {"message": "If a verified account exists for that email, a password reset code has been sent."}


@router.post("/reset-password")
def reset_password(
    request: Request,
    response: Response,
    payload: runtime.PasswordResetRequest,
    x_csrf_token: str = Header(),
):
    runtime.require_csrf(request, x_csrf_token)
    if len(runtime.OTP_HASH_SECRET) < 32:
        raise HTTPException(status_code=503, detail="Password reset is not configured on the server.")

    address_hash = runtime.client_address_hash(request)
    email_hash = runtime.hash_email_identifier(payload.email)
    invalid_code = False
    with runtime.psycopg.connect(**runtime.DB_CONFIG, row_factory=runtime.dict_row) as connection:
        allowed = runtime.consume_rate_limit(
            connection, f"password-reset-confirm:{address_hash}:{email_hash}", 10, 60 * 60
        )
        if not allowed:
            raise HTTPException(status_code=429, detail="Too many password reset attempts. Try again later.")

        connection.execute("SELECT pg_advisory_xact_lock(739104221)")
        row = connection.execute(
            """
            SELECT users.id, codes.code_hash,
                   codes.expires_at > CURRENT_TIMESTAMP AS is_valid,
                   codes.failed_attempts
            FROM app_users AS users
            JOIN password_reset_codes AS codes ON codes.user_id = users.id
            WHERE users.email = %s AND users.email_verified_at IS NOT NULL
            FOR UPDATE OF codes
            """,
            (payload.email,),
        ).fetchone()

        if row is None or not row["is_valid"] or row["failed_attempts"] >= 5:
            invalid_code = True
        elif not runtime.hmac.compare_digest(
            row["code_hash"], runtime.hash_verification_code(payload.code)
        ):
            connection.execute(
                "UPDATE password_reset_codes SET failed_attempts = failed_attempts + 1 WHERE user_id = %s",
                (row["id"],),
            )
            invalid_code = True
        else:
            connection.execute(
                "UPDATE app_users SET password_hash = %s WHERE id = %s",
                (runtime.password_hasher.hash(payload.password), row["id"]),
            )
            connection.execute("DELETE FROM password_reset_codes WHERE user_id = %s", (row["id"],))
            connection.execute("DELETE FROM app_sessions WHERE user_id = %s", (row["id"],))

    if invalid_code:
        raise HTTPException(status_code=400, detail="Invalid or expired password reset code.")

    response.headers["Cache-Control"] = "no-store"
    return {"message": "Password reset. Sign in with your new password."}


@router.post("/login")
def login(request: Request, response: Response, payload: runtime.LoginRequest, x_csrf_token: str = Header()):
    runtime.require_csrf(request, x_csrf_token)
    address_hash = runtime.client_address_hash(request)
    blocked = False
    user = None
    session_token = None
    csrf_token = None
    invalid_credentials = False

    with runtime.psycopg.connect(**runtime.DB_CONFIG, row_factory=runtime.dict_row) as connection:
        blocked = runtime.register_login_attempt(connection, address_hash)
        if not blocked:
            user = connection.execute(
                "SELECT id, name, email, password_hash FROM app_users WHERE email = %s",
                (payload.email,),
            ).fetchone()

            valid_password = False
            if user and user["password_hash"]:
                try:
                    valid_password = runtime.password_hasher.verify(user["password_hash"], payload.password)
                except runtime.VerificationError:
                    valid_password = False

            if not valid_password:
                invalid_credentials = True
                user = None
            else:
                if runtime.password_hasher.check_needs_rehash(user["password_hash"]):
                    connection.execute(
                        "UPDATE app_users SET password_hash = %s WHERE id = %s",
                        (runtime.password_hasher.hash(payload.password), user["id"]),
                    )
                connection.execute(
                    "DELETE FROM auth_login_limits WHERE address_hash = %s",
                    (address_hash,),
                )
                session_token, csrf_token = runtime.create_session(connection, user["id"])

    if blocked:
        raise HTTPException(status_code=429, detail="Too many sign-in attempts. Try again in 15 minutes.")
    if invalid_credentials:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    runtime.set_auth_cookies(response, session_token, csrf_token)
    return {
        "message": "Signed in.",
        "user": {"id": user["id"], "name": user["name"], "email": user["email"]},
        "csrf_token": csrf_token,
    }


@router.get("/me")
def current_user(response: Response, user: dict = Depends(runtime.get_current_user)):
    response.set_cookie(
        runtime.CSRF_COOKIE_NAME,
        user["csrf_token"],
        max_age=runtime.SESSION_MAX_AGE,
        httponly=True,
        secure=runtime.SESSION_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "user": {"id": user["id"], "name": user["name"], "email": user["email"]},
        "csrf_token": user["csrf_token"],
    }


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    x_csrf_token: str = Header(),
    user: dict = Depends(runtime.get_current_user),
):
    runtime.require_csrf(request, x_csrf_token)
    session_token = request.cookies[runtime.SESSION_COOKIE_NAME]
    token_hash = runtime.hashlib.sha256(session_token.encode("utf-8")).hexdigest()
    with runtime.psycopg.connect(**runtime.DB_CONFIG) as connection:
        connection.execute(
            "DELETE FROM app_sessions WHERE token_hash = %s AND user_id = %s",
            (token_hash, user["id"]),
        )
    response.delete_cookie(runtime.SESSION_COOKIE_NAME, path="/", secure=runtime.SESSION_COOKIE_SECURE, httponly=True, samesite="lax")
    response.delete_cookie(runtime.CSRF_COOKIE_NAME, path="/", secure=runtime.SESSION_COOKIE_SECURE, httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return {"message": "Signed out."}

