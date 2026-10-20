"""Compatibility names for the shared calcium imaging API (no scientific imports)."""

from functools import wraps

# Keep this boundary explicit: acquisition identifiers such as ONIX, UCLA and
# the Miniscope directory layout are not analysis option names.
LEGACY_OPTIONS = {
    "miniscope_filenames": "calcium_imaging_filenames",
    "compute_miniscope_phase": "compute_calcium_imaging_phase",
    "filter_miniscope_data": "filter_calcium_imaging_data",
    "compute_miniscope_spectrogram": "compute_calcium_imaging_spectrogram",
}


def accept_legacy_keywords(**aliases):
    """Accept old kwargs while preserving the canonical callable's signature.

    For a dataclass, decorate after @dataclass to wrap its generated initializer.
    Reject duplicate old/new spellings instead of silently choosing a value.
    """
    def decorate(target):
        if isinstance(target, type):
            target.__init__ = decorate(target.__init__)
            return target

        @wraps(target)
        def call(*args, **kwargs):
            for old, new in aliases.items():
                if old in kwargs:
                    if new in kwargs:
                        raise TypeError(f"Use only one of {old!r} and {new!r}.")
                    kwargs[new] = kwargs.pop(old)
            return target(*args, **kwargs)

        return call
    return decorate


def alias_attribute(canonical):
    """Keep historical attribute reads and writes attached to one value."""
    return property(
        lambda self: getattr(self, canonical),
        lambda self, value: setattr(self, canonical, value),
        doc=f"Compatibility alias for {canonical}.",
    )


def options_for_keys(options, allowed_keys):
    """Translate option spellings for a canonical or historical consumer.

    CSV/GUI callers can retain their saved columns. If both spellings exist,
    the canonical spelling wins, independent of CSV column order.
    """
    result = dict(options)
    for old, new in LEGACY_OPTIONS.items():
        if new in allowed_keys:
            if old in result:
                result.setdefault(new, result.pop(old))
        elif old in allowed_keys and new in result:
            result[old] = result.pop(new)
    return result
