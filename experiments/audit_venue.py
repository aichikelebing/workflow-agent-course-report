"""Post hoc rescore for one TODS venue alias, holding original paths fixed."""
import study


TODS_NAMES = {
    "acm trans database syst",
    "acm transactions on database systems tods",
}


def main():
    rows = study.load("main-traces.json")
    cases = {p["case"]: p for p in study.load("cases.json")}
    updated = []
    changes = []
    for row in rows:
        paper = cases[row["case"]]
        fields = row["actions"]
        margin = study.margin(paper, fields)
        if "venue" in fields:
            left, right = study.evidence(paper, "venue")
            if {study.norm(left), study.norm(right)} <= TODS_NAMES:
                # Replace the original venue contribution with the existing
                # match contribution. Every other component stays identical.
                margin += .10 - study.contribution("venue", left, right)
        prediction = int(margin >= 0)
        corrected = dict(row, prediction=prediction, correct=prediction == row["gold"])
        updated.append(corrected)
        if prediction != row["prediction"]:
            changes.append(dict(case=row["case"], group=row["group"], gold=row["gold"],
                                actions=fields, before=row["prediction"], after=prediction))
    summary = {g: study.metrics([r for r in updated if r["group"] == g]) for g in "ABC"}
    study.save("venue-audit.json", dict(changed_predictions=changes, summary=summary))


if __name__ == "__main__":
    main()
