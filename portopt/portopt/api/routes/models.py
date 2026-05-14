"""Model catalog endpoint — the menu of optimization models.

Returns the full menu with educational metadata (pedagogy block).
This is what the frontend renders as model cards in "learning mode".
"""

from fastapi import APIRouter, HTTPException

from portopt.api.pedagogy import get_pedagogy
from portopt.api.schemas import ModelInfo
from portopt.models import MODEL_REGISTRY

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelInfo])
def list_models():
    """Return all available models with full pedagogy.

    Ordered by educational tier (naive → allocation → alt_risk → risk_budget → robust).
    """
    seen = {}
    for alias, cls in MODEL_REGISTRY.items():
        canonical = cls.name
        seen.setdefault(canonical, {"cls": cls, "aliases": []})
        if alias != canonical:
            seen[canonical]["aliases"].append(alias)

    tier_order = {"naive": 0, "allocation": 1, "alt_risk": 2, "risk_budget": 3, "robust": 4, "roadmap": 5}

    out: list[ModelInfo] = []
    for canonical, info in seen.items():
        pedagogy = get_pedagogy(canonical)
        cls = info["cls"]
        out.append(ModelInfo(
            name=canonical,
            aliases=info["aliases"],
            tier=pedagogy.tier if pedagogy else "roadmap",
            risk_measure=cls.native_risk_measure,  # type: ignore[arg-type]
            requires_returns_history=cls.requires_returns,
            supports_short=cls.supports_short,
            pedagogy=pedagogy if pedagogy else _placeholder_pedagogy(canonical, cls),
        ))

    out.sort(key=lambda m: (tier_order.get(m.tier, 9), m.name))
    return out


@router.get("/{name}", response_model=ModelInfo)
def get_model_info(name: str):
    """Get a single model's full pedagogy."""
    key = name.lower()
    if key not in MODEL_REGISTRY:
        raise HTTPException(404, f"Model {name!r} not found")
    cls = MODEL_REGISTRY[key]
    pedagogy = get_pedagogy(cls.name)
    return ModelInfo(
        name=cls.name,
        aliases=[a for a, c in MODEL_REGISTRY.items() if c is cls and a != cls.name],
        tier=pedagogy.tier if pedagogy else "roadmap",
        risk_measure=cls.native_risk_measure,  # type: ignore[arg-type]
        requires_returns_history=cls.requires_returns,
        supports_short=cls.supports_short,
        pedagogy=pedagogy if pedagogy else _placeholder_pedagogy(cls.name, cls),
    )


def _placeholder_pedagogy(name: str, cls):
    """Minimal pedagogy for models without curated content (stubs)."""
    from portopt.api.schemas import PedagogyBlock
    return PedagogyBlock(
        model_name=name,
        tier="roadmap",
        one_liner="(Pedagogy content pending.)",
        formula_latex="",
        reference="Reference not available",
        references=[],
        drawbacks=[],
        when_to_use=[],
    )
