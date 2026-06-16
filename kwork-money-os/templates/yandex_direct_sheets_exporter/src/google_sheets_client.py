"""Safe skeleton for writing report tables to Google Sheets."""

from __future__ import annotations

from dataclasses import dataclass, field

from config import AppConfig
from report_builder import ReportTable


@dataclass
class GoogleSheetsClient:
    config: AppConfig
    written_tables: list[ReportTable] = field(default_factory=list)

    def validate(self) -> None:
        if self.config.mock_mode:
            return
        if not self.config.google_service_account_json or self.config.google_service_account_json == "...":
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON is required for real API mode")
        if not self.config.spreadsheet_id or self.config.spreadsheet_id == "...":
            raise ValueError("SPREADSHEET_ID is required for real API mode")

    def write_tables(self, tables: list[ReportTable]) -> None:
        self.validate()
        if self.config.mock_mode:
            self.written_tables.extend(tables)
            for table in tables:
                print(f"[mock] would write {len(table.rows)} rows to sheet: {table.title}")
            return
        raise NotImplementedError("Implement Google Sheets API write/update calls here")
