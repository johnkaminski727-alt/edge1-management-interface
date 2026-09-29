"""Tests for the canonical Edge1 application registry."""
from server.edge1_application_registry import load_registry, authorized_modules

def test_registry_is_fail_closed_and_unique():
    data=load_registry()
    assert data["navigation_grants_authorization"] is False
    ids=[m["id"] for m in data["modules"]]
    assert len(ids)==len(set(ids))
    assert all(m["required_scopes"] for m in data["modules"])

def test_contacts_scope_reveals_both_contacts_surfaces_only():
    modules=authorized_modules({"contacts:read"})
    assert [m["id"] for m in modules] == ["phone-directory","contacts"]

def test_menu_visibility_does_not_imply_authorization():
    data=load_registry()
    assert data["navigation_grants_authorization"] is False
    assert authorized_modules(set()) == []

def test_multi_scope_menu_is_sorted_and_bounded():
    modules=authorized_modules({"contacts:read","library:search","edge1.status.detail.read"})
    assert [m["id"] for m in modules] == ["library","phone-directory","contacts","operations-center"]
