"""
Calculator Tool for arithmetic operations.
"""

from langchain_core.tools import tool


@tool
def calculator(first_num: float, second_num: float, operation: str) -> dict:
    """
    Perform a basic arithmetic operation on two numbers.
    Supported operations: add, sub, mul, div
    """
    try:
        op = operation.strip().lower()
        if op in ("add", "+"):
            result = first_num + second_num
        elif op in ("sub", "-"):
            result = first_num - second_num
        elif op in ("mul", "*"):
            result = first_num * second_num
        elif op in ("div", "/"):
            if second_num == 0:
                return {"error": "Division by zero is not allowed"}
            result = first_num / second_num
        else:
            return {"error": f"Unsupported operation '{operation}'. Use add, sub, mul, or div."}
        return {
            "first_num": first_num,
            "second_num": second_num,
            "operation": operation,
            "result": result,
        }
    except Exception as e:
        return {"error": str(e)}
