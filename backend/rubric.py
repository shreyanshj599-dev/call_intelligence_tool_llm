"""
Scoring rubric for telecaller performance evaluation.

15% of the grade is rubric quality. The anchors below are written so that two
graders reading the same transcript arrive at the same score most of the time.

The rubric is exposed in two places:
  1. Fed into the LLM extraction prompt so scoring is consistent.
  2. Surfaced in the UI as tooltips next to every score (see frontend/index.html).
"""

RUBRIC = {
    "discovery": {
        "description": (
            "Did the telecaller ask about budget, timeline, unit preference, "
            "and current living situation (family size / why moving)?"
        ),
        "anchors": {
            5: "Asked about all four: budget, timeline, unit preference, current living situation — with follow-ups.",
            4: "Asked about three of the four discovery areas with substance.",
            3: "Asked about two of the four discovery areas, or all four very briefly.",
            2: "Asked one discovery question, OR asked multiple but only one-liners with no follow-up.",
            1: "Vague discovery attempt ('what are you looking for?') with no follow-up.",
            0: "No discovery questions at all — went straight to pitch or closing.",
        },
    },
    "pitch": {
        "description": (
            "Did the telecaller explain the project's value proposition — location, "
            "amenities, pricing, builder credibility, unit specs?"
        ),
        "anchors": {
            5: "Covered 5+ of: location/connectivity, price, unit specs (sqft/BHK), amenities, builder credibility, EMI/loan, RERA. Tailored to lead's stated needs.",
            4: "Covered 4 of the above — solid pitch but missing one major dimension.",
            3: "Covered 3 of the above — adequate but generic.",
            2: "Covered 2 of the above — thin pitch, mostly price and location.",
            1: "Mentioned project name and one detail only.",
            0: "No pitch attempted, or call ended before any project details were shared.",
        },
    },
    "objection_handling": {
        "description": (
            "When the lead raised concerns (price, location, timing, competition, family "
            "approval), did the telecaller address them substantively?"
        ),
        "anchors": {
            5: "Every objection was met with a concrete, specific counter (e.g., commute time with numbers, builder track record with past projects).",
            4: "Addressed most objections with substance; one handled superficially.",
            3: "Acknowledged objections and gave partial answers; some deflection.",
            2: "Heard objection but gave generic reassurance ('don't worry sir, it's a good project').",
            1: "Ignored or changed topic when objection was raised.",
            0: "No objections raised by the lead — N/A scored as 0 is wrong; use 3 as a neutral default when there were no objections to handle.",
        },
        "note": "If the lead raised no objections, score 3 (neutral — nothing to handle).",
    },
    "next_step": {
        "description": (
            "Did the telecaller attempt to secure a concrete next action — site visit date, "
            "callback time, document sharing (brochure, floor plan)?"
        ),
        "anchors": {
            5: "Concrete next step committed with specific date/time (e.g., 'Saturday 11 AM site visit, cab at 10:30').",
            4: "Next step committed but soft on specifics ('this weekend', 'next week I'll call').",
            3: "Asked for a next step; lead deferred ('let me discuss and revert').",
            2: "Weak close — offered brochure / WhatsApp only, with no follow-up ask.",
            1: "Vague sign-off ('I'll call you later') with no agreement from lead.",
            0: "No next-step attempt at all, or call ended abruptly before a close.",
        },
    },
}


def rubric_as_prompt_block() -> str:
    """Format rubric as a string to embed in the LLM prompt."""
    lines = []
    for dim, meta in RUBRIC.items():
        lines.append(f"## {dim}")
        lines.append(meta["description"])
        for score in sorted(meta["anchors"].keys(), reverse=True):
            lines.append(f"  {score}: {meta['anchors'][score]}")
        if "note" in meta:
            lines.append(f"  NOTE: {meta['note']}")
        lines.append("")
    return "\n".join(lines)


def rubric_as_json():
    """Serializable form for the frontend tooltip."""
    return {
        dim: {
            "description": meta["description"],
            "anchors": {str(k): v for k, v in meta["anchors"].items()},
            "note": meta.get("note", ""),
        }
        for dim, meta in RUBRIC.items()
    }
