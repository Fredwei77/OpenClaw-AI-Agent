def register():
    return {
        "tools": [
            {
                "name": "example_tool",
                "function": example_tool
            }
        ]
    }

def example_tool(input_data):
    """
    Simulated entrypoint for third-party hook capabilities.
    """
    return {"result": f"processed input {input_data}"}
