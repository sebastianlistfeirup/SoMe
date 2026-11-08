from pathlib import Path
import re

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "SoMe-mini-bibel-v1.0-source.txt"
TARGET = ROOT / "docs" / "SoMe-mini-bibel-v1.3.md"
PDF = ROOT / "docs" / "SoMe-mini-bibel-v1.3.pdf"


def revised_text() -> str:
    text = SOURCE.read_text(encoding="utf-8")
    text = text.replace("VERSION 1.0 · 5. NOVEMBER 2026 · DANSK", "VERSION 1.3 · 8. NOVEMBER 2026 · DANSK")
    text = text.replace("v1.0", "v1.3")
    old_step = "1) Vælg en godkendt emnekandidat. Saml faktakilder og lovligt materiale. Download til karantæne med\nstørrelses- og tidsgrænser. Valider URL, indholdstype, filsignatur og faktisk medieformat; blokér private\nnetværksadresser og cloud-metadata-endpoints."
    new_step = """1) Vælg en godkendt emnekandidat. Saml faktakilder og lovligt materiale. Produktionsvideoer skal ALTID som standard bygges på rigtige klip fra internettet med dokumenteret tilladelse. Download til karantæne med størrelses- og tidsgrænser. Valider URL, indholdstype, filsignatur og faktisk medieformat; blokér private netværksadresser og cloud-metadata-endpoints.

Tilladte standardkilder er:
· Stockklip med en konkret licens til kommerciel brug og bearbejdning.
· Public domain eller CC-materiale, når det konkrete værks vilkår tillader formålet og efterleves fuldt ud.
· Gameplay, når udgiverens aktuelle regler tillader videoformatet, redigering, monetisering og den konkrete musikbrug.
· Producentens pressemateriale, når licensen konkret tillader den planlagte brug.

Klip fra tilfældige streamere, seere eller repost-konti er ikke standardmateriale, selv om spiludgiveren tillader gameplayvideoer. Den enkelte klipskabers rettigheder skal også være afklaret. Brug helst egne optagelser, udgiverens officielle gameplayklip eller pressemateriale med eksplicit tilladelse. Gem kilde- og licensbevis for hvert enkelt klip før download og render."""
    if old_step not in text:
        raise RuntimeError("Kapitel 13-matcher ikke originalen")
    text = text.replace(old_step, new_step)
    old_rights = "Fodbold- og badmintonudsendelser, dokumentarfilm, streamerklip og pressevideoer må ikke behandles\nsom frit materiale. Egne gameplayoptagelser kræver kontrol af udgiverens regler og musik. Overvej\negen grafik, egne skærmoptagelser og kildebelagte forklaringer, hvor det er praktisk."
    new_rights = """Fodbold- og badmintonudsendelser, dokumentarfilm, streamerklip og pressevideoer må ikke behandles som frit materiale. Egne gameplayoptagelser kræver kontrol af udgiverens regler og musik.

Egne motion graphics, illustrationer, farvede baggrunde og PowerPoint-lignende slideshows er KUN en absolut fallback, når der efter en reel søgning ikke findes passende internetklip med dokumenteret licens. De må ikke være standarden for at spare tid. Et statisk slideshow uden animationer må ikke præsenteres som en færdig gameplayvideo. En ranking skal have et rigtigt, rettighedsryddet klip for hvert enkelt objekt; ellers standses produktionen eller ændres listen efter ny rettighedskontrol.

Overgange, titler, thumbnails og grafik skal understøtte det rigtige klipmateriale og dets historie – aldrig erstatte det. Kvalitet og engagement er mål, men visninger, likes og abonnementer kan ikke garanteres."""
    if old_rights not in text:
        raise RuntimeError("Kapitel 14-matcher ikke originalen")
    text = text.replace(old_rights, new_rights)
    platform_rules = """

PLATFORMFORMAT OG BILLEDKOMPOSITION v1.3
Vertikale gamingvideoer skal som hovedregel bruge dynamisk fuldskærms-gameplay med et dokumenteret fokuspunkt pr. klip. Et lille 16:9-udsnit med stor tom flade må ikke være eneste version. Tekst og undertekster skal ligge i platformens safe areas uden at skjule den vigtigste action.

Lav ved behov to vertikale varianter. ZOOM veksler mellem fuld originalbredde og mindst to tydelige fuldskærms-zooms pr. spil eller emne. Hver fase skal have en eksakt varighed og synkron tidskode, så den anden zoom ikke forsvinder eller forskyder lyden. SAFE viser hele spillets originale bredde på op til 1040 pixels med dæmpet, sløret udfyldning bagved. SAFE er obligatorisk når tekstkort, brugerflade eller vigtig action ellers ville blive beskåret. Begge varianter skal kontrolleres som faktiske billedserier, ikke kun som filterkode.

Lav separate redaktionelle varianter: TikTok med kortere og hurtigere kommentar, Instagram Reels med vertikal action og gem/del-CTA, og YouTube med 16:9, længere kommentar og eget landskabsthumbnail. Gem platform, mobiltilstand, antal zooms og CTA som features før publicering, så resultaterne kan sammenlignes korrekt.

Brug en naturlig og energisk stemme med dokumenteret modellicens og kvalitetsgodkendt udtale. Generisk eller kedelig oplæsning er ikke færdig produktionskvalitet. Kokoro kan køre lokalt på CPU med Apache-2.0-modellicens; hver stemme og hastighed skal evalueres. Ingen stemmeefterligning af en virkelig person uden tilladelse.
"""
    text = text.replace("\n7) Kontrollér ffprobe", platform_rules + "\n7) Kontrollér ffprobe", 1)
    return text


