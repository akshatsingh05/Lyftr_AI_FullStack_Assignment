import logging
import os

import litellm


def setup_logging() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    litellm.suppress_debug_info = True
    litellm.set_verbose = False
    # LiteLLM's own logger can echo request details; keep it at WARNING so secrets never reach logs.
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)
