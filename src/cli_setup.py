"""
Simplified Telegram MCP server setup using unified ServerConfig.
"""

import asyncio
import getpass
import os
import sys
import tempfile
import traceback
import uuid
from pathlib import Path

import qrcode
from pydantic import Field
from pydantic_settings import CliImplicitFlag, SettingsConfigDict
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    PasswordHashInvalidError,
    PhoneNumberBannedError,
    PhoneNumberInvalidError,
    PhoneNumberUnoccupiedError,
    SessionPasswordNeededError,
)
from telethon.tl.functions.account import GetPasswordRequest

from src.client.connection import generate_bearer_token
from src.utils.logging_utils import mask_phone_number

from .config.server_config import ServerConfig, ServerMode
from .telemetry import flush_auth_events, send_auth_event
from .utils.mcp_config import generate_mcp_config_json
from .utils.proxy import build_mtproto_client_args


def _categorize_cli_error(exc: BaseException) -> str:
    """Map a Telethon/OS exception to an ADR 0008 error category string."""
    if isinstance(exc, PasswordHashInvalidError):
        return "2fa_wrong_password"
    if isinstance(exc, FloodWaitError):
        return "flood_wait"
    if isinstance(exc, PhoneNumberBannedError):
        return "phone_banned"
    if isinstance(exc, PhoneNumberInvalidError):
        return "phone_invalid"
    if isinstance(exc, PhoneNumberUnoccupiedError):
        return "phone_unoccupied"
    if isinstance(exc, ConnectionError):
        return "connect_failed"
    if isinstance(exc, (TimeoutError, OSError)):
        return "timeout"
    return "unknown"


def _is_interactive_terminal() -> bool:
    """Check if both stdin and stdout are interactive terminals."""
    return sys.stdin.isatty() and sys.stdout.isatty()


class QrScanFailedError(Exception):
    """QR scan failed (timeout exhausted or recreate error)."""


class QrScanNeeds2FAError(Exception):
    """QR scan succeeded but account requires two-factor authentication."""


class SetupConfig(ServerConfig):
    """
    Setup configuration extending ServerConfig with setup-specific options.

    Inherits all server configuration (API credentials, session settings, etc.)
    and adds setup-specific options like overwrite flag.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Native CLI parsing configuration
        cli_parse_args=True,
        cli_kebab_case=True,
        cli_exit_on_error=True,
        cli_enforce_required=False,
    )

    # Setup-specific options
    overwrite: CliImplicitFlag[bool] = Field(
        default=False,
        description="Automatically overwrite existing session without prompting",
    )

    bot_api_token: str = Field(
        default="",
        description="Bot token from BotFather (for bot account setup)",
    )

    def validate_required_fields(self) -> None:
        """Validate that required fields are provided."""
        if not self.api_id:
            raise ValueError(
                "API ID is required. Provide via --api-id argument or API_ID environment variable."
            )
        if not self.api_hash:
            raise ValueError(
                "API Hash is required. Provide via --api-hash argument or API_HASH environment variable."
            )

        # Auth method is inferred: QR (default), phone, or bot token.
        # No phone or bot token required — QR login is the default.

        # Validate session name doesn't contain slashes (would break URL-based auth and file paths)
        if (
            self.server_mode != ServerMode.HTTP_AUTH
            and self.session_name
            and "/" in self.session_name
        ):
            raise ValueError(
                "Session name cannot contain '/' character. "
                "This would break URL-based authentication and file path handling."
            )


async def _print_2fa_password_hint(client: TelegramClient) -> None:
    """Print Telegram's optional 2FA password hint before prompting for password."""
    pwd = await client(GetPasswordRequest())
    if hint := getattr(pwd, "hint", None):
        print(f"2FA password hint: {hint}")
    else:
        print("2FA password hint: (not set in Telegram)")


def _render_qr_terminal(url: str) -> bool:
    """Render QR code in terminal. Returns True on success, False on failure."""
    try:
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.print_ascii(invert=True)
        return True
    except Exception:
        return False


def _cleanup_temp_session(temp_path: Path) -> None:
    """Remove temp session file and sidecar files."""
    for ext in ("", "-journal", "-wal"):
        p = Path(f"{temp_path}.session{ext}")
        p.unlink(missing_ok=True)


