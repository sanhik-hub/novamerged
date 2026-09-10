from pathlib import Path

path = Path(r"..\Server\services\questionAPI.py")
data = path.read_bytes()
backup = Path(r"..\Server\services\questionAPI.py.backup-mcq-validation-v1")
backup.write_bytes(data)

old = (
    b"Before returning, verify:\r\n"
    b"- The original problem was interpreted correctly.\r\n"
    b"- All mathematics is correct.\r\n"
    b"- There are 5\xe2\x80\x9315 smaller questions.\r\n"
    b"- Every question has exactly 4 options and one correct answer.\r\n"
    b"- Hints, answers, and solutions are consistent.\r\n"
    b"- The smaller questions collectively prepare the student to solve the original problem.\r\n"
    b"- The output follows the configured JSON schema exactly."
)

old_lf = old.replace(b"\r\n", b"\n")

new = (
    b"Before returning, perform a strict mathematical validation for every generated question:\n"
    b"- Solve the generated question yourself before writing the options.\n"
    b"- Put the mathematically correct result in exactly one option.\n"
    b"- Construct the three incorrect options from specific plausible mathematical mistakes.\n"
    b"- Re-check every option against the solved question.\n"
    b"- The value of correct_option MUST identify the one option that is mathematically correct, using 1=A, 2=B, 3=C, 4=D.\n"
    b"- Never return a question when zero options are correct or when more than one option is correct; regenerate that question first.\n"
    b"- For calculation questions, independently substitute/differentiate/integrate where applicable to verify the selected correct option.\n"
    b"- Hints, correct_option, options, and solutions MUST all agree.\n"
    b"- There must be 5-15 smaller questions.\n"
    b"- Every question must have exactly 4 options and exactly one correct answer.\n"
    b"- The smaller questions collectively prepare the student to solve the original problem.\n"
    b"- Use ASCII mathematical notation only: x^2, x^(n+1), 1/2, sqrt(...), pi, sin(x), cos(x). Never use superscript Unicode characters, subscript Unicode characters, or Markdown backticks.\n"
    b"- The output follows the configured JSON schema exactly."
)

count = data.count(old)

if count == 0:
    count = data.count(old_lf)

if count != 1:
    raise SystemExit(
        f"ABORT: expected exactly one validation block, found {count}"
    )

data = data.replace(old if old in data else old_lf, new, 1)

path.write_bytes(data)

print("MCQ VALIDATION PROMPT PATCH COMPLETE")
print("Backup:", backup)
