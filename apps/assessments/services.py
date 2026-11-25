from decimal import Decimal, ROUND_HALF_UP


def weighted_percentage(grades) -> Decimal | None:
    grades = list(grades)
    if not grades:
        return None
    total_weight = sum((Decimal(str(grade.weight)) for grade in grades), Decimal("0"))
    if total_weight <= 0:
        return sum((grade.percentage for grade in grades), Decimal("0")) / Decimal(
            len(grades)
        )
    weighted_total = sum(
        (grade.percentage * Decimal(str(grade.weight)) for grade in grades),
        Decimal("0"),
    )
    return weighted_total / total_weight


def gpa_points(percentage) -> Decimal:
    value = Decimal(str(percentage))
    thresholds = (
        (Decimal("90"), Decimal("4.0")),
        (Decimal("85"), Decimal("3.7")),
        (Decimal("80"), Decimal("3.3")),
        (Decimal("75"), Decimal("3.0")),
        (Decimal("70"), Decimal("2.7")),
        (Decimal("65"), Decimal("2.3")),
        (Decimal("60"), Decimal("2.0")),
        (Decimal("50"), Decimal("1.0")),
    )
    for threshold, points in thresholds:
        if value >= threshold:
            return points
    return Decimal("0.0")


def calculate_gpa(grades) -> Decimal | None:
    percentage = weighted_percentage(grades)
    if percentage is None:
        return None
    return gpa_points(percentage).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_percentage(value) -> float | None:
    if value is None:
        return None
    return float(
        Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
