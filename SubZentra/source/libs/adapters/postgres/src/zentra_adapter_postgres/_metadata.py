"""The one `MetaData` every table registers against.

Its own module so the schema can be split across files without either half
importing the other. Foreign keys reference tables by name, not by object, so
nothing else needs to cross the boundary.
"""

from __future__ import annotations

from sqlalchemy import MetaData

metadata = MetaData()
