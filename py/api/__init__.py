"""Domain-specific API mixins for SherpaNoteAPI.

Each mixin provides @expose methods for a specific domain.
SherpaNoteAPI inherits from all mixins plus Bridge.
"""

from py.api.asr import AsrMixin
from py.api.ai import AiMixin
from py.api.storage import StorageMixin
from py.api.models import ModelsMixin
from py.api.ocr_plugin import OcrPluginMixin
from py.api.config_backup import ConfigBackupMixin

__all__ = [
    "AsrMixin",
    "AiMixin",
    "StorageMixin",
    "ModelsMixin",
    "OcrPluginMixin",
    "ConfigBackupMixin",
]
