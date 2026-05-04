"""
Plugins — Message lifecycle hooks for pre/post processing.

Plugins intercept messages at specific events (ON_RECEIVE_MESSAGE,
ON_HANDLE_CONTEXT, etc.) and can modify or block the message flow.

Distinction from agent/tools/:
  - plugins/     → Message lifecycle hooks (triggered automatically)
  - agent/tools/ → Called by LLM via function calling (Agent decides when)

To add a plugin: create a class extending Plugin, register it with
@PluginManager.register(), and implement event handlers (on_handle_context, etc.).
"""

from .event import *
from .plugin import *
from .plugin_manager import PluginManager

instance = PluginManager()

register = instance.register
# load_plugins                = instance.load_plugins
# emit_event                  = instance.emit_event
