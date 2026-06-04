"""
download_models.py — Model artifact bootstrapper for the FinSight ML microservice.

Downloads ML model artifacts from remote storage (Hugging Face) during Render
startup when the files do not already exist locally.  Large files (~605 MB) are
streamed in chunks so memory usage stays constant regardless of file size.

Typical usage (Render Start Command):
    python -m ml.download_models && uvicorn ml.app:app --host 0.0.0.0 --port $PORT

Required environment variables:
    MODEL_URL          URL of the serialised RandomForest model (.pkl)
    PREPROCESSOR_URL   URL of the fitted preprocessor / pipeline (.pkl)
    MODEL_PATH         Local path where the model should be saved
    PREPROCESSOR_PATH  Local path where the preprocessor should be saved

Exit codes:
    0  All artifacts are present and ready.
    1  Configuration error — a required environment variable is missing.
    2  Download or network error (HTTP error, connection failure, empty file).
    3  Unexpected / unhandled error.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# 8 MB per chunk: low memory footprint, efficient for Render's shared memory.
_CHUNK_SIZE: int = 8 * 1024 * 1024

# (connect timeout, read timeout).  The read timeout is None so the connection
# is never forcibly closed mid-transfer — critical for a 605 MB download on a
# variable-speed link.
_TIMEOUT: tuple[int, Optional[int]] = (30, None)

# Log progress every N percent when Content-Length is known.
_LOG_INTERVAL_PCT: int = 10

# Log progress every N bytes when Content-Length is *not* known.
_LOG_INTERVAL_BYTES: int = 100 * 1024 * 1024  # 100 MB


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def _get_required_env(key: str) -> str:
    """Return the value of a required environment variable.

    Args:
        key: Name of the environment variable.

    Returns:
        The non-empty string value of the variable.

    Raises:
        EnvironmentError: If the variable is absent or set to an empty string.
    """
    value: str = os.environ.get(key, "").strip()
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set or is empty.  "
            "Add it to your .env file or Render's Environment settings."
        )
    return value


def _load_config() -> dict[str, str]:
    """Load and return all required configuration values.

    Returns:
        A mapping of config keys to their resolved string values::

            {
                "model_url":         "https://...",
                "preprocessor_url":  "https://...",
                "model_path":        "ml/saved_models/random_forest.pkl",
                "preprocessor_path": "ml/saved_models/preprocessor.pkl",
            }

    Raises:
        EnvironmentError: If any required variable is missing.
    """
    return {
        "model_url": _get_required_env("MODEL_URL"),
        "preprocessor_url": _get_required_env("PREPROCESSOR_URL"),
        "model_path": _get_required_env("MODEL_PATH"),
        "preprocessor_path": _get_required_env("PREPROCESSOR_PATH"),
    }


# ---------------------------------------------------------------------------
# Download logic
# ---------------------------------------------------------------------------


def download_file(url: str, destination: str, label: str = "file") -> None:
    """Stream a remote file to a local path, skipping if already present.

    The file is written to a ``.tmp`` sibling first and renamed on success so
    the destination path is never left in a partially-written state across
    process restarts.

    Args:
        url:         HTTPS URL to download from.
        destination: Absolute or relative local filesystem path for the file.
        label:       Human-readable name used in log messages (e.g. ``"Random Forest model"``).

    Raises:
        requests.HTTPError:       Server returned a non-2xx status code.
        requests.ConnectionError: Could not reach the host.
        requests.Timeout:         Connection timed out (30 s limit).
        requests.RequestException: Any other network-level failure.
        RuntimeError:             Downloaded file is 0 bytes.
    """
    dest: Path = Path(destination)

    if dest.exists():
        size_mb: float = dest.stat().st_size / (1024 * 1024)
        logger.info(
            "[SKIP] '%s' already exists at '%s' (%.2f MB) — skipping download.",
            label,
            destination,
            size_mb,
        )
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp: Path = dest.with_suffix(dest.suffix + ".tmp")

    logger.info("[START] Downloading '%s'", label)
    logger.info("        URL:         %s", url)
    logger.info("        Destination: %s", destination)

    try:
        with requests.get(url, stream=True, timeout=_TIMEOUT) as response:
            response.raise_for_status()

            raw_length: Optional[str] = response.headers.get("Content-Length")
            total_bytes: Optional[int] = int(raw_length) if raw_length else None

            if total_bytes is not None:
                logger.info(
                    "        Size:        %.2f MB (reported by server)",
                    total_bytes / (1024 * 1024),
                )
            else:
                logger.info("        Size:        unknown (server did not send Content-Length)")

            downloaded: int = 0
            last_logged_pct: int = -1
            last_logged_bytes: int = 0

            with tmp.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    downloaded += len(chunk)

                    if total_bytes:
                        pct: int = int(downloaded / total_bytes * 100)
                        bucket: int = pct // _LOG_INTERVAL_PCT
                        if bucket > last_logged_pct // _LOG_INTERVAL_PCT:
                            logger.info(
                                "[PROGRESS] '%s': %3d%%  (%.1f / %.1f MB)",
                                label,
                                pct,
                                downloaded / (1024 * 1024),
                                total_bytes / (1024 * 1024),
                            )
                            last_logged_pct = pct
                    else:
                        if downloaded - last_logged_bytes >= _LOG_INTERVAL_BYTES:
                            logger.info(
                                "[PROGRESS] '%s': %.1f MB downloaded so far...",
                                label,
                                downloaded / (1024 * 1024),
                            )
                            last_logged_bytes = downloaded

    except requests.RequestException:
        if tmp.exists():
            tmp.unlink()
            logger.warning("[CLEANUP] Removed incomplete temp file: %s", tmp)
        raise

    # Validate the temp file before promoting it.
    final_size: int = tmp.stat().st_size
    if final_size == 0:
        tmp.unlink()
        raise RuntimeError(
            f"Downloaded file for '{label}' is 0 bytes.  "
            "The URL may be inaccessible or the resource may be empty."
        )

    tmp.rename(dest)
    logger.info(
        "[DONE]  '%s' saved to '%s' (%.2f MB).",
        label,
        destination,
        final_size / (1024 * 1024),
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def ensure_models(config: dict[str, str]) -> None:
    """Download all required model artifacts that are not yet present locally.

    Artifacts are downloaded sequentially.  The preprocessor is small (~38 KB)
    and downloads almost instantly; the Random Forest model (~605 MB) is
    downloaded first so any failure surfaces before the wait for the preprocessor.

    Args:
        config: Configuration dictionary returned by :func:`_load_config`.

    Raises:
        Propagates any exception raised by :func:`download_file`.
    """
    artifacts: list[tuple[str, str, str]] = [
        (config["model_url"],        config["model_path"],        "Random Forest model (~605 MB)"),
        (config["preprocessor_url"], config["preprocessor_path"], "Preprocessor (~38 KB)"),
    ]

    for url, path, label in artifacts:
        download_file(url=url, destination=path, label=label)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Bootstrap model artifacts and exit with an appropriate status code.

    This function is the sole entry point when the module is executed directly
    (``python -m ml.download_models``).  Non-zero exit codes cause Render's
    start command to abort before uvicorn is launched, preventing the service
    from starting with missing models.

    Exit codes:
        0 — all artifacts present and ready.
        1 — configuration error (missing environment variable).
        2 — download or network error.
        3 — unexpected error.
    """
    logger.info("=" * 60)
    logger.info("FinSight ML — model artifact bootstrap")
    logger.info("=" * 60)

    try:
        config: dict[str, str] = _load_config()
    except EnvironmentError as exc:
        logger.error("[CONFIG ERROR] %s", exc)
        sys.exit(1)

    try:
        ensure_models(config)
    except requests.HTTPError as exc:
        logger.error(
            "[HTTP ERROR] Server rejected the download request: %s", exc
        )
        sys.exit(2)
    except (requests.ConnectionError, requests.Timeout) as exc:
        logger.error("[NETWORK ERROR] Could not reach the download server: %s", exc)
        sys.exit(2)
    except requests.RequestException as exc:
        logger.error("[DOWNLOAD ERROR] %s", exc)
        sys.exit(2)
    except RuntimeError as exc:
        logger.error("[VALIDATION ERROR] %s", exc)
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001
        logger.error("[UNEXPECTED ERROR] %s", exc, exc_info=True)
        sys.exit(3)

    logger.info("=" * 60)
    logger.info("All model artifacts ready — starting API server.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