def _finalize_temp_session_files(temp_filename: str | None, session_path: Path) -> None:
    """Move temp session file and sidecars to final path. Call after client.disconnect()."""
    if not temp_filename:
        return
    temp_base = Path(temp_filename).with_suffix("")
    for ext in ("", "-journal", "-wal"):
        src = Path(f"{temp_base}.session{ext}")
        dst = Path(f"{session_path}.session{ext}")
        if src.exists():
            os.rename(str(src), str(dst))


async def _wait_for_qr_scan(
    qr_login: object,
    max_retries: int = 5,
    *,
    flow_id: str = "",
    method: str = "qr",
    branch: str = "qr_scan",
) -> None:
    """Wait for QR scan with retry on timeout. Raises QrScanFailedError or QrScanNeeds2FAError."""
    for attempt in range(max_retries):
        try:
            print(f"Waiting for scan... (attempt {attempt + 1})")
            await qr_login.wait()
            return
        except TimeoutError:
            if attempt >= max_retries - 1:
                print("\n❌ QR code expired. Maximum retries reached.")
                send_auth_event(
                    event="qr_expired", flow_id=flow_id, method=method, branch=branch
                )
                raise QrScanFailedError() from None
            send_auth_event(
                event="qr_expired", flow_id=flow_id, method=method, branch=branch
            )
            try:
                qr_login = await qr_login.recreate()
            except Exception as recreate_err:
                print(f"\n❌ Failed to regenerate QR: {recreate_err}")
                raise QrScanFailedError() from recreate_err
            send_auth_event(
                event="qr_session_created",
                flow_id=flow_id,
                method=method,
                branch=branch,
            )
            url = str(getattr(qr_login, "url", "")).strip()
            print("\nQR expired. New code generated:")
            _render_qr_terminal(url)
            print(f"  Or open: {url}")
        except SessionPasswordNeededError:
            raise QrScanNeeds2FAError() from None


async def _handle_qr_2fa(
    client: TelegramClient,
    *,
    flow_id: str = "",
    method: str = "qr",
    branch: str = "qr_2fa",
) -> bool:
    """Handle 2FA password prompt after QR scan. Returns True on success."""
    print("\nTwo-step verification is enabled for this account.")
    await _print_2fa_password_hint(client)
    for pwd_attempt in range(3):
        password = getpass.getpass("Please enter your 2FA password: ")
        send_auth_event(
            event="user_submitted_password",
            flow_id=flow_id,
            method=method,
            branch=branch,
        )
        try:
            await client.sign_in(password=password)
            send_auth_event(
                event="password_validated",
                flow_id=flow_id,
                method=method,
                branch=branch,
            )
            return True
        except PasswordHashInvalidError:
            send_auth_event(
                event="password_validated",
                flow_id=flow_id,
                method=method,
                branch=branch,
                error="2fa_wrong_password",
            )
            if pwd_attempt < 2:
                print("❌ Wrong password. Try again.")
            else:
                print("❌ Too many wrong password attempts.")
                return False
    return False


