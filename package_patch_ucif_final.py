import zipfile
from pathlib import Path

src = Path(r"C:\Users\DELL\OneDrive\Documents\SRM\Churn_Research\UCIF_Report.docx")
out = Path(r"C:\Users\DELL\OneDrive\Documents\SRM\Churn_Research\UCIF_Report_Audited_Final_v3.docx")

with zipfile.ZipFile(src, "r") as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == "word/numbering.xml":
            text = data.decode("utf-8")
            text = text.replace('w:lvlText w:val="\uf0b7"', 'w:lvlText w:val="-"')
            text = text.replace(
                'w:rFonts w:ascii="Symbol" w:hAnsi="Symbol" w:hint="default"',
                'w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:hint="default"',
            )
            data = text.encode("utf-8")
        elif item.filename == "word/document.xml":
            text = data.decode("utf-8")
            text = text.replace("• What does this data set appear to signify?", "- What does this data set appear to signify?")
            text = text.replace("• Which business terms were identified?", "- Which business terms were identified?")
            text = text.replace("• Is the input schema credible enough?", "- Is the input schema credible enough?")
            text = text.replace("• What prediction path was chosen?", "- What prediction path was chosen?")
            text = text.replace("• Was fallback routing applied?", "- Was fallback routing applied?")
            text = text.replace("• How does the external business context influence the interpretation?", "- How does the external business context influence the interpretation?")
            text = text.replace("• If the result is fit for decision-making.", "- If the result is fit for decision-making.")
            text = text.replace("� What does this data set appear to signify?", "- What does this data set appear to signify?")
            text = text.replace("� Which business terms were identified?", "- Which business terms were identified?")
            text = text.replace("� Is the input schema credible enough?", "- Is the input schema credible enough?")
            text = text.replace("� What prediction path was chosen?", "- What prediction path was chosen?")
            text = text.replace("� Was fallback routing applied?", "- Was fallback routing applied?")
            text = text.replace("� How does the external business context influence the interpretation?", "- How does the external business context influence the interpretation?")
            text = text.replace("� If the result is fit for decision-making.", "- If the result is fit for decision-making.")
            text = text.replace(
                "Central control by CLI is helpful, though not necessarily",
                "Central control by CLI is helpful, but it keeps orchestration centralized.",
            )
            text = text.replace(
                "It allows for defining new domains, which need vocabularies and models",
                "New domains can be added, but they require vocabulary and model updates.",
            )
            text = text.replace(
                "UCIF guarantees the process from proof to decision",
                "UCIF preserves evidence from schema-level proof to decision output.",
            )
            text = text.replace(
                "It is adaptive, though the predictability of transfer is inconsistent",
                "The framework adapts structurally, but predictive transfer is inconsistent.",
            )
            data = text.encode("utf-8")
        zout.writestr(item, data)

print(out)
