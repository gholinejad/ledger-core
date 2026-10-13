"""The six-day event stream from the brief, in the order it is replayed."""
from .core import Event
from .money import to_minor

ACCOUNTS = {"ACC-001": "AED", "ACC-002": "BHD"}


def aed(x: str) -> int:
    return to_minor(x, "AED")


def bhd(x: str) -> int:
    return to_minor(x, "BHD")


STREAM = [
    Event("E1", 1, "CREDIT", "ACC-001", aed("1200.00"), value_day=1),
    Event("E2", 1, "DEBIT", "ACC-001", aed("950.00"), value_day=1),
    Event("E3", 2, "AUTHORIZATION", "ACC-001", aed("200.00"), value_day=2, auth_id="Auth-A"),
    Event("E4", 3, "CREDIT", "ACC-001", aed("400.00"), value_day=3),
    Event("E5", 4, "SETTLEMENT", "ACC-001", aed("185.00"), value_day=4, auth_id="Auth-A"),
    Event("E6", 4, "SETTLEMENT", "ACC-001", aed("180.00"), value_day=4, auth_id="Auth-Z"),
    Event("E7", 5, "DEBIT", "ACC-001", aed("620.00"), value_day=2),
    Event("E8", 5, "AUTHORIZATION", "ACC-001", aed("90.00"), value_day=5, auth_id="Auth-B"),
    Event("E9", 6, "REVERSAL", "ACC-001", value_day=2, target="E7"),
    Event("E10", 5, "CREDIT", "ACC-002", bhd("10.000"), value_day=5, parts=3),
]
