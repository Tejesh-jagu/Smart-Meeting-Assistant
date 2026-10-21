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
            connection.execute("SELECT pg_advisory_xact_lock(739104221)")
            first_user = connection.execute(
                "SELECT NOT EXISTS (SELECT 1 FROM app_users) AS is_first_user"
            ).fetchone()["is_first_user"]
            user = connection.execute(
                """
                INSERT INTO app_users (name, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id, name, email
                """,
                (payload.name, payload.email, runtime.password_hasher.hash(payload.password)),
            ).fetchone()
            if first_user:
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
                    (user["id"],),
                )
                connection.execute(
                    """
                    UPDATE app_users
                    SET next_session_number = GREATEST(
                        next_session_number,
                        COALESCE((
                            SELECT MAX(session_number) + 1
                            FROM meetings
                            WHERE user_id = %s
                        ), 1)
                    )
                    WHERE id = %s
                    """,
                    (user["id"], user["id"]),
                )
            session_token, csrf_token = runtime.create_session(connection, user["id"])
    except runtime.psycopg.errors.UniqueViolation as error:
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from error

    runtime.set_auth_cookies(response, session_token, csrf_token)
    return {
        "message": "Account created.",
        "user": {"id": user["id"], "name": user["name"], "email": user["email"]},
        "csrf_token": csrf_token,
    }


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
            if user:
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