async def _qr_login_flow(
    client: TelegramClient,
    session_path: Path,
    *,
    flow_id: str = "",
) -> bool:
    """Perform QR code login flow. Returns True on success, False on failure.

    Uses temp SQLiteSession to avoid corrupting existing session files.
    Disconnects client before renaming temp file (SQLite requires closed handles).
    """
    try:
        qr_login = await client.qr_login()
        url = str(getattr(qr_login, "url", "")).strip()
        if not url:
            print("\u274c Telethon QR login did not return a valid URL")
            return False

        send_auth_event(
            event="qr_session_created", flow_id=flow_id, method="qr", branch="qr_scan"
        )

        # Render QR in terminal (best-effort) + always print URL
        rendered = _render_qr_terminal(url)
        print(
            "\nScan with Telegram: Settings \u2192 Devices \u2192 Link Desktop Device"
        )
        if not rendered:
            print("(QR rendering failed \u2014 use the link below)")
        print(f"  Or open: {url}")

        # Wait for scan (with timeout retries)
        try:
            await _wait_for_qr_scan(qr_login, flow_id=flow_id)
        except QrScanNeeds2FAError:
            send_auth_event(
                event="user_scanned_qr", flow_id=flow_id, method="qr", branch="qr_2fa"
            )
            if not await _handle_qr_2fa(client, flow_id=flow_id):
                flush_auth_events(flow_id)
                return False
        except QrScanFailedError:
            flush_auth_events(flow_id)
            return False
        else:
            send_auth_event(
                event="user_scanned_qr", flow_id=flow_id, method="qr", branch="qr_scan"
            )

        # Validate auth succeeded
        me = await client.get_me()
        if not me:
            print("\u274c Auth succeeded but get_me() failed")
            flush_auth_events(flow_id)
            return False

        send_auth_event(
            event="qr_login_confirmed", flow_id=flow_id, method="qr", branch="qr_scan"
        )
        username = (
            getattr(me, "username", None) or getattr(me, "first_name", None) or "user"
        )
        print(f"\u2705 Logged in as @{username}")

    except Exception as exc:
        traceback.print_exc()
        print(f"\u274c QR login failed due to an unexpected error: {exc}")
        flush_auth_events(flow_id)
        return False

    # Capture session filename before disconnect (client.session may be cleared after disconnect)
    temp_session_filename = getattr(client.session, "filename", None)

    # Disconnect before renaming temp session (SQLite requires closed handles)
    await client.disconnect()
    _finalize_temp_session_files(temp_session_filename, session_path)

    send_auth_event(
        event="session_established", flow_id=flow_id, method="qr", branch="qr_scan"
    )
    flush_auth_events(flow_id)
    return True


async def _qr_session_login(
    setup_config: SetupConfig,
    session_path: Path,
    bearer_token: str | None,
) -> tuple[Path, str | None] | None:
    """Handle QR login with temp session lifecycle. Creates, connects, and cleans up on failure."""
    session_dir = setup_config.session_directory

    # mkstemp creates the file atomically (avoids TOCTOU race with mktemp)
    fd, temp_path = tempfile.mkstemp(dir=str(session_dir))
    os.close(fd)
    os.unlink(temp_path)  # Telethon will create its own .session file at this base

    client_kwargs = {
        "session": temp_path,
        "api_id": int(setup_config.api_id),
        "api_hash": setup_config.api_hash,
        "entity_cache_limit": setup_config.entity_cache_limit,
        "receive_updates": True,
    }
    client_kwargs |= build_mtproto_client_args(setup_config.mtproto_proxy, print)

    client = TelegramClient(**client_kwargs)
    try:
        await client.connect()
        flow_id = str(uuid.uuid4())
        if not await _qr_login_flow(client, session_path, flow_id=flow_id):
            await client.disconnect()
            _cleanup_temp_session(Path(temp_path))
            return None
        return session_path, bearer_token
    except Exception:
        await client.disconnect()
        _cleanup_temp_session(Path(temp_path))
        raise


