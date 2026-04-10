from __future__ import annotations

import sys

from perplexity import Perplexity
from perplexity._exceptions import PerplexityError


def get_client(api_key: str | None = None) -> Perplexity:
    """Create a Perplexity API client.

    Resolution order for the API key:
    1. Explicit api_key argument (from --api-key CLI option)
    2. PERPLEXITY_API_KEY environment variable (handled by the SDK)

    If neither is available, prints a helpful error and exits.
    """
    try:
        return Perplexity(api_key=api_key) if api_key else Perplexity()
    except PerplexityError:
        print(
            "Error: No API key found.\n\n"
            "Set the PERPLEXITY_API_KEY environment variable:\n"
            '  export PERPLEXITY_API_KEY="your-api-key"\n\n'
            "Or pass it directly:\n"
            "  perplexity-cli --api-key your-api-key search \"query\"\n\n"
            "Get your API key at: https://www.perplexity.ai/settings/api",
            file=sys.stderr,
        )
        raise SystemExit(2)
