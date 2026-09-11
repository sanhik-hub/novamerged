from pathlib import Path

ROOT = Path("Server")

def replace(path, old, new):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    n = s.count(old)
    if n != 1:
        raise RuntimeError(f"{path}: expected 1 match, got {n}")
    p.write_text(s.replace(old, new), encoding="utf-8", newline="\n")
    print("UPDATED", p)

replace(
    "services/provider_router.py",
    'from providers.local_llm.provider import LocalLLMProvider\n',
    'from providers.local_llm.provider import LocalLLMProvider\nfrom providers.gemini.provider import GeminiProvider\n'
)

replace(
    "services/provider_router.py",
    '            "local_llm": LocalLLMProvider(),\n',
    '            "local_llm": LocalLLMProvider(),\n            "gemini": GeminiProvider(),\n'
)

replace(
    "services/provider_router.py",
    '''    def calculate(
        self,
        query: str,
        provider: str = "wolfram",
    ):
        selected = self.get_provider(provider)
        return selected.calculate(query)
''',
    '''    def calculate(
        self,
        query: str,
        provider: str = "wolfram",
        image_path: str | None = None,
    ):
        selected = self.get_provider(provider)
        if provider == "gemini":
            return selected.calculate(query, image_path=image_path)
        return selected.calculate(query)
'''
)

replace(
    "services/computation_service.py",
    '''    def compute(
        self,
        query: str,
        operation: str = "compute",
        provider: str = "wolfram",
    ):
        normalization = normalize_expression_result(query)
        normalized_query = normalization.normalized

        try:
            result = self.router.calculate(
                query=normalized_query,
                provider=provider,
            )
''',
    '''    def compute(
        self,
        query: str,
        operation: str = "compute",
        provider: str = "wolfram",
        image_path: str | None = None,
    ):
        if provider == "gemini":
            normalized_query = query
        else:
            normalization = normalize_expression_result(query)
            normalized_query = normalization.normalized

        try:
            result = self.router.calculate(
                query=normalized_query,
                provider=provider,
                image_path=image_path,
            )
'''
)

replace(
    "services/workspace_computation_service.py",
    '''        if settings.computation_mode == "online":
            return None, "Online computation is not enabled yet"
        if settings.computation_mode != "offline":
            return None, "Invalid workspace computation mode"
''',
    '''        if settings.computation_mode != "online":
            return None, "Workspace computation requires online mode"
'''
)

replace(
    "services/workspace_computation_service.py",
    '''            result = self.computation.compute(
                query=question.question,
                operation=operation,
                provider=provider,
            )
''',
    '''            result = self.computation.compute(
                query=question.question,
                operation=operation,
                provider=provider,
                image_path=question.image_path,
            )
'''
)

replace(
    "services/workspace_solution_services.py",
    "from datetime import datetime\n",
    "from datetime import datetime, timezone\n"
)

replace(
    "services/workspace_solution_services.py",
    '    if mode not in {"solver", "assessment", "mcq"}:\n',
    '    if mode not in {"solver", "assessment", "mcq", "guided"}:\n'
)

replace(
    "services/workspace_solution_services.py",
    "datetime.now(datetime.timezone.utc)",
    "datetime.now(timezone.utc)"
)

p = ROOT / "providers/gemini"
p.mkdir(parents=True, exist_ok=True)
(p / "__init__.py").write_text("", encoding="utf-8", newline="\n")
(p / "provider.py").write_text(
'''from typing import Any

from providers.base import ComputationProvider
from services.questionAPI import get_response


class GeminiProvider(ComputationProvider):
    name = "gemini"

    def calculate(
        self,
        query: str,
        image_path: str | None = None,
    ) -> dict[str, Any]:
        try:
            response = get_response(
                username="workspace",
                question=query,
                img_path=image_path,
            )
            return {
                "success": True,
                "result": response,
                "error": None,
                "engine": self.name,
            }
        except Exception as exc:
            return {
                "success": False,
                "result": None,
                "error": str(exc),
                "engine": self.name,
            }

    def is_available(self) -> bool:
        return True
''',
    encoding="utf-8",
    newline="\n",
)

print("BACKEND COMPLETE")
