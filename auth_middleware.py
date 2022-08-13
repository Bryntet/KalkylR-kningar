from functools import wraps
from flask import request
from flask import current_app


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if "Authorization" in request.headers:
            token = request.headers["Authorization"]
        if not token:
            return {
                "message": "Authentication Token is missing!",
                "data": None,
                "error": "Unauthorized"
            }, 401
        if token == current_app.config["SECRET_KEY"]:
            return f(*args, **kwargs)

        return f(*args, **kwargs)

    return decorated
