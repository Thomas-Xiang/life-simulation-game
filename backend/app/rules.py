"""v2.1 rules layered over the original v2 engine.

Financial values, partner distributions and progression are fictional game rules.
Keep simulation.py unchanged.
"""
import copy

from .simulation import *
from . import simulation as core


# Preserve the original implementations before installing updated helpers.
_old_new = core.new_life
_old_question = core.question
_old_choose = core.choose
_old_advance = core.advance
_old_salary = core.salary
_old_cost = core.annual_cost
_old_finance = core.annual_finance
_old_quote = core.quote
_old_jobs = core.jobs
_old_impact = core.impact
_old_buy_terms = core.buy_terms


LIFE_SCIENCE = {"biology", "biochemistry", "neuroscience"}

MAJORS.update({
    "biochemistry": "Biochemistry",
    "neuroscience": "Neuroscience",
    "economics": "Economics",
    "psychology": "Psychology",
    "legal_studies": "Legal studies",
    "marketing": "Marketing",
})

# Modeled duration and annual tuition, not real program prices.
PROGRAMS.update({
    "law": (3, 40000),
    "masters": (2, 22000),
    "mba": (2, 30000),
})

# Major: role, display label, fictional starting pay, game sector.
# These supplement the original major-specific careers.
EXTRA = {
    "computing": [
        ("data_analyst", "Data analyst", 68000, "technology"),
        ("cybersecurity", "Security analyst", 76000, "technology"),
        ("qa", "Quality assurance analyst", 61000, "technology"),
    ],
    "finance": [
        ("accounting", "Staff accounting", 58000, "finance"),
        ("risk", "Risk analyst", 70000, "finance"),
    ],
    "economics": [
        ("economic_analyst", "Economic analyst", 65000, "finance"),
        ("consulting", "Business consulting", 72000, "finance"),
    ],
    "biology": [
        ("clinical_research", "Clinical research coordinator", 53000, "biotech"),
        ("biotech", "Biotech associate", 60000, "biotech"),
    ],
    "biochemistry": [
        ("biotech", "Biotech associate", 60000, "biotech"),
        ("lab", "Laboratory support", 49000, "biotech"),
    ],
    "neuroscience": [
        ("research_assistant", "Research assistant", 51000, "biotech"),
    ],
    "engineering": [
        ("quality_engineer", "Quality engineering team", 70000, "manufacturing"),
        (
            "manufacturing_engineer",
            "Manufacturing engineering team",
            73000,
            "manufacturing",
        ),
    ],
    "psychology": [
        ("hr", "Human resources associate", 52000, "public_service"),
        (
            "community_support",
            "Community support, nonclinical",
            45000,
            "public_service",
        ),
    ],
    "legal_studies": [
        ("legal_support", "Legal support, not attorney", 50000, "public_service"),
        ("compliance", "Compliance associate", 62000, "finance"),
    ],
    "marketing": [
        ("marketing", "Marketing specialist", 57000, "technology"),
        ("market_research", "Market research analyst", 62000, "finance"),
    ],
    "humanities": [
        ("technical_writer", "Technical writing", 63000, "technology"),
    ],
    "arts": [
        ("ux", "UX design", 68000, "technology"),
    ],
    "education": [
        (
            "learning_support",
            "Learning support coordinator",
            47000,
            "public_service",
        ),
    ],
    "nursing": [
        ("care_coordinator", "Care coordinator scenario", 64000, "healthcare"),
    ],
}

for rows in EXTRA.values():
    for role, label, pay, sector in rows:
        BASE_PAY[role] = pay
        SECTORS[role] = sector

BASE_PAY.update({
    "attorney": 95000,
    "research_specialist": 74000,
    "management": 90000,
})

SECTORS.update({
    "attorney": "public_service",
    "research_specialist": "biotech",
    "management": "finance",
})


def ensure(l):
    """Defaults prevent missing-field crashes; new journeys are recommended."""
    l.setdefault("done", [])
    l.setdefault("partner", None)
    l.setdefault("partner_offer", None)
    l.setdefault("personal_income", 0)
    l.setdefault("partner_income", 0)
    l.setdefault("family_plan", None)
    l.setdefault("marriage_plan", None)
    l.setdefault("dependent_ages", [])
    return l


