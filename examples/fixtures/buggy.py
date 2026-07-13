"""A deliberately buggy module for the end-to-end 'fix a bug' capability test.

Moss is asked to fix the bug so that test_buggy.py passes. The bug: add()
returns a+b but subtract() returns a+b instead of a-b. A real agent must
read this file, find subtract is wrong, fix it, and run the tests.
"""


def add(a, b):
    return a + b


def subtract(a, b):
    # BUG: returns a+b instead of a-b. Tests fail until this is fixed.
    return a + b


def multiply(a, b):
    return a * b
