"""Application-credential regression tests for NIO Open Telematics."""

import ast
from pathlib import Path


def test_authorize_request_uses_provider_supported_scope_set() -> None:
    """The authorization URL requests every scope exposed by this NIO app."""
    root = Path(__file__).parents[1] / "custom_components" / "nio_telematics"
    const_tree = ast.parse((root / "const.py").read_text(encoding="utf-8"))
    scopes_assignment = next(
        (
            node
            for node in ast.walk(const_tree)
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "OAUTH_SCOPES"
        ),
        None,
    )

    assert scopes_assignment is not None
    assert isinstance(scopes_assignment.value, (ast.List, ast.Tuple))
    assert [scope.value for scope in scopes_assignment.value.elts] == [
        "vehicle:read",
        "vehicle:dynamics:read",
        "vehicle:location:read",
        "vehicle:energy:read",
        "vehicle:body:read",
        "vehicle:cabin:read",
        "vehicle:powertrain:read",
        "vehicle:diagnostics:read",
        "vehicle:adas:read",
        "vehicle:nomi:read",
        "aftersales:read",
    ]

    application_source = (root / "application_credentials.py").read_text(
        encoding="utf-8"
    )
    assert '"scope": " ".join(OAUTH_SCOPES)' in application_source
