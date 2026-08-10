"""Official Scanning 2023-09-01 FileExtensionsType values (single source of truth)."""

from __future__ import annotations

# https://learn.microsoft.com/en-us/rest/api/purview/scanningdataplane/scan-rulesets/get
# ?view=rest-purview-scanningdataplane-2023-09-01#fileextensionstype
FILE_EXTENSIONS_TYPE: frozenset[str] = frozenset(
    {
        "AVRO",
        "ORC",
        "PARQUET",
        "JSON",
        "TXT",
        "XML",
        "Documents",
        "CSV",
        "PSV",
        "SSV",
        "TSV",
        "GZ",
        "DOC",
        "DOCM",
        "DOCX",
        "DOT",
        "ODP",
        "ODS",
        "ODT",
        "PDF",
        "POT",
        "PPS",
        "PPSX",
        "PPT",
        "PPTM",
        "PPTX",
        "XLC",
        "XLS",
        "XLSB",
        "XLSM",
        "XLSX",
        "XLT",
    }
)

FILE_EXTENSIONS_TYPE_SORTED: tuple[str, ...] = tuple(sorted(FILE_EXTENSIONS_TYPE))
