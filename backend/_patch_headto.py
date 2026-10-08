"""Patch admin.py: replace the misspelled head-to-head ref in delete_team with the
real class name (A). Avoids me mis-typing look-alike spellings."""
import models.match as m
import api.v1.endpoints.admin as a

A = [n for n in dir(m) if n.startswith("HeadTo")][0]
B = [t for t in a.delete_team.__code__.co_names if t.startswith("HeadTo")][0]

path = "app/api/v1/endpoints/admin.py"
with open(path, "r", encoding="utf-8") as f:
    src = f.read()

n_before = src.count(B)
patched = src.replace(B, A)
n_after = patched.count(A)

with open(path, "w", encoding="utf-8") as f:
    f.write(patched)

print("class A =", repr(A))
print("delete_team bad ref B =", repr(B))
print("B occurrences in file before patch:", n_before)
print("A occurrences in file after patch:", n_after, "(was", src.count(A), "before)")
