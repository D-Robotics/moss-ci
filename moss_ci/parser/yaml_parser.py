from __future__ import annotations
from pathlib import Path
import yaml
from moss_ci.models.pipeline import SuiteConfig


def parse_suite_string(yaml_str: str) -> SuiteConfig:
    """Parse a suite definition from a YAML string.

    Args:
        yaml_str: Raw YAML string containing a suite definition.

    Returns:
        A validated SuiteConfig instance.

    Raises:
        ValueError: If the YAML is invalid or doesn't match the schema.
    """
    data = yaml.safe_load(yaml_str)
    if data is None:
        raise ValueError("Empty YAML document")
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping, got {type(data).__name__}")
    try:
        return SuiteConfig(**data)
    except Exception as e:
        raise ValueError(f"Invalid suite definition: {e}") from e


def parse_suite(filepath: str | Path) -> SuiteConfig:
    """Parse a suite definition from a YAML file.

    Args:
        filepath: Path to the YAML file.

    Returns:
        A validated SuiteConfig instance.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the YAML is invalid or doesn't match the schema.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Suite file not found: {filepath}")
    content = path.read_text(encoding="utf-8")
    return parse_suite_string(content)