def new_life(home, seed, life_id):
    l = ensure(_old_new(home, seed, life_id))

    # Independent fictional draw, not a demographic or compatibility model.
    r = rng(seed, "partner-background")
    level = r.choice(["unemployed", "low", "mid", "high"])

    l["partner_offer"] = {
        "level": level,
        "base_income": cents({
            "unemployed": 0,
            "low": 28000,
            "mid": 60000,
            "high": 110000,
        }[level]),
        "education": r.choice([
            "high school",
            "associate degree",
            "bachelor degree",
            "graduate degree",
        ]),
        "cash": cents(r.choice([0, 2000, 10000, 25000])),
        "debt": cents(r.choice([0, 5000, 20000, 40000])),
        "experience": 0,
    }

    return l


def salary(l, state=None):
    """Personal pay: state/sector base plus modeled experience growth."""
    temp = copy.deepcopy(l)
    temp["experience"] = 0
    base = _old_salary(temp, state)

    # Training pay follows the existing program rules.
    if l["program"] or l["retired"]:
        return base

    # Fictional 3.5% annual experience progression, capped at 40 working years.
    return round(base * 1.035 ** min(l["experience"], 40))


def partner_pay(l, state=None):
    p = l.get("partner")
    if not p:
        return 0

    # Simplified household retirement scenario.
    if l["retired"]:
        return cents(18000) if p["base_income"] else 0

    return round(
        p["base_income"]
        * STATES[state or l["state"]]["wage"]
        * 1.025 ** min(p["experience"], 40)
    )


def annual_cost(l, state=None, housing=None):
    extra_adult = (
        cents(8000 * STATES[state or l["state"]]["cost"])
        if l.get("partner")
        else 0
    )
    return _old_cost(l, state, housing) + extra_adult


def annual_finance(l, seed):
    ensure(l)
    if l["age"] < 18:
        return

    partner_income = partner_pay(l)
    partner_tax = round(partner_income * .22)

    # Make partner cash available before paying tuition, expenses and debt.
    # Otherwise the engine could borrow unnecessarily before adding that income.
    l["cash"] += partner_income - partner_tax

    previous_experience = l["experience"]
    _old_finance(l, seed)

    l["personal_income"] = l["income"]
    l["partner_income"] = partner_income
    l["income"] += partner_income
    l["tax"] += partner_tax
    l["cashflow"] += partner_income - partner_tax

    # Do not award paid-work experience for an unpaid/nonworking role.
    if l["career"] in {"none", "student", "caregiving"} and not l["program"]:
        l["experience"] = previous_experience

    if l["partner"] and not l["retired"] and l["partner"]["base_income"]:
        l["partner"]["experience"] += 1

    l["ledger"][-1].update(
        personal_income=l["personal_income"],
        partner_income=partner_income,
        income=l["income"],
        tax=l["tax"],
        cashflow=l["cashflow"],
    )


def quote(l, code, housing="shared"):
    """Keep relocation previews consistent with household finances."""
    result = _old_quote(l, code, housing)
    extra = partner_pay(l, code)

    result["personal_income"] = result["income"]
    result["partner_income"] = extra
    result["income"] += extra
    result["tax"] += round(extra * .22)
    result["surplus"] += extra - round(extra * .22)

    return result


def buy_terms(l):
    terms = _old_buy_terms(l)
    household_income = salary(l) + partner_pay(l)

    terms["eligible"] = (
        not l["program"]
        and household_income > 0
        and l["cash"] >= terms["cash_needed"]
        and terms["annual_payment"] <= household_income * .30
        and not l["home_value"]
    )
    return terms


def jobs(l):
    result = _old_jobs(l)
    credentials = set(l["credentials"])

    for major, rows in EXTRA.items():
        if "bachelor:" + major in credentials:
            result += [(role, label) for role, label, _, _ in rows]

    if "law" in credentials and "bar_license" in credentials:
        result.append((
            "attorney",
            "Attorney: modeled bar admission completed",
        ))

    if "masters" in credentials and l["major"] in LIFE_SCIENCE:
        result.append(("research_specialist", "Research specialist"))

    if "mba" in credentials:
        result.append(("management", "Business management scenario"))

    return list(dict(result).items())


