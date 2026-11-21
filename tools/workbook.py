"""Extract the browsing workbook using only the Python standard library."""
import json
import posixpath
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def extract(workbook, destination):
    destination = Path(destination)
    with zipfile.ZipFile(workbook) as archive:
        strings = ["".join(node.itertext()) for node in
                   ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        links = {node.attrib["Id"]: posixpath.normpath("xl/" + node.attrib["Target"])
                 for node in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))}
        sheets = ET.fromstring(archive.read("xl/workbook.xml")).find(NS + "sheets")
        for sheet in sheets:
            name = sheet.attrib["name"].lower().replace(" ", "_")
            if name == "start_here":
                continue
            path = destination / ("policy_sheet.txt" if name == "policy" else name + ".jsonl")
            with archive.open(links[sheet.attrib[REL + "id"]]) as source, path.open("w", encoding="utf-8") as out:
                headers = None
                for _, row in ET.iterparse(source, events=("end",)):
                    if row.tag != NS + "row":
                        continue
                    cells = {}
                    for cell in row.findall(NS + "c"):
                        column = "".join(c for c in cell.attrib["r"] if c.isalpha())
                        value = cell.findtext(NS + "v")
                        if cell.attrib.get("t") == "s" and value is not None:
                            value = strings[int(value)]
                        elif cell.attrib.get("t") == "inlineStr":
                            value = "".join(cell.find(NS + "is").itertext())
                        cells[column] = value
                    if name == "policy":
                        out.write("\n".join(v for v in cells.values() if v is not None) + "\n")
                    elif headers is None:
                        headers = cells
                    elif any(v is not None for v in cells.values()):
                        out.write(json.dumps({key: cells.get(col) for col, key in headers.items() if key}, ensure_ascii=False) + "\n")
                    row.clear()
