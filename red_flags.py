
def detect_red_flags(answers):
    """
    Rule-based warning detection.
    This does not diagnose a medical condition.
    """

    alerts = []

    symptom = answers.get("symptom", "").strip()
    severity = answers.get("severity", "").strip()
    associated = answers.get("associated", "").strip()
    temperature = answers.get("temperature", "").strip()

    # Headache-related warning signs
    if symptom == "Headache":
        if associated in ["Blurred vision", "Vomiting"]:
            alerts.append(
                "Headache reported with " + associated.lower()
                + ". Prompt clinical review is recommended."
            )

        if severity == "Severe":
            alerts.append(
                "Severe headache reported. Clinical review is recommended."
            )

    # Fever-related warning signs
    if symptom == "Fever":
        if temperature == "Above 102°F":
            alerts.append(
                "Patient reports fever above 102°F. "
                "Prompt clinical review is recommended."
            )

    # Stomach pain-related warning signs
    if symptom == "Stomach pain" and severity == "Severe":
        alerts.append(
            "Severe stomach pain reported. "
            "Prompt clinical review is recommended."
        )

    # General severity warning
    if severity == "Severe" and not alerts:
        alerts.append(
            "Patient has reported severe symptoms. "
            "Doctor review is recommended."
        )

    if alerts:
        return {
            "level": "Needs Review",
            "details": " ".join(alerts)
        }

    return {
        "level": "Normal",
        "details": "No predefined red flags detected from the answers provided."
    }
