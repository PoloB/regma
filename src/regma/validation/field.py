"""Define validator for fields in template model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from regma.core import FieldReference
from regma.error import ValidationError
from regma.validation.core import TemplateValidator

if TYPE_CHECKING:
    from regma.model import TemplateModelMeta


class FieldNameValidator(TemplateValidator):
    """Validate all fields have a valid name.

    Field names ending with underscore or containing double underscore would collide
    with regex construction.
    """

    @override
    def validate(self, model_cls: TemplateModelMeta) -> None:
        for attr in (*model_cls.__model_fields__, *model_cls.__typed_fields__):
            if attr.endswith("_"):
                msg = (
                    f"{model_cls.__name__}: field attribute {attr!r} cannot ends with "
                    f"underscore (reserved for regex construction)"
                )
                raise ValidationError(msg)

            if "__" in attr:
                msg = (
                    f"{model_cls.__name__}: field attribute {attr!r} cannot contains "
                    f"double underscores (reserved for regex construction)"
                )
                raise ValidationError(msg)


class FieldReferenceValidator(TemplateValidator):
    """Validate the model has all its fields in __template__."""

    @override
    def validate(self, model_cls: TemplateModelMeta) -> None:
        # Template shall contain all the element required to build its model references

        def _check_has_all_elements(
            model_cls_: TemplateModelMeta, references: set[str], parent_bound: str
        ) -> None:
            # Check leaf fields are used in the template
            missing_fields = set(model_cls_.__typed_fields__).difference(references)
            if missing_fields:
                # Rebuild the full missing field
                missing_full_fields = sorted(
                    f"{parent_bound}.{missing_field}" for missing_field in missing_fields
                )
                msg = (
                    f"All fields of {parent_bound!r} are not used in "
                    f"{model_cls.__name__} template (missing {missing_full_fields})"
                )
                raise ValidationError(msg)

            for bound_name, model_field in model_cls_.__model_fields__.items():
                # Get all the references starting with the bound name
                model_refs = {r for r in references if r.startswith(bound_name)}
                if bound_name in model_refs:
                    # There is a complete reference, this is ok
                    continue

                sub_references = {r.split(".", maxsplit=1)[1] for r in model_refs}
                # Check recursively
                _check_has_all_elements(
                    model_field.field.model,
                    sub_references,
                    f"{parent_bound}.{bound_name}" if parent_bound else bound_name,
                )

        ref_fields = {
            node.name
            for node in model_cls.__chain__.nodes
            if isinstance(node, FieldReference)
        }

        _check_has_all_elements(model_cls, ref_fields, "")
