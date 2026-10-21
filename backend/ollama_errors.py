from urllib.parse import urlsplit


def http_error_message(status_code, model):
    if status_code == 404:
        return (
            f"Ollama model '{model}' was not found. "
            f"Run `ollama pull {model}` and try again."
        )
    return f"Ollama returned HTTP {status_code} while generating the report."


def connection_error_message(base_url):
    try:
        parsed = urlsplit(base_url)
    except ValueError:
        parsed = None
    hostname = parsed.hostname if parsed else None
    if hostname:
        hostname = f"[{hostname}]" if ":" in hostname else hostname
        try:
            port = f":{parsed.port}" if parsed.port else ""
        except ValueError:
            port = ""
        location = f"{parsed.scheme}://{hostname}{port}" if parsed.scheme in {"http", "https"} else hostname
        destination = f" at {location}"
    else:
        destination = ""
    return (
        f"Could not connect to Ollama{destination}. "
        "Check that Ollama is running and the base URL is correct."
    )