def graduate_options(l):
    credentials = set(l["credentials"])
    options = [("work", "Enter the workforce")]

    # Requested game restriction: medicine only through life-science preparation.
    if l["major"] in LIFE_SCIENCE and "premed" in credentials:
        options.append(("medical", "Medical school: 4 modeled years"))

    options += [
        ("law", "Law school: 3 modeled years"),
        ("masters", "Master degree: 2 modeled years"),
    ]

    if l["major"] in {"finance", "economics", "marketing"}:
        options.append(("mba", "MBA: 2 modeled years"))

    return options


def impact(l, key, value):
    if key == "relationship":
        if value == "marry":
            return (
                "Pool partner cash/debt once; $3,000 wedding; add partner "
                "earnings and $8,000 x state cost/year household expenses."
            )
        return "No new shared income, assets or debt."

    if key == "family":
        count = {"one": 1, "two": 2}.get(value, 0)
        return (
            f"Add {count} dependent(s): "
            f"${count * 6500:,} x state cost/year until age 18."
        )

    if key == "graduate":
        if value == "work":
            return "No further tuition; choose a credential-eligible career next."

        years, tuition = PROGRAMS[value]
        return (
            f"{years} modeled years; ${tuition:,}/year tuition plus "
            "living costs. Shortfalls become debt."
        )

    if key == "bar":
        return (
            "$2,000 modeled fee; attorney roles unlocked."
            if value == "pass"
            else "No fee; attorney roles remain locked."
        )

    return _old_impact(l, key, value)


def question(l):
    ensure(l)

    if l["complete"] or not l["chapter"]:
        return None

    while l["queue"]:
        key = l["queue"][0]

        if key in l["done"]:
            l["queue"].pop(0)
            continue

        if key == "premed" and l["major"] not in LIFE_SCIENCE:
            l["queue"].pop(0)
            continue

        if key == "graduate":
            return q(
                l,
                key,
                "Your degree is complete: work or further study?",
                graduate_options(l),
                "One-time graduation decision. "
                "All admissions are fictional scenarios.",
            )

        if key == "bar":
            return q(
                l,
                key,
                "Law school completed: bar admission",
                [
                    ("pass", "Complete the modeled bar-admission requirements"),
                    ("defer", "Do not enter licensed attorney work"),
                ],
                "Completion costs $2,000 in this game. "
                "Not an actual license or exam prediction.",
            )

        if key == "relationship":
            p = l["partner_offer"]

            description = (
                f"Fictional partner: {p['level']} income, {p['education']}; "
                f"gross ${p['base_income'] / 100:,.0f} before state multiplier; "
                f"cash ${p['cash'] / 100:,.0f}; "
                f"debt ${p['debt'] / 100:,.0f}."
            ) if p else "No partner profile available for this old save."

            options = [
                ("single", "Choose an independent life"),
                ("later", "Revisit once at age 33"),
            ]

            if p:
                options.insert(
                    0, ("marry", "Choose marriage with this fictional partner")
                )

            if l["age"] >= 33:
                options = [o for o in options if o[0] != "later"]

            return q(
                l,
                key,
                "Your relationship chapter",
                options,
                description
                + " Marriage pools game cash/debt and adds household "
                "living costs; no legal property model.",
            )

        if key == "family":
            options = [
                ("none", "No children in this story"),
                ("one", "One child"),
                ("two", "Two children"),
                ("later", "Revisit once at age 35"),
            ]

            if l["age"] >= 35:
                options = [o for o in options if o[0] != "later"]

            return q(
                l,
                key,
                "Would you like children in this story?",
                options,
                "Available independently of marriage. Each dependent adds "
                "$6,500 x state cost per year until age 18. "
                "Fictional story choice.",
            )

        if key == "housing":
            result = _old_question(l)
            terms = buy_terms(l)

            if not terms["eligible"] and not l["home_value"]:
                result["help"] += (
                    " Buying is currently locked: need "
                    f"${terms['cash_needed'] / 100:,.0f} cash, no active study, "
                    "and payments within 30% of modeled household gross."
                )

            return result

        return _old_question(l)

    l["chapter"] = None
    return None


