from wolframclient.evaluation import WolframLanguageSession
from wolframclient.language import wlexpr

KERNEL = r"C:\Program Files\Wolfram Research\Wolfram Engine\15.0\WolframKernel.exe"

w = WolframLanguageSession(kernel=KERNEL)

print("Session started.")

# Compute the expression
r = w.evaluate(wlexpr("3*x^2"))

print("\nRESULT TYPE:")
print(type(r))

print("\nRAW RESULT:")
print(r)

# Ask Wolfram to format the expression directly
formatted = w.evaluate(
    wlexpr(
        '''
        With[
            {r = 3*x^2},
            <|
                "text" -> ToString[r, InputForm],
                "latex" -> ToString[TeXForm[r]],
                "input_form" -> ToString[r, InputForm],
                "head" -> ToString[Head[r], InputForm]
            |>
        ]
        '''
    )
)

print("\nFORMATTED TYPE:")
print(type(formatted))

print("\nFORMATTED RESULT:")
print(formatted)

w.terminate()

print("\nSession terminated.")