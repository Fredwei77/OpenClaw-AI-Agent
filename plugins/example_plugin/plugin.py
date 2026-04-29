"""
Example Plugin - 插件系统示例

这个插件演示了如何编写一个符合 OpenClaw 插件规范的插件。
包含三个示例工具函数。
"""

import os
import platform


def register():
    """
    插件注册函数 - 必须在插件模块中定义此函数

    Returns:
        dict: 包含插件元信息和工具列表的字典
    """
    return {
        "name": "example_plugin",
        "version": "1.0",
        "description": "示例插件 - 演示插件系统功能",
        "tools": [
            {
                "name": "hello_world",
                "description": "输出Hello World问候",
                "function": hello_world,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "要问候的名字"
                        }
                    }
                }
            },
            {
                "name": "process_data",
                "description": "处理输入数据并进行转换",
                "function": process_data,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "object",
                            "description": "要处理的数据对象"
                        },
                        "operation": {
                            "type": "string",
                            "description": "操作类型：uppercase/lowercase/reverse"
                        }
                    },
                    "required": ["data", "operation"]
                }
            },
            {
                "name": "get_platform_info",
                "description": "获取当前运行平台的信息",
                "function": get_platform_info,
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
    }


def hello_world(name: str = "World") -> dict:
    """
    Hello World 示例函数

    Args:
        name: 要问候的名字，默认为 "World"

    Returns:
        dict: 包含问候消息的字典
    """
    return {
        "success": True,
        "message": f"Hello, {name}! Welcome to OpenClaw Plugin System.",
        "timestamp": str(__import__('datetime').datetime.now())
    }


def process_data(data: dict, operation: str = "uppercase") -> dict:
    """
    数据处理示例函数

    Args:
        data: 要处理的数据对象
        operation: 操作类型 - uppercase/lowercase/reverse

    Returns:
        dict: 处理结果
    """
    if not isinstance(data, dict):
        return {
            "success": False,
            "error": "Data must be a dictionary"
        }

    result = {}

    if operation == "uppercase":
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = value.upper()
            else:
                result[key] = value
    elif operation == "lowercase":
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = value.lower()
            else:
                result[key] = value
    elif operation == "reverse":
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = value[::-1]
            else:
                result[key] = value
    else:
        return {
            "success": False,
            "error": f"Unknown operation: {operation}"
        }

    return {
        "success": True,
        "operation": operation,
        "result": result
    }


def get_platform_info() -> dict:
    """
    获取当前平台信息

    Returns:
        dict: 平台信息字典
    """
    return {
        "success": True,
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "cwd": os.getcwd()
    }
