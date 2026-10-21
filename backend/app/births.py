"""2024 FINAL resident birth counts: 50 states plus DC.

Source: Births: Final Data for 2024, Table 5, June 9, 2026.
https://www.cdc.gov/nchs/data/nvsr/nvsr75/nvsr75-02.pdf

Use counts as sampling weights, not birth/fertility rates.
"""
from .simulation import rng


BIRTHS = {
    "AL": 57934,  "AK": 8943,   "AZ": 78711,  "AR": 35395,
    "CA": 402075, "CO": 64268,  "CT": 34599,  "DE": 10550,
    "DC": 7616,   "FL": 224389, "GA": 126437, "HI": 14917,
    "ID": 23276,  "IL": 125731, "IN": 80257,  "IA": 36436,
    "KS": 33984,  "KY": 52913,  "LA": 53305,  "ME": 11601,
    "MD": 65797,  "MA": 68184,  "MI": 99525,  "MN": 62110,
    "MS": 33473,  "MO": 67998,  "MT": 11331,  "NE": 24785,
    "NV": 32381,  "NH": 11770,  "NJ": 101372, "NM": 21328,
    "NY": 205489, "NC": 122856, "ND": 9634,   "OH": 126795,
    "OK": 47962,  "OR": 38963,  "PA": 127299, "RI": 10009,
    "SC": 58768,  "SD": 11451,  "TN": 83833,  "TX": 390828,
    "UT": 46664,  "VT": 5023,   "VA": 94054,  "WA": 83118,
    "WV": 17022,  "WI": 59686,  "WY": 6089,
}

assert len(BIRTHS) == 51
assert sum(BIRTHS.values()) == 3628934


def random_home(seed):
    return rng(seed, "home-state-2024").choices(
        list(BIRTHS),
        weights=list(BIRTHS.values()),
        k=1,
    )[0]