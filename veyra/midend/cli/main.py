"""CLI for MIDEND runtime configuration."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import sys

try:
    from ..ai.errors import AIProviderError, AIProviderNotConfiguredError
    from ..ai.openai_compatible import OpenAICompatibleProvider
    from ..config.ai_provider import AIConfigError, get_ai_config, get_ai_config_manager
except ImportError:  # pragma: no cover
    from ai.errors import AIProviderError, AIProviderNotConfiguredError
    from ai.openai_compatible import OpenAICompatibleProvider
    from config.ai_provider import AIConfigError, get_ai_config, get_ai_config_manager


def _status(_: argparse.Namespace) -> int:
    status = get_ai_config().status()
    # Explicit field selection is a guard against accidentally adding secrets later.
    print(json.dumps({key: status[key] for key in
                      ("provider", "base_url", "model", "configured", "source")}, indent=2))
    return 0


def _configure(args: argparse.Namespace) -> int:
    current = get_ai_config()
    api_key = args.api_key
    if api_key is None:
        api_key = getpass.getpass("API key (hidden): ")
    try:
        config = get_ai_config_manager().configure(
            base_url=args.base_url or current.base_url,
            api_key=api_key,
            model=args.model or current.model,
            persist=False,
        )
    except AIConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({key: config.status()[key] for key in
                      ("provider", "base_url", "model", "configured", "source")}, indent=2))
    print("Provider configuration is process-local; plaintext API-key persistence is disabled.")
    return 0


async def _test_async() -> int:
    try:
        print(json.dumps(await OpenAICompatibleProvider().test(), indent=2))
        return 0
    except AIProviderNotConfiguredError as exc:
        print(json.dumps({"success": False, "error": {"code": exc.code, "message": str(exc)}}))
        return 2
    except AIProviderError as exc:
        print(json.dumps({"success": False, "error": {"code": "ai_provider_error", "message": str(exc)}}))
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="midend", description="VEYRA MIDEND runtime configuration")
    groups = parser.add_subparsers(dest="group")
    ai = groups.add_parser("ai", help="AI provider operations")
    commands = ai.add_subparsers(dest="command", required=True)
    status = commands.add_parser("status", help="show safe provider status")
    status.set_defaults(handler=_status)
    configure = commands.add_parser("configure", help="configure the provider")
    configure.add_argument("--base-url")
    configure.add_argument("--api-key", help="API key (prefer hidden interactive prompt)")
    configure.add_argument("--model")
    configure.add_argument("--no-persist", action="store_true", help="kept for CLI compatibility")
    configure.set_defaults(handler=_configure)
    test = commands.add_parser("test", help="explicitly make a provider test request")
    test.set_defaults(handler=lambda _: asyncio.run(_test_async()))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not hasattr(args, "handler"):
        build_parser().print_help()
        return 2
    return args.handler(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
