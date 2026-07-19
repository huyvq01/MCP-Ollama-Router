from app.services import router

session = "demo"

print("=" * 50)

print(
    router.chat(
        session,
        "Xin chào"
    )
)

print("=" * 50)

print(
    router.chat(
        session,
        "Bạn còn nhớ câu trước không?"
    )
)

print("=" * 50)

print(
    router.sessions()
)