def choose(l, question_id, option_id):
    current = question(l)

    if not current or current["id"] != question_id:
        raise ValueError("Question changed; reload the life")

    options = {o["id"]: o for o in current["options"]}
    if option_id not in options:
        raise ValueError("Ineligible choice")

    key = current["key"]

    if key not in {"graduate", "bar", "relationship", "family"}:
        previous_role = l["career"]
        previous_experience = l["experience"]

        result = _old_choose(l, question_id, option_id)

        # Selecting the same role must not erase accumulated experience.
        if key == "career" and result["career"] == previous_role:
            result["experience"] = previous_experience

        if key in {"premed", "wellbeing", "path", "retire"}:
            result["done"].append(key)

        return result

    l["queue"].pop(0)

    if key == "graduate":
        if option_id == "work":
            l["queue"] = ["career", "relocate", "housing"] + l["queue"]
        else:
            enroll(l, option_id)

    elif key == "bar":
        if option_id == "pass":
            spend(l, cents(2000))
            l["credentials"].append("bar_license")

        l["queue"] = ["career", "relocate", "housing"] + l["queue"]

    elif key == "relationship":
        l["marriage_plan"] = option_id

        if option_id == "marry":
            l["relationship"] = "married"
            l["partner"] = copy.deepcopy(l["partner_offer"])

            l["cash"] += l["partner"]["cash"]
            l["other_debt"] += l["partner"]["debt"]

            # Explicit fictional wedding budget.
            spend(l, cents(3000))

        if option_id != "later":
            l["done"].append(key)

    elif key == "family":
        l["family_plan"] = option_id

        if option_id in {"one", "two"}:
            count = 1 if option_id == "one" else 2
            l["dependent_ages"] += [0] * count
            l["dependents"] = len(l["dependent_ages"])

        if option_id != "later":
            l["done"].append(key)

    if key in {"graduate", "bar"}:
        l["done"].append(key)

    l["answers"].append({
        "age": l["age"],
        "question": current["title"],
        "option": options[option_id]["label"],
        "impact": current["help"],
    })

    event(
        l,
        current["title"],
        options[option_id]["label"] + ". " + current["help"],
    )

    l["queue"] = list(dict.fromkeys(l["queue"]))
    l["version"] += 1
    question(l)

    return l


def advance(l, seed, mortality):
    ensure(l)
    previous_program = copy.deepcopy(l["program"])

    # Retains the existing annual mortality draw, financial update,
    # dependent aging and actual training-duration progression.
    _old_advance(l, seed, mortality)

    if l["complete"]:
        return l

    # Discard the old decade-review questionnaires.
    l["chapter"], l["queue"] = None, []
    keys = []

    if l["age"] == 18:
        keys += ["path", "wellbeing"]

    if previous_program and l["program"] is None:
        kind = previous_program["kind"]
        keys += {
            "cc": ["transfer"],
            "bachelor": ["graduate"],
            "medical": ["residency"],
            "residency": ["license"],
            "law": ["bar"],
        }.get(kind, ["career", "relocate", "housing"])

    if l["age"] in {25, 40}:
        keys += ["housing"]

    if l["age"] == 28 or (
        l["age"] == 33 and l["marriage_plan"] == "later"
    ):
        keys += ["relationship"]

    if l["age"] == 30 or (
        l["age"] == 35 and l["family_plan"] == "later"
    ):
        keys += ["family"]

    if l["age"] == 65:
        keys += ["retire"]

    # Merge coinciding milestones rather than dropping one of them.
    keys = [
        key for key in dict.fromkeys(keys)
        if key not in l["done"]
    ]

    if keys:
        open_chapter(l, "major-life-event", keys)

    question(l)
    return l


# Original functions resolve these helpers from simulation.py internally.
# Installing them keeps old training/financial machinery using the new rules.
core.salary = salary
core.annual_cost = annual_cost
core.annual_finance = annual_finance
core.quote = quote
core.buy_terms = buy_terms
core.jobs = jobs
core.question = question
core.impact = impact