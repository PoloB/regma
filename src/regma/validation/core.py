"""Core interface of template validator."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from regma.model import TemplateModelMeta


class TemplateValidator(abc.ABC):
    """Protocol of template validator."""

    @abc.abstractmethod
    def validate(self, template: TemplateModelMeta) -> None:
        """Implement template validation.

        Raising ValidityError if validation fails.
        """
