from pathlib import Path

# Default directory for all output files (patches, fragments, summaries)
DEFAULT_OUTPUT_DIR = Path("out")

# Token limit per fragment, chosen to fit comfortably within most LLM context windows
# whilst leaving room for system prompts and responses
DEFAULT_MAX_TOKENS = 50_000

# tiktoken encoder name for GPT-4o; used for consistent token estimation across the project
TOKEN_ENCODER_NAME = "o200k_base"

DEFAULT_PATCH_EXT = ".patch"

# Default model for LLM operations (summarisation, etc.)
DEFAULT_MODEL_ID = "anthropic:claude-opus-4-5"

# Number of retries for LLM operations in case of transient failures
DEFAULT_RETRIES = 3
