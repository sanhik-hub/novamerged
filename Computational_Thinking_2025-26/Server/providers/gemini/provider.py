from typing import Any

from providers.base import ComputationProvider
from services.questionAPI import (
    generate_gemini_response,
    get_response,
)

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

    def generate(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        system_prompt: str | None = None,
        enable_thinking: bool = False,
    ) -> dict[str, Any]:
        try:
            response = generate_gemini_response(
                prompt=prompt,
                system_prompt=system_prompt,
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
