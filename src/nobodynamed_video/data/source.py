"""DataSource protocol — any data backend must satisfy this interface."""

from typing import Protocol

from nobodynamed_video.models import DataProvenance, NameRecord


class DataSource(Protocol):
    """Retrieve a NameRecord for a given name, sex, and reference year."""

    async def get_record(self, name: str, sex: str, year: int) -> NameRecord:
        """Return the full NameRecord for *name*/*sex* up to *year* (inclusive)."""
        ...

    async def latest_year(self) -> int:
        """Newest complete dataset year available from this source."""
        ...

    async def provenance(self) -> DataProvenance:
        """Machine-readable source and import provenance."""
        ...
