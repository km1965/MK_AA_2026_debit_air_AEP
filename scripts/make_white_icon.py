# -*- coding: utf-8 -*-
"""Régénère les icônes avec un fond blanc/clair pour différencier
MK_AA_2026 de l'app Calculateur_Débits_air.

Méthode : retirer le fond coloré sombre par transparence (basé sur la distance
à la couleur de fond), puis composer sur un fond blanc avec antialiasing.

Usage :  py -3.14 scripts/make_white_icon.py
"""
import os
import sys
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PNG = os.path.join(RACINE, "assets", "icon.png")
OUT_PNG = os.path.join(RACINE, "assets", "icon.png")
OUT_ICO = os.path.join(RACINE, "assets", "icon.ico")

# Couleur de fond détectée (bleu marine sombre), tolérance pour l'antialiasing
FOND = (3.0, 25.0, 57.1)
SEUIL = 200.0          # distance RGB max considérée comme "fond"


def distance(c1, c2):
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5


def luminosite(p):
    return 0.30 * p[0] + 0.59 * p[1] + 0.11 * p[2]


def fond_blanc(img: Image.Image) -> Image.Image:
    """Retire le fond sombre et compose sur un fond blanc.

    Critère principal = luminosité : les régions sombres (fond) deviennent
    transparentes de façon progressive (antialiasing), le dessin clair est
    préservé.
    """
    LUM_MAX = 170.0     # luminosité max considérée comme fond (progressif)
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y][:4]
            lum = luminosite((r, g, b))
            if lum < LUM_MAX:
                # alpha croissant avec la luminosité → fond progressivement transparent
                t = lum / LUM_MAX
                alpha = int(a * t)
                px[x, y] = (r, g, b, alpha)
    # composer sur fond blanc
    blanc = Image.new("RGBA", img.size, (255, 255, 255, 255))
    result = Image.alpha_composite(blanc, img).convert("RGB")
    # post-traitement : forcer les coins en blanc pur
    draw = ImageDraw.Draw(result)
    m = 12
    draw.rectangle([0, 0, m, m], fill=(255, 255, 255))
    draw.rectangle([w - m, 0, w, m], fill=(255, 255, 255))
    draw.rectangle([0, h - m, m, h], fill=(255, 255, 255))
    draw.rectangle([w - m, h - m, w, h], fill=(255, 255, 255))
    return result


def main():
    img = Image.open(SRC_PNG)
    new_img = fond_blanc(img)

    # Forcer un fond blanc pur sur les 4 coins (anti-artefact)
    new_img.save(OUT_PNG)
    # Générer le .ico multirésolution à partir du PNG haute résolution
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    new_img.save(OUT_ICO, format="ICO", sizes=sizes)
    print("Icônes régénérées à fond blanc :")
    print("  ", OUT_PNG)
    print("  ", OUT_ICO)

    # Vérif : couleur des coins doit être blanche
    check = Image.open(OUT_PNG)
    w, h = check.size
    coins = [check.getpixel((2, 2)), check.getpixel((w - 3, 2)),
             check.getpixel((2, h - 3)), check.getpixel((w - 3, h - 3))]
    print("Couleur des coins:", coins)


if __name__ == "__main__":
    main()
