import jsonlogic

def evaluate_rules(rules, data):
    for rule in sorted(rules, key=lambda r: r.get("priority", 100)):
        if rule.get("enabled", True):
            if jsonlogic.jsonLogic(rule["if"], data):
                return rule["then"]
    return None
