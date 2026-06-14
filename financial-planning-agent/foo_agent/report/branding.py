"""White-label branding config. An advisor supplies a small YAML file (firm name,
colors, logo); everything else falls back to neutral defaults so a report always
renders."""
from __future__ import annotations

from dataclasses import dataclass, field

import yaml


@dataclass(frozen=True)
class Branding:
    firm_name: str = "Your Advisory Firm"
    primary_color: str = "#1f3a5f"
    accent_color: str = "#3d7ea6"
    logo_path: str | None = None
    footer: str = ""
    extra_disclosures: tuple = field(default_factory=tuple)

    @staticmethod
    def load(path: str | None) -> "Branding":
        if not path:
            return Branding()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return Branding(
            firm_name=data.get("firm_name", Branding.firm_name),
            primary_color=data.get("primary_color", Branding.primary_color),
            accent_color=data.get("accent_color", Branding.accent_color),
            logo_path=data.get("logo_path"),
            footer=data.get("footer", ""),
            extra_disclosures=tuple(data.get("extra_disclosures", [])),
        )
