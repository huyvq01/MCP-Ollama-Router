from app.services import history_manager

history_manager.add_user_message(
    "demo",
    "Hello"
)

history_manager.add_assistant_message(
    "demo",
    "Hi!"
)

print(
    history_manager.get_messages("demo")
)

history_manager.clear("demo")

print(
    history_manager.get_messages("demo")
)