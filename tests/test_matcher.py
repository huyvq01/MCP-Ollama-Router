from app.router.matcher import matcher

tests = [
    "Write a Python API",
    "Solve this math proof",
    "Describe this image",
    "Hello, how are you?",
]

for prompt in tests:

    print(prompt)

    print(
        "=>",
        matcher.match(prompt),
    )