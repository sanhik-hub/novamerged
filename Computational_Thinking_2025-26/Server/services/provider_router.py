from providers.wolfram_engine.provider import WolframProvider
from providers.sympy.provider import SymPyProvider
from providers.local_llm.provider import LocalLLMProvider
from providers.gemini.provider import GeminiProvider


class ProviderRouter:

    def __init__(self):
        self.providers = {
            "wolfram": WolframProvider(),
            "sympy": SymPyProvider(),
            "local_llm": LocalLLMProvider(),
            "gemini": GeminiProvider(),
        }

    def get_provider(self, name: str):
        provider = self.providers.get(name)

        if provider is None:
            raise ValueError(f"Unknown provider: {name}")

        return provider

    def calculate(
        self,
        query: str,
        provider: str = "wolfram",
        image_path: str | None = None,
    ):
        selected = self.get_provider(provider)

        if provider == "gemini":
            return selected.calculate(
                query,
                image_path=image_path,
            )

        return selected.calculate(query)

    def generate(
        self,
        prompt: str,
        max_tokens=None,
        temperature=None,
        system_prompt=None,
        enable_thinking=False,
    ):
        provider = self.get_provider("local_llm")

        return provider.generate(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=system_prompt,
            enable_thinking=enable_thinking,
        )
