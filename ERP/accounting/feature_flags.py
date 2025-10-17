def is_enabled(flag, settings):
    return settings.get("feature_flags", {}).get(flag, False)
