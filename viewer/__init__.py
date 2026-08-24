"""Viewer helpers: canonical schema, normalization, visibility, framework naming."""

# Public surface (only these names should be imported by viewer.py):
#
#     from viewer.normalize   import canon, friendly_name, span_kind, to_messages
#     from viewer.canonical   import SPAN_KINDS, FIELD_ALIASES
#     from viewer.visibility  import is_span_visible, filter_visible_attrs
#
# Adding a new agent framework means adding ONE file under
# viewer/naming/<framework>.py - never edit canonical.py / normalize.py.