def markdown(text: str) -> str:
    pages = []
    for page in text.split("\f"):
        lines = page.strip().splitlines()
        if not lines:
            continue
        if lines[-1].startswith("SoMe-maskinen ·"):
            lines.pop()
        while lines and not lines[-1].strip():
            lines.pop()
        pages.append("\n".join(lines).strip())
    return "\n\n---\n\n".join(pages) + "\n"


def pdf(text: str) -> None:
    pdfmetrics.registerFont(TTFont("DejaVu", "C:/Windows/Fonts/arial.ttf"))
    pdfmetrics.registerFont(TTFont("DejaVuBold", "C:/Windows/Fonts/arialbd.ttf"))
    regular = ParagraphStyle("regular", fontName="DejaVu", fontSize=9.3, leading=13.4, spaceAfter=7, textColor="#18253a")
    heading = ParagraphStyle("heading", parent=regular, fontName="DejaVuBold", fontSize=17, leading=22, spaceBefore=3, spaceAfter=14, textColor="#12365b")
    cover = ParagraphStyle("cover", parent=heading, fontSize=28, leading=34, alignment=TA_CENTER, spaceBefore=65)
    code = ParagraphStyle("code", parent=regular, fontName="Courier", fontSize=7.8, leading=10.5, backColor="#f0f4f7")
    doc = SimpleDocTemplate(str(PDF), pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=18 * mm, bottomMargin=17 * mm, title="SoMe-maskinen — mini-bibel v1.3", author="SoMe-maskinen")
    story = []
    for page_number, page in enumerate(text.split("\f"), 1):
        lines = page.strip().splitlines()
        if lines and lines[-1].startswith("SoMe-maskinen ·"):
            lines.pop()
        first_content = True
        for line in lines:
            stripped = line.strip()
            if not stripped:
                story.append(Spacer(1, 4))
                continue
            escaped = stripped.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if stripped.startswith("http"):
                escaped = f'<link href="{stripped}" color="#175e8c">{stripped}</link>'
            if page_number == 1 and first_content:
                story.append(Paragraph(escaped, cover))
            elif first_content and re.match(r"^\d+\.", stripped):
                story.append(Paragraph(escaped, heading))
            elif stripped.isupper() and len(stripped) < 95:
                story.append(Paragraph(escaped, heading))
            elif re.match(r"^(sudo |python -m|ssh |apt-get |printf |http|#|ARCH=|ANTHROPIC|CLAUDE|DRY_RUN|PUBLISH|PAID|MONTHLY|MAX_JOB|APP_|DATABASE|MODEL_|WORKER|services:|web:|worker:|command:|user:|env_file:|ports:|volumes:|restart:|mem_limit:|cpus:|security_opt:|cap_drop:|logging:|options:|healthcheck:|test:|interval:|timeout:|retries:)", stripped):
                story.append(Paragraph(escaped, code))
            else:
                story.append(Paragraph(escaped, regular))
            first_content = False
        if page_number < len(text.split("\f")):
            story.append(PageBreak())

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("DejaVu", 7.5)
        canvas.setFillColor("#61758b")
        canvas.drawString(20 * mm, 9 * mm, "SoMe-maskinen · Bygge- og driftsinstruktion · v1.3")
        canvas.drawRightString(190 * mm, 9 * mm, str(document.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    content = revised_text()
    TARGET.write_text(markdown(content), encoding="utf-8")
    pdf(content)
    print(PDF)
