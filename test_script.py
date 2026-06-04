import os
import ast

# Load secret from environment / repo secrets instead of hardcoding
SECRET = os.environ.get("SECRET_KEY")


def risky_func(user_input):
    """
    Safely parse Python literal values (numbers, strings, lists, dicts).
    Avoid eval() to prevent code execution.
    """
    try:
        return ast.literal_eval(user_input)
    except (ValueError, SyntaxError):
        raise ValueError("Invalid input")
