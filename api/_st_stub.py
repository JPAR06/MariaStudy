"""
Streamlit no-op stub.
MUST be imported before any src/ module to prevent @st.cache_resource crashes.
"""
import sys
import types


class _Noop:
    """Universal no-op: works as decorator, attribute, or callable."""
    def __call__(self, *a, **kw):
        # When used as @st.cache_resource → return the function unchanged
        if len(a) == 1 and callable(a[0]) and not kw:
            return a[0]
        return self
    def __getattr__(self, _):
        return self
    def __bool__(self):
        return False


_noop = _Noop()
_mod = types.ModuleType("streamlit")
_mod.cache_resource = _noop
_mod.cache_data = _noop
_mod.error = lambda *a, **kw: None
_mod.warning = lambda *a, **kw: None
_mod.info = lambda *a, **kw: None
_mod.stop = lambda: None
_mod.session_state = {}

sys.modules.setdefault("streamlit", _mod)
