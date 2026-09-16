import re
from typing import Dict, Any, List
from django.core.exceptions import ValidationError

PLACEHOLDER_REGEX = re.compile(r'\{\{\s*([a-zA-Z0-9_]+)\s*\}\}')


def validate_template_variables(body: str, allowed_variables: List[str]) -> List[str]:
    """
    Extracts all variables from template body and verifies they exist in allowed_variables.
    Raises ValidationError if unauthorized variable keys are used.
    """
    found_variables = set(PLACEHOLDER_REGEX.findall(body))
    allowed_set = set(allowed_variables) if allowed_variables else set()

    if allowed_set:
        unauthorized = found_variables - allowed_set
        if unauthorized:
            raise ValidationError(
                f"Unauthorized variables in template: {', '.join(sorted(unauthorized))}. "
                f"Allowed variables: {', '.join(sorted(allowed_set))}"
            )
    return list(found_variables)


def render_notification_template(template_body: str, context: Dict[str, Any], allowed_variables: List[str] = None) -> str:
    """
    Safely renders a template string with provided context variables.
    Does NOT use raw eval or unsafe template engines.
    """
    if allowed_variables:
        # Validate that no unapproved variables exist in template
        validate_template_variables(template_body, allowed_variables)

    def _replace(match):
        var_name = match.group(1).strip()
        if var_name in context:
            val = context[var_name]
            return str(val) if val is not None else ""
        return match.group(0)

    return PLACEHOLDER_REGEX.sub(_replace, template_body)
