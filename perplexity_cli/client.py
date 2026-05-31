from __future__ import annotations

import os
import sys

from .config import Config
from .providers import FallbackProvider, OpenRouterProvider, PerplexityProvider, Provider


def resolve_keys(
    perplexity_api_key: str | None,
    config: Config | None,
) -> tuple[str | None, str | None]:
    """Resolve (perplexity_key, openrouter_key) with precedence:

        explicit flag > environment variable > config file

    The explicit `perplexity_api_key` only feeds the Perplexity slot
    (there is intentionally no flag for OpenRouter). A `None` result means
    no key was found for that backend.
    """
    pkey = perplexity_api_key or os.environ.get("PERPLEXITY_API_KEY")
    okey = os.environ.get("OPENROUTER_API_KEY")
    if config is not None:
        pkey = pkey or config.perplexity_api_key
        okey = okey or config.openrouter_api_key
    return pkey, okey


def get_provider(
    perplexity_api_key: str | None = None,
    config: Config | None = None,
) -> Provider:
    """Resolve an API Provider based on available credentials.

    Resolution order per backend (see resolve_keys):
      1. Explicit `perplexity_api_key` (from --api-key), Perplexity slot only.
      2. PERPLEXITY_API_KEY / OPENROUTER_API_KEY environment variables.
      3. Config file values (config.perplexity_api_key / openrouter_api_key).

    Result:
      - Both keys present  → FallbackProvider(Perplexity primary, OpenRouter fallback).
      - Only Perplexity    → PerplexityProvider.
      - Only OpenRouter    → OpenRouterProvider.
      - Neither            → exit with a helpful error.

    An explicit empty `perplexity_api_key` (e.g. `--api-key ""`) is rejected.
    """
    if perplexity_api_key == "":
        print(
            "Error: --api-key was passed an empty value.\n"
            "Provide a real key or unset the flag to fall back to PERPLEXITY_API_KEY.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    pkey, okey = resolve_keys(perplexity_api_key, config)

    if pkey and okey:
        return FallbackProvider(PerplexityProvider(pkey), OpenRouterProvider(okey))
    if pkey:
        return PerplexityProvider(pkey)
    if okey:
        return OpenRouterProvider(okey)

    print(
        "Error: No API key found.\n\n"
        "Set the PERPLEXITY_API_KEY environment variable:\n"
        '  export PERPLEXITY_API_KEY="your-api-key"\n\n'
        "Or set OPENROUTER_API_KEY to use OpenRouter as a backend:\n"
        '  export OPENROUTER_API_KEY="your-api-key"\n\n'
        "Or pass it directly:\n"
        '  perplexity-cli --api-key your-api-key search "query"\n\n'
        "Get your Perplexity API key at: https://www.perplexity.ai/settings/api\n"
        "Get your OpenRouter API key at: https://openrouter.ai/keys",
        file=sys.stderr,
    )
    raise SystemExit(2)
