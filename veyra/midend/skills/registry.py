"""Skill registry. Adding a skill only requires registering its implementation."""

from __future__ import annotations

from .base import Skill, SkillError
from .spcas9_gene_cutting import SpCas9GeneCuttingSkill
from .offtarget_toxicity_risk import OfftargetToxicityRiskSkill
from .model_calibration import ModelCalibrationSkill

_calibration_skill = ModelCalibrationSkill()

_SKILLS: dict[str, Skill] = {
    "spcas9_gene_cutting": SpCas9GeneCuttingSkill(),
    "offtarget_toxicity_risk": OfftargetToxicityRiskSkill(),
    "model_calibration": _calibration_skill,
    "calibration": _calibration_skill,
}


def list_skills() -> list[dict]:
    # Return unique skills by skill_id
    seen = set()
    skills = []
    for skill in _SKILLS.values():
        if skill.metadata.skill_id not in seen:
            seen.add(skill.metadata.skill_id)
            skills.append(skill.describe())
    return skills


def get_skill(skill_id: str) -> Skill:
    try:
        return _SKILLS[skill_id]
    except KeyError:
        raise SkillError("unknown_skill", f"Unknown skill '{skill_id}'.", "skill_id") from None