async def setup_telegram_session(
    setup_config: SetupConfig,
) -> tuple[Path, str | None] | None:
    """Set up Telegram session; return path and bearer token, or None if setup was cancelled."""

    session_dir = setup_config.session_directory

    # Ensure directory exists
    session_dir.mkdir(parents=True, exist_ok=True)

    # Determine session behavior based on server mode
    if setup_config.server_mode == ServerMode.HTTP_AUTH:
        # HTTP_AUTH mode: Generate random bearer token and use it as session name
        # This is the security model for production multi-user deployments
        bearer_token = generate_bearer_token()
        session_path = session_dir / bearer_token
        print(
            f"Setting up HTTP_AUTH session: {bearer_token[:12]}...{bearer_token[-4:]}.session"
        )
        print("(Random token ensures security for multi-user production)")
    else:
        # STDIO or HTTP_NO_AUTH mode: Use configured session name
        # This allows user-controlled session names like "personal", "work", etc.
        session_path = setup_config.session_path
        bearer_token = None  # No bearer token for STDIO/HTTP_NO_AUTH modes
        print(f"Setting up session: {setup_config.session_name}.session")
        print(f"(Mode: {setup_config.server_mode.value})")

    print("\nStarting Telegram session setup...")
    print(f"API ID: {setup_config.api_id}")

    is_qr_flow = not setup_config.bot_api_token and not setup_config.phone_number

    if setup_config.bot_api_token:
        print("Bot token: [REDACTED]")
        print("Account type: Bot")
    elif is_qr_flow:
        print("Auth method: QR Code")
        print("Account type: User")
    else:
        print(f"Phone: {mask_phone_number(setup_config.phone_number)}")
        print("Account type: User")

    # Note: Telethon adds .session extension automatically to session_path
    # So we pass session_path without .session, and Telethon creates session_path.session
    actual_session_file = Path(f"{session_path!s}.session")
    print(f"Session will be saved to: {actual_session_file}")
    print(f"Session directory: {session_dir}")

    # Non-TTY detection: QR needs terminal rendering (must be before input() calls)
    if is_qr_flow and not _is_interactive_terminal():
        print("❌ Non-interactive terminal detected. QR login requires a terminal.")
        print("   Use --bot-api-token for CI/scripted setup.")
        return None

    # Handle session file conflicts
    if actual_session_file.exists():
        print(f"\n⚠️  Session file already exists: {actual_session_file}")

        if setup_config.overwrite:
            print("✓ Overwriting existing session (as requested)")
            actual_session_file.unlink(missing_ok=True)
        else:
            # Ask user for confirmation
            response = input("Overwrite existing session? [y/N]: ").lower().strip()
            if response in ("y", "yes"):
                actual_session_file.unlink(missing_ok=True)
            else:
                print("❌ Setup cancelled")
                return None

    print(f"\n🔐 Authenticating with session: {setup_config.session_name}")

    if is_qr_flow:
        # QR login flow — delegated to _qr_session_login which manages temp session lifecycle
        return await _qr_session_login(setup_config, session_path, bearer_token)

    client = TelegramClient(
        session=session_path,
        api_id=int(setup_config.api_id),
        api_hash=setup_config.api_hash,
        entity_cache_limit=setup_config.entity_cache_limit,
        **build_mtproto_client_args(setup_config.mtproto_proxy, print),
    )

    try:
        await client.connect()

        if setup_config.bot_api_token:
            # Bot authentication
            flow_id = str(uuid.uuid4())
            send_auth_event(
                event="user_submitted_bot_token",
                flow_id=flow_id,
                method="bot",
                branch="bot_token",
            )
            print("Authenticating as bot...")
            await client.start(bot_token=setup_config.bot_api_token)
            print("Successfully authenticated as bot!")
            send_auth_event(
                event="session_established",
                flow_id=flow_id,
                method="bot",
                branch="bot_token",
            )
            flush_auth_events(flow_id)

            # Test the connection by getting bot info
            me = await client.get_me()
            username = getattr(me, "username", None) or ""
            first_name = getattr(me, "first_name", None) or "Bot"
            print(f"Bot username: @{username}")
            print(f"Bot name: {first_name}")
        else:
            # User authentication
            flow_id = str(uuid.uuid4())
            send_auth_event(
                event="user_submitted_phone",
                flow_id=flow_id,
                method="phone",
                branch="phone_code",
            )
            if not await client.is_user_authorized():
                print(
                    f"Sending code to {mask_phone_number(setup_config.phone_number)}..."
                )
                await client.send_code_request(setup_config.phone_number)
                send_auth_event(
                    event="code_requested",
                    flow_id=flow_id,
                    method="phone",
                    branch="phone_code",
                )

                # Get verification code (interactive only)
                code = input("Enter the code you received: ")
                send_auth_event(
                    event="user_submitted_code",
                    flow_id=flow_id,
                    method="phone",
                    branch="phone_code",
                )

                try:
                    await client.sign_in(setup_config.phone_number, code)
                    send_auth_event(
                        event="code_validated",
                        flow_id=flow_id,
                        method="phone",
                        branch="phone_code",
                    )
                except SessionPasswordNeededError:
                    send_auth_event(
                        event="code_validated",
                        flow_id=flow_id,
                        method="phone",
                        branch="phone_code",
                    )
                    print("\nTwo-step verification is enabled for this account.")
                    await _print_2fa_password_hint(client)
                    password = getpass.getpass("Please enter your 2FA password: ")
                    send_auth_event(
                        event="user_submitted_password",
                        flow_id=flow_id,
                        method="phone",
                        branch="phone_2fa",
                    )
                    try:
                        await client.sign_in(password=password)
                        send_auth_event(
                            event="password_validated",
                            flow_id=flow_id,
                            method="phone",
                            branch="phone_2fa",
                        )
                    except PasswordHashInvalidError:
                        send_auth_event(
                            event="password_validated",
                            flow_id=flow_id,
                            method="phone",
                            branch="phone_2fa",
                            error="2fa_wrong_password",
                        )
                        flush_auth_events(flow_id)
                        raise
                except Exception as exc:
                    send_auth_event(
                        event="code_validated",
                        flow_id=flow_id,
                        method="phone",
                        branch="phone_code",
                        error=_categorize_cli_error(exc),
                    )
                    flush_auth_events(flow_id)
                    raise

            send_auth_event(
                event="session_established",
                flow_id=flow_id,
                method="phone",
                branch="phone_code",
            )
            flush_auth_events(flow_id)
            print("Successfully authenticated!")

            # Test the connection by getting some dialogs
            async for dialog in client.iter_dialogs(limit=1):
                print(f"Successfully connected! Found chat: {dialog.name}")
                break

    finally:
        await client.disconnect()

    return session_path, bearer_token


