from __future__ import annotations

from pathlib import Path

from hemis_formatter import format_word_file


BASE_DIR = Path(__file__).resolve().parent
SPECS = [
    ("jismoniy_yangi.docx", "jismoniy_uz"),
    ("jismoniy_yangi_rus.doc", "jismoniy_ru"),
    ("XORIJIY TILLAR YADA TESTLARI UMUMIY HEMIS (2).doc", "sequential"),
]


def main() -> None:
    for file_name, profile in SPECS:
        result = format_word_file(BASE_DIR / file_name, output_dir=BASE_DIR, profile=profile)
        print(
            f"{result.source_name}: {result.question_count} ta savol formatlandi -> "
            f"{result.docx_path.name} [{result.profile}/{result.encoding}]"
        )


if __name__ == "__main__":
    main()
