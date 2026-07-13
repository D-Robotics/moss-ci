"""Tests for buggy.py — FAIL until subtract() is fixed.

Moss must make all these pass by fixing buggy.py's subtract() function.
Run with: python -m pytest test_buggy.py
"""
from buggy import add, subtract, multiply


def test_add():
    assert add(2, 3) == 5


def test_subtract():
    # This is the failing one: subtract(5, 3) returns 8 (bug) but should be 2.
    assert subtract(5, 3) == 2


def test_subtract_negative():
    assert subtract(0, 5) == -5


def test_multiply():
    assert multiply(4, 6) == 24
