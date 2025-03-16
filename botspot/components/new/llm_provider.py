"""

1 - tokens
a) make sure necessary libs are installed - anthropic, openai etc
b)
c) how do I get a client that's working?

2 - utils. for calmlib
a)
b)
c)
d)

3 - quotas
a) for friend - unlimited
b) single user mode - unlimited
c)
d)

----

1) Simple query_llm funciton
2) support 'telegram user' arg or check for single_user_mode
3) future: support interoperability with calmlib: make calmlib query_llm check if botspot is enabled, if so - use botspot's llm provider
4) async (have both versions - complete and acomplete)
5) 
6) 

Decisions:
- Do I need LLMProvider class? Just for the sake of having a class corresponding to the component? 
    - to wire with db, deps etc? Well, i store all those in deps.. do i need like properties or something? 
- Do I need _llm_query_base function? e.g. to return raw response, parsed json or just text 
- 

"""

from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

logger = get_logger()


class LLMProviderSettings(BaseSettings):
    enabled: bool = False

    class Config:
        env_prefix = "BOTSPOT_LLM_PROVIDER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class LLMProvider:
    def __init__(self, settings: LLMProviderSettings):
        self.settings = settings

    def _query_llm_base(self, prompt):
        raise NotImplementedError()

    async def _aquey_llm_base(self, prompt):
        raise NotImplementedError()

    # region
    # endregion


def setup_dispatcher(dp):
    return dp


def initialize(settings: LLMProviderSettings) -> LLMProvider:
    pass


# ---------------------------------------------
# region utils
# ---------------------------------------------


def get_llm_provider() -> LLMProvider:
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return deps.llm_provider


# ---------------------------------------------
# endregion utils
# ---------------------------------------------
