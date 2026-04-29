"""
Plugin Manager - 插件管理系统
负责插件的发现、加载、初始化和卸载
"""

import os
import json
import importlib
import sys
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PluginInfo:
    """插件元信息"""
    name: str
    version: str
    description: str = ""
    permissions: List[str] = field(default_factory=list)
    author: str = ""
    manifest_path: str = ""
    module_path: str = ""
    loaded_at: Optional[datetime] = None
    enabled: bool = True
    tools: List[Dict] = field(default_factory=list)


class PluginManager:
    """
    插件管理器

    功能：
    1. 自动发现 plugins/ 目录下的插件
    2. 加载和初始化插件
    3. 管理插件生命周期
    4. 提供插件工具调用接口
    """

    def __init__(self, plugins_dir: str = None):
        if plugins_dir is None:
            # 默认从项目根目录的 plugins 目录加载
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.plugins_dir = os.path.join(project_root, 'plugins')
        else:
            self.plugins_dir = plugins_dir

        self._plugins: Dict[str, PluginInfo] = {}
        self._tools: Dict[str, callable] = {}
        self._enabled = True

    def discover_plugins(self) -> List[PluginInfo]:
        """自动发现并加载所有插件"""
        discovered = []

        if not os.path.exists(self.plugins_dir):
            print(f"[PluginManager] Plugins directory not found: {self.plugins_dir}")
            return discovered

        for item in os.listdir(self.plugins_dir):
            plugin_path = os.path.join(self.plugins_dir, item)

            # 跳过非目录项和 plugin_manager 本身
            if not os.path.isdir(plugin_path) or item == 'plugin_manager':
                continue

            # 检查 manifest.json 是否存在
            manifest_path = os.path.join(plugin_path, 'manifest.json')
            if not os.path.exists(manifest_path):
                continue

            try:
                plugin_info = self._load_plugin_manifest(item, manifest_path)
                discovered.append(plugin_info)
                print(f"[PluginManager] Discovered plugin: {plugin_info.name} v{plugin_info.version}")
            except Exception as e:
                print(f"[PluginManager] Failed to load manifest for {item}: {e}")

        return discovered

    def _load_plugin_manifest(self, plugin_name: str, manifest_path: str) -> PluginInfo:
        """加载插件清单"""
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        plugin_info = PluginInfo(
            name=manifest.get('name', plugin_name),
            version=manifest.get('version', '1.0'),
            description=manifest.get('description', ''),
            permissions=manifest.get('permissions', []),
            author=manifest.get('author', ''),
            manifest_path=manifest_path,
            module_path=os.path.join(os.path.dirname(manifest_path), 'plugin.py')
        )

        return plugin_info

    def load_plugin(self, plugin_name: str) -> bool:
        """
        加载指定插件

        Args:
            plugin_name: 插件名称

        Returns:
            bool: 是否加载成功
        """
        if plugin_name in self._plugins:
            print(f"[PluginManager] Plugin {plugin_name} already loaded")
            return True

        # 查找插件信息
        plugin_info = None
        for discovered in self.discover_plugins():
            if discovered.name == plugin_name:
                plugin_info = discovered
                break

        if not plugin_info:
            print(f"[PluginManager] Plugin {plugin_name} not found")
            return False

        try:
            # 动态导入插件模块
            module_name = f"plugins.{plugin_name}.plugin"
            if module_name in sys.modules:
                module = sys.modules[module_name]
            else:
                module = importlib.import_module(module_name)

            # 调用插件的 register 函数
            if hasattr(module, 'register'):
                result = module.register()

                if isinstance(result, dict) and 'tools' in result:
                    plugin_info.tools = result['tools']

                    # 注册工具
                    for tool in result['tools']:
                        if 'name' in tool and 'function' in tool:
                            self._tools[tool['name']] = tool['function']

                plugin_info.loaded_at = datetime.now()
                self._plugins[plugin_name] = plugin_info

                print(f"[PluginManager] Loaded plugin: {plugin_name} with {len(plugin_info.tools)} tools")
                return True
            else:
                print(f"[PluginManager] Plugin {plugin_name} has no register() function")
                return False

        except Exception as e:
            print(f"[PluginManager] Failed to load plugin {plugin_name}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def load_all_plugins(self) -> int:
        """
        加载所有已发现的插件

        Returns:
            int: 成功加载的插件数量
        """
        discovered = self.discover_plugins()
        loaded_count = 0

        for plugin_info in discovered:
            if self.load_plugin(plugin_info.name):
                loaded_count += 1

        print(f"[PluginManager] Loaded {loaded_count}/{len(discovered)} plugins")
        return loaded_count

    def unload_plugin(self, plugin_name: str) -> bool:
        """
        卸载指定插件

        Args:
            plugin_name: 插件名称

        Returns:
            bool: 是否卸载成功
        """
        if plugin_name not in self._plugins:
            print(f"[PluginManager] Plugin {plugin_name} not loaded")
            return False

        plugin_info = self._plugins[plugin_name]

        # 注销工具
        for tool in plugin_info.tools:
            if 'name' in tool and tool['name'] in self._tools:
                del self._tools[tool['name']]

        del self._plugins[plugin_name]
        print(f"[PluginManager] Unloaded plugin: {plugin_name}")
        return True

    def get_tool(self, tool_name: str) -> Optional[callable]:
        """
        获取工具函数

        Args:
            tool_name: 工具名称

        Returns:
            callable or None: 工具函数
        """
        return self._tools.get(tool_name)

    def call_tool(self, tool_name: str, **kwargs) -> Any:
        """
        调用工具函数

        Args:
            tool_name: 工具名称
            **kwargs: 工具参数

        Returns:
            Any: 工具执行结果
        """
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        return tool(**kwargs)

    def list_plugins(self) -> List[PluginInfo]:
        """列出所有已加载的插件"""
        return list(self._plugins.values())

    def list_tools(self) -> List[str]:
        """列出所有可用工具"""
        return list(self._tools.keys())

    def get_plugin_info(self, plugin_name: str) -> Optional[PluginInfo]:
        """获取插件信息"""
        return self._plugins.get(plugin_name)

    def is_enabled(self) -> bool:
        """检查插件系统是否启用"""
        return self._enabled

    def set_enabled(self, enabled: bool):
        """设置插件系统启用状态"""
        self._enabled = enabled
        print(f"[PluginManager] Plugin system {'enabled' if enabled else 'disabled'}")


# 全局单例
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """获取全局插件管理器实例"""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


def init_plugin_system() -> int:
    """
    初始化插件系统

    Returns:
        int: 加载的插件数量
    """
    manager = get_plugin_manager()
    return manager.load_all_plugins()
