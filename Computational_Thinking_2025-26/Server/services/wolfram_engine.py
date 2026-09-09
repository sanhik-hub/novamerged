from dataclasses import dataclass
from typing import Any, Optional

from wolframclient.evaluation import WolframLanguageSession
from wolframclient.language import wlexpr


@dataclass
class WolframResult:
    success: bool

    result: Any = None
    error: Optional[str] = None
    raw_output: Optional[str] = None

    # Frontend/API-friendly representations
    text: Optional[str] = None
    latex: Optional[str] = None
    input_form: Optional[str] = None
    result_type: Optional[str] = None
    exact: Optional[bool] = None

    def to_dict(self) -> dict:
        """
        Convert the result into a JSON/API-friendly dictionary.

        Raw WolframClient expression objects are deliberately not
        returned through the API.
        """
        return {
            "success": self.success,
            "result": self.text if self.success else None,
            "latex": self.latex,
            "input_form": self.input_form,
            "result_type": self.result_type,
            "exact": self.exact,
            "error": self.error,
            "raw_output": self.raw_output,
        }


class WolframEngine:
    """
    Python interface to the local Wolfram Language Engine.

    Python
        ↓
    WolframLanguageSession
        ↓
    Wolfram Engine
        ↓
    Python result + formatted representations
    """

    def __init__(
        self,
        executable: Optional[str] = None,
        timeout: int = 30,
    ):
        self.timeout = timeout
        self.executable = executable
        self.session: Optional[WolframLanguageSession] = None

        self._start_session()

    # =========================================================
    # SESSION MANAGEMENT
    # =========================================================

    def _start_session(self) -> None:
        """Start a persistent Wolfram Engine session."""

        try:
            if self.executable:
                self.session = WolframLanguageSession(
                    kernel=self.executable
                )
            else:
                self.session = WolframLanguageSession()

        except Exception as exc:
            self.session = None

            raise RuntimeError(
                f"Failed to start Wolfram Engine session: {exc}"
            ) from exc

    def _ensure_session(self) -> None:
        """Ensure that a Wolfram session exists."""

        if self.session is None:
            self._start_session()

    def close(self) -> None:
        """Terminate the Wolfram Engine session."""

        if self.session is not None:
            try:
                self.session.terminate()
            except Exception:
                pass
            finally:
                self.session = None

    def restart(self) -> None:
        """Restart the Wolfram Engine session."""

        self.close()
        self._start_session()

    def __enter__(self):
        self._ensure_session()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    # =========================================================
    # RESULT SERIALIZATION / FORMATTING
    # =========================================================

    def _format_result(self, expression: str) -> dict:
        """
        Evaluate an expression and obtain API/frontend-friendly
        representations from Wolfram.

        Returns:
            {
                "text": ...,
                "latex": ...,
                "input_form": ...,
                "result_type": ...,
                "exact": ...
            }
        """

        self._ensure_session()

        try:
            # The expression has already been validated as Wolfram
            # Language input by the calculation itself.
            #
            # We evaluate the formatting wrapper directly inside
            # Wolfram so that the result is formatted there rather
            # than trying to call a WL Function from Python.
            formatting_expression = f"""
                With[
                    {{r = ({expression})}},
                    <|
                        "text" -> ToString[r, InputForm],
                        "latex" -> ToString[TeXForm[r]],
                        "input_form" -> ToString[r, InputForm],
                        "head" -> ToString[Head[r], InputForm]
                    |>
                ]
            """

            formatted = self.session.evaluate(
                wlexpr(formatting_expression)
            )

            if isinstance(formatted, dict):
                head = str(formatted.get("head", ""))

                # ---------------------------------------------
                # Semantic result type
                # ---------------------------------------------

                if head in {
                    "Integer",
                    "Rational",
                    "Real",
                    "Complex",
                }:
                    result_type = "number"

                elif head == "List":
                    result_type = "list"

                elif head == "Rule":
                    result_type = "rule"

                elif head == "Association":
                    result_type = "object"

                else:
                    result_type = "expression"

                input_form = str(
                    formatted.get("input_form", "")
                )

                # ---------------------------------------------
                # Conservative exactness detection
                # ---------------------------------------------
                #
                # Wolfram approximate numerical values normally
                # contain a decimal point or precision mark.
                #
                # This is deliberately conservative. More advanced
                # exactness classification can be added later.
                #
                exact = not any(
                    marker in input_form
                    for marker in (".", "`")
                )

                return {
                    "text": str(formatted.get("text", "")),
                    "latex": str(formatted.get("latex", "")),
                    "input_form": input_form,
                    "result_type": result_type,
                    "exact": exact,
                }

        except Exception:
            pass

        return self._fallback_format(expression)

    def _fallback_format(self, expression: str) -> dict:
        """
        Safe fallback if Wolfram formatting itself fails.

        The actual evaluated result is still returned separately
        by calculate().
        """

        text = str(expression)

        return {
            "text": text,
            "latex": None,
            "input_form": text,
            "result_type": "expression",
            "exact": None,
        }

    # =========================================================
    # CORE EVALUATION
    # =========================================================

    def calculate(self, expression: str) -> WolframResult:
        """
        Evaluate arbitrary Wolfram Language code.

        Wolfram can return special failure expressions such as $Failed
        without raising a Python exception. Those must be treated as
        unsuccessful computations and must never be cached as valid
        solutions.
        """
        if not expression or not expression.strip():
            return WolframResult(
                success=False,
                error="Expression is empty.",
            )

        try:
            self._ensure_session()

            # Evaluate exactly once.
            result = self.session.evaluate(
                wlexpr(expression)
            )

            # -----------------------------------------------------
            # Wolfram failure detection
            # -----------------------------------------------------
            #
            # Wolfram may return $Failed instead of raising an
            # exception. wolframclient represents this as a WL
            # expression/symbol, so inspect its string form.
            #
            result_text = str(result).strip()

            if result_text == "$Failed":
                return WolframResult(
                    success=False,
                    result=None,
                    error=(
                        "Wolfram Engine could not evaluate the "
                        "expression."
                    ),
                    raw_output=result_text,
                )

            # Also catch common failure-style symbolic results.
            if result_text in {
                "$Aborted",
                "$Canceled",
                "$Interrupt",
            }:
                return WolframResult(
                    success=False,
                    result=None,
                    error=f"Wolfram Engine evaluation returned {result_text}.",
                    raw_output=result_text,
                )

            # -----------------------------------------------------
            # Format the already-computed result
            # -----------------------------------------------------
            #
            # Do NOT call _format_result(expression) here because
            # that evaluates the original expression a second time.
            #
            # For now, use the evaluated result's string form for
            # the API-facing text. The raw Wolfram result remains
            # available internally.
            #
            text = result_text

            try:
                result_type = "expression"

                # Basic semantic classification.
                if isinstance(result, (int, float, complex)):
                    result_type = "number"
                elif isinstance(result, (list, tuple)):
                    result_type = "list"

                # Try Wolfram-side formatting without re-running the
                # original computation.
                formatting_expression = f"""
                    With[
                        {{r = ({result_text})}},
                        <|
                            "text" -> ToString[r, InputForm],
                            "latex" -> ToString[TeXForm[r]],
                            "input_form" -> ToString[r, InputForm],
                            "head" -> ToString[Head[r], InputForm]
                        |>
                    ]
                """

                formatted = self.session.evaluate(
                    wlexpr(formatting_expression)
                )

                if isinstance(formatted, dict):
                    head = str(formatted.get("head", ""))

                    if head in {
                        "Integer",
                        "Rational",
                        "Real",
                        "Complex",
                    }:
                        result_type = "number"
                    elif head == "List":
                        result_type = "list"
                    elif head == "Rule":
                        result_type = "rule"
                    elif head == "Association":
                        result_type = "object"

                    text = str(formatted.get("text", text))
                    latex = str(formatted.get("latex", ""))
                    input_form = str(
                        formatted.get("input_form", text)
                    )

                    exact = not any(
                        marker in input_form
                        for marker in (".", "`")
                    )
                else:
                    latex = None
                    input_form = text
                    exact = None

            except Exception:
                # Formatting failure must not turn a valid computation
                # into a failed computation.
                latex = None
                input_form = text
                exact = None

            return WolframResult(
                success=True,
                result=result,
                text=text,
                latex=latex,
                input_form=input_form,
                result_type=result_type,
                exact=exact,
                raw_output=result_text,
            )

        except Exception as exc:
            return WolframResult(
                success=False,
                result=None,
                error=f"Wolfram Engine evaluation failed: {exc}",
                raw_output=None,
            )

    # =========================================================
    # SOLVE
    # =========================================================

    def solve(
        self,
        equation: str,
        variable: str = "x",
    ) -> WolframResult:

        expression = f"Solve[{equation}, {variable}]"

        return self.calculate(expression)

    # =========================================================
    # SIMPLIFY
    # =========================================================

    def simplify(self, expression: str) -> WolframResult:

        return self.calculate(
            f"Simplify[{expression}]"
        )

    # =========================================================
    # EXPAND
    # =========================================================

    def expand(self, expression: str) -> WolframResult:

        return self.calculate(
            f"Expand[{expression}]"
        )

    # =========================================================
    # FACTOR
    # =========================================================

    def factor(self, expression: str) -> WolframResult:

        return self.calculate(
            f"Factor[{expression}]"
        )

    # =========================================================
    # DIFFERENTIATE
    # =========================================================

    def differentiate(
        self,
        expression: str,
        variable: str = "x",
    ) -> WolframResult:

        return self.calculate(
            f"D[{expression}, {variable}]"
        )

    # =========================================================
    # INTEGRATE
    # =========================================================

    def integrate(
        self,
        expression: str,
        variable: str = "x",
    ) -> WolframResult:

        return self.calculate(
            f"Integrate[{expression}, {variable}]"
        )

    # =========================================================
    # LIMIT
    # =========================================================

    def limit(
        self,
        expression: str,
        variable: str,
        value: str,
    ) -> WolframResult:

        return self.calculate(
            f"Limit[{expression}, {variable} -> {value}]"
        )

    # =========================================================
    # PLOT
    # =========================================================

    def plot(
        self,
        expression: str,
        variable: str = "x",
        xmin: float = -10,
        xmax: float = 10,
        points: int = 200,
    ) -> WolframResult:
        """
        Generate numerical plot data.

        Returns:
            [
                [x1, y1],
                [x2, y2],
                ...
            ]
        """

        if not expression or not expression.strip():
            return WolframResult(
                success=False,
                error="Expression is empty.",
            )

        if points <= 0:
            return WolframResult(
                success=False,
                error="Number of points must be greater than zero.",
            )

        try:
            self._ensure_session()

            step = (xmax - xmin) / points

            plot_expression = f"""
                Table[
                    {{
                        N[x],
                        N[
                            ({expression}) /. {variable} -> x
                        ]
                    }},
                    {{x, {xmin}, {xmax}, {step}}}
                ]
            """

            result = self.session.evaluate(
                wlexpr(plot_expression)
            )

            return WolframResult(
                success=True,
                result=result,
                text=str(result),
                input_form=str(result),
                result_type="list",
                exact=False,
            )

        except Exception as exc:
            return WolframResult(
                success=False,
                error=f"Wolfram plotting failed: {exc}",
            )

    # =========================================================
    # NUMERICAL EVALUATION
    # =========================================================

    def numerical(self, expression: str) -> WolframResult:

        return self.calculate(
            f"N[{expression}]"
        )

    # =========================================================
    # EQUATION / INEQUALITY REDUCTION
    # =========================================================

    def reduce(
        self,
        equation: str,
        variable: str = "x",
    ) -> WolframResult:

        return self.calculate(
            f"Reduce[{equation}, {variable}, Reals]"
        )

    # =========================================================
    # DIFFERENTIAL EQUATIONS
    # =========================================================

    def differential_equation(
        self,
        equation: str,
        function: str,
        variable: str = "x",
    ) -> WolframResult:

        return self.calculate(
            f"DSolve[{equation}, {function}, {variable}]"
        )

    # =========================================================
    # SERIES
    # =========================================================

    def series(
        self,
        expression: str,
        variable: str = "x",
        point: str = "0",
        order: int = 5,
    ) -> WolframResult:

        return self.calculate(
            f"Series[{expression}, "
            f"{{{variable}, {point}, {order}}}]"
        )

    # =========================================================
    # MATRIX / LINEAR ALGEBRA
    # =========================================================

    def determinant(self, matrix: str) -> WolframResult:

        return self.calculate(
            f"Det[{matrix}]"
        )

    def inverse(self, matrix: str) -> WolframResult:

        return self.calculate(
            f"Inverse[{matrix}]"
        )

    def eigenvalues(self, matrix: str) -> WolframResult:

        return self.calculate(
            f"Eigenvalues[{matrix}]"
        )

    def eigenvectors(self, matrix: str) -> WolframResult:

        return self.calculate(
            f"Eigenvectors[{matrix}]"
        )

    # =========================================================
    # ADVANCED SIMPLIFICATION
    # =========================================================

    def simplify_full(self, expression: str) -> WolframResult:

        return self.calculate(
            f"FullSimplify[{expression}]"
        )

    def assumptions(
        self,
        expression: str,
        assumptions: str,
    ) -> WolframResult:

        return self.calculate(
            f"Simplify[{expression}, {assumptions}]"
        )