from functools import lru_cache

import tiktoken

from ..conf import TOKEN_ENCODER_NAME


@lru_cache
def _get_token_encoder() -> tiktoken.Encoding:
    """Returns the tiktoken encoder configured for this project"""
    return tiktoken.get_encoding(encoding_name=TOKEN_ENCODER_NAME)


def estimate_tokens(content: str) -> int:
    """Estimate the number of tokens in a string using the project's configured encoder."""
    encoder = _get_token_encoder()
    return len(encoder.encode(content))
