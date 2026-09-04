"""Test-support package for the CBDB-Desktop application.

The package holds *infrastructure only* — configuration, staging of the
shipped archive, and the process/HTTP driver for the real ``cbdb.exe``.
It deliberately contains no re-implementation of any application query:
the code under test is the shipped Go binary and the SQLite database that
ships beside it, and the tests drive that binary directly.
"""
