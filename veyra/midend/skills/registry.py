"""Skill registry. Adding a skill only requires registering its implementation."""

from __future__ import annotations

from .base import Skill, SkillError
from .spcas9_gene_cutting import SpCas9GeneCuttingSkill
from .offtarget_toxicity_risk import OfftargetToxicityRiskSkill

_SKILLS: dict[str, Skill] = {
    "spcas9_gene_cutting": SpCas9GeneCuttingSkill(),
    "offtarget_toxicity_risk": OfftargetToxicityRiskSkill(),
}


def list_skills() -> list[dict]:
    return [skill.describe() for skill in _SKILLS.values()]


def get_skill(skill_id: str) -> Skill:
    try:
        return _SKILLS[skill_id]
    except KeyError:
        raise SkillError("unknown_skill", f"Unknown skill '{skill_id}'.", "skill_id") from None