def _print_mode_instructions(
    mode: ServerMode,
    session_path: Path,
    session_name: str,
    bearer_token: str | None,
    domain: str | None = None,
    api_id: str = "",
    api_hash: str = "",
) -> None:
    """Print mode-specific setup instructions with MCP config."""
    # Generate MCP config using shared utility
    config_json = generate_mcp_config_json(
        mode, session_name, bearer_token, domain, api_id, api_hash
    )

    # Print session info
    print(f"📁 Session saved to: {session_path}.session")

    if mode == ServerMode.HTTP_AUTH:
        print(f"🔑 Bearer Token: {bearer_token}")
        print("\n⚠️  SECURITY: Keep this Bearer token secret!")
        print("   Anyone with this token can access your Telegram account")
    else:
        print(f"🔑 Session name: {session_name}")

    # Print MCP configuration
    print("\n📋 MCP Configuration (add to your MCP client):")
    print(config_json)

    # Print mode-specific notes
    if mode == ServerMode.HTTP_AUTH:
        print("\n💡 For HTTP_AUTH mode (production):")
        print(
            f"   Configure your server domain via DOMAIN env var (currently: {domain or 'your-server.com'})"
        )
        print("   The Bearer token above is required for authentication")
        print("\n   Two auth methods are supported:")
        print("   1. Header-based (recommended):")
        print("      url: https://your-domain.com/v1/mcp")
        print("      headers: {Authorization: Bearer <token>}")
        print("   2. URL-based (for limited clients):")
        print("      url: https://your-domain.com/v1/url_auth/<token>/mcp")
        print("      (Token visible in URLs and logs)")
    elif mode == ServerMode.HTTP_NO_AUTH:
        print("\n💡 For HTTP_NO_AUTH mode (development):")
        print("   Start server with: fast-mcp-telegram --mode http-no-auth")
        print("   No authentication needed - use for local development only")
    else:  # STDIO
        print("\n💡 For STDIO mode (Cursor IDE):")
        print("   Save the config above to your Cursor MCP settings")
        if session_name != "telegram":
            print(f"   Note: Using custom session name '{session_name}'")


async def main():
    """Main setup function."""

    try:
        # Create setup configuration with automatic CLI parsing
        setup_config = SetupConfig()

        # Validate required fields
        setup_config.validate_required_fields()

        # Set up Telegram session
        session_result = await setup_telegram_session(setup_config)
        if session_result is None:
            return
        session_path, bearer_token = session_result

        # Display results
        print("\n✅ Setup complete!")
        _print_mode_instructions(
            setup_config.server_mode,
            session_path,
            setup_config.session_name,
            bearer_token,
            setup_config.domain,
            setup_config.api_id,
            setup_config.api_hash,
        )

        # Display account type specific information
        if setup_config.bot_api_token:
            print("\n🤖 Bot setup complete! You can now use the MTProto bridge:")
            print("   - Use /mtproto-api/... endpoints for bot operations")
            print(
                "   - High-level tools (search, send_message, etc.) are disabled for bots"
            )
        else:
            print("\n🚀 You can now use the Telegram search functionality!")

    except ValueError as e:
        print(f"❌ Error: {e}")
        return
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return


def sync_main():
    """Synchronous entry point for console script."""
    asyncio.run(main())


if __name__ == "__main__":
    sync_main()
