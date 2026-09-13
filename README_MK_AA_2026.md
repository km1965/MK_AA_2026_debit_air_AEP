# NOTE TECHNIQUE MK_A.A 2026 — Cahier des charges
## Débits d'air admis · Conduites AEP · Casse franche

---

**Version du document :** V1.0 (spécification de la nouvelle application)
**Référentiel :** « Exemple de calcul — Note technique MK_A.A 2026 (Avril 2026) »
**Statut :** __Confidentiel — Usage opérationnel interne__

> Ce document est le **cahier des charges** destiné à construire une **nouvelle application
> autonome et complète** pour le dimensionnement des débits d'air admis en conduites AEP.
> Il formalise, à partir de la note technique de référence, le socle de calcul **commun et
> non modifiable**, ainsi que les **seules données applicatives** qu'un projeteur peut
> ajuster d'un projet à l'autre.
>
> **Principe fondamental :** les **bases de calcul restent identiques** quel que soit le
> projet. Seules les **données projet** changent (maître d'ouvrage / références, diamètre
> de la canalisation principale, températures, altimétrie).

---

## Sommaire

1. [Objet et domaine d'application](#1-objet-et-domaine-dapplication)
2. [Portée de la nouvelle application](#2-portée-de-la-nouvelle-application)
3. [Socle de calcul FIXE (non modifiable)](#3-socle-de-calcul-fixe-non-modifiable)
4. [Données projet variables (seules modifiables)](#4-données-projet-variables-seules-modifiables)
5. [Schémas de vidange (8 cas)](#5-schémas-de-vidange-8-cas)
6. [Méthode de calcul détaillée](#6-méthode-de-calcul-détaillée)
7. [Logigramme de calcul](#7-logigramme-de-calcul)
8. [Dimensionnement des organes](#8-dimensionnement-des-organes)
9. [Nouveau paragraphe — Débit de remplissage & purgeur](#9-nouveau-paragraphe--débit-de-remplissage--purgeur)
10. [Extension future — Dépressions admissibles étendues](#10-extension-future--dépressions-admissibles-étendues)
11. [Livrables de l'application](#11-livrables-de-lapplication)
12. [Références bibliographiques](#12-références-bibliographiques)
13. [Annexes catalogue (organes)](#13-annexes-catalogue-organes)
14. [Roadmap — Évolutions prévues](#14-roadmap--évolutions-prévues)

---

## 1. Objet et domaine d'application

La note technique a pour objet de **décrire et de justifier la méthode de calcul des débits
d'air admis** dans une conduite d'eau potable (AEP) **lors d'une casse franche**, aux fins de
dimensionner les **ventouses**, les **clapets d'entrée d'air** et les **purgeurs**.

- **Domaine :** hydraulique AEP sous pression — conduites gravitaires.
- **Méthode :** Darcy-Weisbach → Colebrook-White → **Formule explicite MK_A.A (2026)**.
- **Schémas :** 8 variantes couvrant toutes les configurations de vidange.
- **Point haut Ve** (ventouse) et **points intermédiaires PI1 / PI2**.
- **Organes :** Ventouse TRIFON (FIRM) · Clapet CEAI (Ramus) · Purgeur PSA (Ramus). Purgeur et Clapet NSH/SNH**.

**Point de contrôle :** la dépression maximale admissible au point haut Ve est limitée à
**3 m de colonne d'eau (mCE)** (NF EN 805). Au-delà : risques de cavitation, d'entrée d'air
incontrôlée et d'arrachement des joints — inacceptables.

---

## 2. Portée de la nouvelle application

La nouvelle application doit :
1. Saisir le **profil en long** et les **caractéristiques de la conduite** (variables projet).
2. Appliquer le **socle de calcul identique** aux 8 schémas de vidange.
3. **Dimensionner automatiquement** les organes (ventouse, clapet, purgeur) sur chaque point.
4. **Prendre en compte la vanne de vidange** (limitation du débit) et le **débit de remplissage**.
5. Générer un **rapport de synthèse** défendable (calcul pas-à-pas, justifications, annexes
   catalogue, note de méthodologie).

La nouvelle application est **indépendante** de tout autre outil existant : elle reprend ce
socle de calcul comme **référentiel unique et figé**.

---

## 3. Socle de calcul FIXE (non modifiable)

Ces valeurs et formules constituent le **cœur de calcul** ; elles sont **identiques pour tous
les projets** et ne se modifient pas dans l'application.

### 3.1 Paramètres physiques fixes

| Paramètre | Symbole | Valeur | Unité |
|---|---|---|---|
| Accélération de la pesanteur | `g` | 9,81 | m/s² |
| Rugosité absolue (fonte ductile) | `k` | 0,0005 | m |
| Viscosité cinématique (référence 15 °C) | `ν` | 1,02 × 10⁻⁶ | m²/s |
| Seuil de dépression admissible | — | 3 | mCE (NF EN 805) |

> La viscosité **ν** et la rugosité **k** sont des paramètres du socle. La température de
> référence du socle est **15 °C** ; une **correction** est possible via les données projet
> (voir §4.3) mais la valeur nominale reste fixe.

### 3.2 Équations fondamentales

**Équation de Darcy-Weisbach (1857) — ① :**

```
ΔH = λ · (L / D) · (V² / 2g)
```

- `ΔH` : perte de charge (m) · `λ` : coefficient de frottement de Darcy
- `L` : longueur du tronçon (m) · `D` : diamètre intérieur (m)
- `V` : vitesse moyenne = Q/S (m/s) · `g` = 9,81 m/s²

**Coefficient de frottement — Colebrook-White (1939) — ② :**

```
1/√λ = −2 · log₁₀ [ k/(3,71·D)  +  2,51/(Re·√λ) ]
```

- `Re = V·D/ν = 4Q/(π·D·ν)` (nombre de Reynolds)
- Validité : **Re > 4000** · **k/D ∈ [10⁻⁶ ; 10⁻²]**

### 3.3 Formule explicite en débit — MK_A.A (2026) — ⑤

Le système ①–② (implicite en λ) est résolu explicitement en Q :

```
Q = −(π/2) · D^(5/2) · √(2g·ΔH/L) · log₁₀[ k/(3,71·D)  +  2,51·ν / (D^(3/2)·√(2g·ΔH/L)) ]
```

Propriétés :
- **Q > 0** car `log₁₀(arg) < 0` en régime turbulent (arg < 1).
- Validité : **Re > 4000** et **k/D ∈ [10⁻⁶ ; 10⁻²]** (à vérifier après calcul).
- **Précision ± 3 %** par rapport à la méthode itérative complète.
- **Directement applicable sans itération** — adaptée aux feuilles de calcul.

> La nouvelle application utilisera **unique** cette formule explicite (pas d'itération
> interne), avec les mêmes conditions de validité.

---

## 4. Données projet variables (seules modifiables)

Ce sont les **seules** données qu'un utilisateur peut modifier (via l'interface de la
nouvelle application) d'un projet à l'autre. Le **socle de calcul (§3) ne change pas**.

### 4.1 Identification du projet / maître d'ouvrage

| Champ | Exemple (trame) | Variable ? |
|---|---|---|
| Maître d'ouvrage | XXXX | Oui |
| Projet / marché | XXXXXXXXXXXXXXXXXXXXX · Marché N° XXXXXX | Oui |
| Référence document / indice | — | Oui |
| Branches étudiées | BR1, BR2, BR3 | Oui |
| Auteur / vérificateur / approbateur | MK_A.A + contrôleurs | Oui |

### 4.2 Caractéristiques de la canalisation principale

| Champ | Exemple (trame) | Variable ? |
|---|---|---|
| Diamètre nominal `DN` | 1400 / 1600 / 2000 (mm) | **Oui** |
| Diamètre intérieur `D` | 1,40 / 1,60 / 2,00 (m) | **Oui** (déduit du DN) |
| Section `S = π/4·D²` | 1,5394 / 2,0106 / 3,1416 (m²) | Calculée |
| Rapport `k/D` | 0,357 / 0,313 / 0,250 × 10⁻³ | Calculé |
| Débit de remplissage à 2 m/s | voir §9 | Calculé |

**Déduction automatique :** à partir du `DN` saisi, l'application calcule `D`, `S`, `k/D`
et le débit de remplissage.

### 4.3 Température de l'eau

| Champ | Valeur | Variable ? |
|---|---|---|
| Température de référence | 15 °C (nominale) | **Oui** (ajustable) |
| Viscosité cinématique `ν` | 1,02 × 10⁻⁶ m²/s @ 15 °C | Corrigée si T ≠ 15 °C |

> La température est une donnée projet : si elle diffère de 15 °C, l'application doit
> **corriger ν** selon les tables de viscosité de l'eau et l'utiliser dans la formule, tout
> en gardant la valeur nominale comme défaut.

### 4.4 Altimétrie / profil en long

| Variable | Description |
|---|---|
| `Z_Ve` | Altitude du point haut (ventouse), m NGF/NGM |
| `Z_Vi1` | Altitude du point bas amont, m |
| `Z_Vi2` | Altitude du point bas aval, m |
| `Z_PI1` | Altitude du point intermédiaire amont, m |
| `Z_PI2` | Altitude du point intermédiaire aval, m |
| `a` | Vi1 → PI1 (m) |
| `b` | PI1 → Ve (m) |
| `c` | Ve → PI2 (m) |
| `d` | PI2 → Vi2 (m) |
| `L₁` | Vi1 → Ve (m) — si pas de point intermédiaire |
| `L₂` | Ve → Vi2 (m) — si pas de point intermédiaire |

Selon le schéma retenu (§5), seules les distances pertinentes sont saisies.

---

## 5. Schémas de vidange (8 cas)

Classés en 4 groupes, couvrant toutes les configurations de vidange.

| Cas | Groupe | Schéma | Distances | Q_Ve |
|---|---|---|---|---|
| 1A | A — Amont seul | Vi1 ─(L₁)─ Ve | L₁ | SJ(ΔH_am, L₁) |
| 1B | A — Amont seul | Vi1 ─(a)─ PI1 ─(b)─ Ve | a, b | Selon H₁ |
| 2A | B — Aval seul | Ve ─(L₂)─ Vi2 | L₂ | SJ(ΔH_av, L₂) |
| 2B | B — Aval seul | Ve ─(c)─ PI2 ─(d)─ Vi2 | c, d | Selon H₂ |
| 3A | C — Amont + Aval | Vi1 ─(L₁)─ Ve ─(L₂)─ Vi2 | L₁, L₂ | max(Q_am ; Q_av) |
| 3B | C — Amont + Aval | Vi1─a─PI1─b─Ve─c─PI2─d─Vi2 | a, b, c, d | max(Q_am ; Q_av) |
| 4A | D — Asymétrique | Vi1─(a)─PI1─(b)─Ve─(L₂)─Vi2 | a, b, L₂ | max(Q_am ; Q_av) |
| 4B | D — Asymétrique | Vi1─(L₁)─Ve─(c)─PI2─(d)─Vi2 | L₁, c, d | max(Q_am ; Q_av) |

Notation : `SJ(ΔH, L)` = application de la Formule MK_A.A (2026) avec `ΔH` et `L`,
et les données `D`, `k`, `ν` de la conduite considérée.

---

## 6. Méthode de calcul détaillée

### 6.1 Charges H₁ et H₂ aux points intermédiaires

Pour les schémas à points intermédiaires, on compare la cote du point à la ligne
piézométrique tracée avec **−3 m en Ve** :

```
H₁ = Z_PI1  − (a/(a+b))·Z_Ve  + 3a/(a+b)  − (b/(a+b))·Z_Vi1
H₂ = Z_PI2  − (d/(c+d))·Z_Ve  + 3d/(c+d)  − (c/(c+d))·Z_Vi2
```

Règle :
- **H < 3 m** → point intermédiaire sous la ligne piézo → **CAS NORMAL**
- **H ≥ 3 m** → point intermédiaire au-dessus → **CAS PARTICULIER** (poche d'air en PI)

### 6.2 Détail par cas

**Cas 1A — Vidange amont seule, sans PI :**
```
Si Z_Ve − 3 − Z_Vi1 ≤ 0  →  Q_Ve = 0
Si Z_Ve − 3 − Z_Vi1 > 0  →  Q_Ve = MK_A.A(ΔH = Z_Ve−3−Z_Vi1, L = L₁)
```

**Cas 1B — Vidange amont seule, avec PI1 :**
```
1. Calculer H₁ (cf. §6.1)
2. Condition globale : Z_Ve−3−Z_Vi1 ≤ 0  →  Q_am = Q_PI1 = 0
3. Si H₁ < 3 (CAS NORMAL) :
     Q_am = MK_A.A(Z_Ve−3−Z_Vi1, a+b) ;  Q_PI1 = 0
4. Si H₁ ≥ 3 (CAS PARTICULIER) :
     Q_am = MK_A.A(Z_Ve − Z_PI1, b)      ← flux PI1 → Ve
     Q_A  = MK_A.A(Z_PI1−3−Z_Vi1, a)     ← flux Vi1 → PI1
     Q_PI1 = Q_A − Q_am                      ← air admis à PI1
5. Q_Ve = Q_am  (côté amont seul)
```

**Cas 2A — Vidange aval seule, sans PI :** *symétrique du cas 1A* (avec Z_Vi2 et L₂).

**Cas 2B — Vidange aval seule, avec PI2 :** *symétrique du cas 1B* (côté aval) :
```
H₂ < 3 : Q_av = MK_A.A(Z_Ve−3−Z_Vi2, c+d) ;  Q_PI2 = 0
H₂ ≥ 3 : Q_av = MK_A.A(Z_Ve − Z_PI2, c) ;  Q_B = MK_A.A(Z_PI2−3−Z_Vi2, d)
         Q_PI2 = Q_B − Q_av
```

**Cas 3A — Vidanges amont + aval, sans PI :**
```
Q_am = MK_A.A(Z_Ve−3−Z_Vi1, L₁)   (si condition > 0)
Q_av = MK_A.A(Z_Ve−3−Z_Vi2, L₂)   (si condition > 0)
Q_Ve = max(Q_am ; Q_av)
```

**Cas 3B — Vidanges amont + aval, avec PI1 et PI2 (schéma général) :**
```
Côté amont (si Z_Ve−3−Z_Vi1 > 0) :
   H₁ < 3 : Q_am = MK_A.A(...a+b) ; Q_PI1 = 0
   H₁ ≥ 3 : Q_am = MK_A.A(Z_Ve−Z_PI1, b) ; Q_A = MK_A.A(Z_PI1−3−Z_Vi1, a)
            Q_PI1 = Q_A − Q_am
Côté aval  (si Z_Ve−3−Z_Vi2 > 0) :
   H₂ < 3 : Q_av = MK_A.A(...c+d) ; Q_PI2 = 0
   H₂ ≥ 3 : Q_av = MK_A.A(Z_Ve−Z_PI2, c) ; Q_B = MK_A.A(Z_PI2−3−Z_Vi2, d)
            Q_PI2 = Q_B − Q_av
Q_Ve = max(Q_am ; Q_av)
```

**Cas 4A — Vidange, PI1, ventouse, vidange (PI côté amont seulement) :**
```
Côté amont (avec PI1) : identique au cas 1B
Côté aval  (direct)   : Q_av = MK_A.A(Z_Ve−3−Z_Vi2, L₂) ; Q_PI2 = 0
Q_Ve = max(Q_am ; Q_av)
```

**Cas 4B — Vidange, ventouse, PI2, vidange (PI côté aval seulement) :**
```
Côté amont (direct)   : Q_am = MK_A.A(Z_Ve−3−Z_Vi1, L₁) ; Q_PI1 = 0
Côté aval  (avec PI2) : identique au cas 2B
Q_Ve = max(Q_am ; Q_av)
```

### 6.3 Convention de signe

- **Q_PI < 0** : le flux entrant compense le drainage → **aucun air à admettre en PI**
  → `Q_PI = 0` par convention.
- **ΔH ≤ 0** : pas d'écoulement gravitaire dans le sens considéré → **Q = 0**.

---

## 7. Logigramme de calcul

Le logigramme s'applique **à chaque côté (amont et aval) indépendamment** :

```
Début — Saisir : Z_Vi, Z_PI (si applicable), Z_Ve, L, D, k, ν
  │
  ├─ ÉTAPE 1 : [si PI présent] H = Z_PI − a/(a+b)·Z_Ve + 3a/(a+b) − b/(a+b)·Z_Vi
  │
  ├─ ÉTAPE 2 : Vérifier  Z_Ve − 3 − Z_Vi > 0 ?
  │      ├─ NON  → Q = 0 — pas d'aspiration d'air (ventouse de dégazage uniquement)
  │      └─ OUI  → Écoulement gravitaire possible, continuer
  │
  ├─ ÉTAPE 3 : [si PI absent]  CAS DIRECT
  │      Q = MK_A.A(ΔH = Z_Ve−3−Z_Vi, L = L₁ ou L₂)  ·  Q_PI = 0
  │
  ├─ ÉTAPE 3' : [si PI présent] Vérifier  H < 3 m ?
  │      ├─ OUI (H < 3)  → CAS NORMAL :
  │      │     Q = MK_A.A(ΔH = Z_Ve−3−Z_Vi, L = a+b ou c+d)  ·  Q_PI = 0
  │      └─ NON (H ≥ 3)  → CAS PARTICULIER (poche d'air en PI) :
  │            Q_am/av = MK_A.A(Z_Ve−Z_PI, b ou c)
  │            Q_A/B   = MK_A.A(Z_PI−3−Z_Vi, a ou d)
  │            Q_PI    = max(0 ; Q_A/B − Q_am/av)   ← air à admettre en PI
  │
  ├─ ÉTAPE 4 (cas 3A/3B/4A/4B) : Q_Ve = max(Q_am ; Q_av)
  │
  └─ RÉSULTAT : Q_Ve → dimensionnement de la ventouse Ve
```

---

## 8. Dimensionnement des organes

### 8.1 Ventouse (admission d'air grand débit)

- La ventouse Ve doit couvrir **Q_Ve** (débit retenu au point haut).
- Capacité choisie **≥ Q_Ve** avec une **marge de sécurité de 20 à 30 %** sur les débits
  dimensionnants (recommandation de la note).
- Capacités de référence : **ventouse TRIFON (FIRM)** — voir Annexe B.

### 8.2 Clapet d'entrée d'air (admission)

- Associé à la ventouse ; capacité à la **dépression admissible de −3 mCE**.
- Gamme CEAI : DN 80 à DN 500 · PFA 10/16/25 bars.
- **Plusieurs clapets en parallèle** sont nécessaires pour les grandes conduites
  (le DN du clapet désigne l'organe, **non** la conduite).
- Capacités de référence : **clapet CEAI (Ramus)** — voir Annexe A.

### 8.3 Purgeur / dégazage

- **Dégazage permanent** sous pression (petit orifice).
- **Nouveau paragraphe remplissage** : voir §9 (purgeur PSA, capacité d'évacuation de l'air
  lors du remplissage).

### 8.4 Vanne de vidange

- Le débit de la conduite peut être **limité par la vanne de vidange** (prise en compte du
  débit effectivement évacuable). Le débit retenu à la ventouse est alors :
  `min(débit tronçon (Formule MK_A.A) ; débit limité par la vanne)`.

### 8.5 Taux d'utilisation / sélection

- **Taux d'utilisation = Besoin / Capacité installée (%).**
- Sélection des organes avec un **plafond d'utilisation** (défaut 90 %) et une **marge
  directe de +15 %** sur le débit dimensionnant → sur-capacité totale ≈ **+28 %**
  (1,15/0,90), alignée sur les défauts de la note MK_A.A 2026.
- Si le DN d'une ventouse n'existe pas tel quel au catalogue : prendre le **DN supérieur
  disponible** (sécuritaire), ou **plusieurs organes en parallèle**.

---

## 9. Nouveau paragraphe — Débit de remplissage & purgeur

> **Paragraphe dédié "REMPlissage"** à intégrer dans la nouvelle application (nouvelle
> fonctionnalité, non présente dans l'app existante).

### 9.1 Débit de remplissage de la conduite

Le débit d'air à évacuer lors du **remplissage** de la conduite est calculé à la vitesse
d'eau de remplissage recommandée :

```
Q_remplissage = V_eau × (π/4) × D_conduite² × 3600    [m³/h]
```

Avec **V_eau = 2 m/s** (vitesse de remplissage recommandée) :

| Branche | D (m) | Q_remplissage (m³/h) |
|---|---|---|
| Ex. BR1 (DN 1400) | 1,40 | 11 084 |
| Ex. BR2 (DN 1600) | 1,60 | 14 476 |
| Ex. BR3 (DN 2000) | 2,00 | 22 619 |

### 9.2 Purgeur PSA (Ramus) — évacuation de l'air au remplissage

- **Fonction :** évacuation **contrôlée** de l'air lors du remplissage (et non une
  admission) : purgeur **sonique / de remplissage**.
- Vitesse max de sortie d'air : **200 m/s** · Vitesse de remplissage recommandée : **2 m/s**.
- Gamme : DN 80 à DN 250 · PFA 10/16 bars · Certification ACS.
- Capacités de référence : **purgeur PSA (Ramus)** — voir Annexe C.
- Nombre requis = `Q_remplissage / capacité unitaire PSA` (arrondi supérieur), ex. :
  - BR1 : 4 × PSA 250 · BR2 : 5 × PSA 250 · BR3 : 7 × PSA 250

**Interface :** la nouvelle app doit, pour chaque conduite, **afficher un paragraphe
"Remplissage"** qui présente Q_remplissage et recommande le purgeur PSA associé.

---

## 10. Extension future — Dépressions admissibles étendues

Les annexes catalogue fournissent des **capacités à plusieurs dépressions** :
**−2 / −3 / −4 mCE** (ventouse TRIFON et clapet CEAI). Cette capacité de données prépare
une extension possible de l'application à des **dépressions admissibles étendues**.

> **État : optionnel / au cas où.** La version nominale reste **câblée à −3 mCE**. La
> structure des données (`capacites` par dépression) doit être prévue dès la conception
> pour permettre, sans refonte, le choix d'une autre dépression admissible à l'avenir.

---

## 11. Livrables de l'application

1. **Saisie projet** : identification (§4.1), conduite (§4.2), température (§4.3), profil
   en long (§4.4), schéma (§5).
2. **Calcul** : journal pas-à-pas (charge H, gradient, Re, log₁₀(arg), Q par tronçon,
   Q_Ve retenu), conforme au logigramme (§7).
3. **Dimensionnement** : ventouse + clapet + purgeur sur chaque point, avec marge directe
   +15 % et plafond d'utilisation 90 % (sur-capacité totale ≈ +28 %).
4. **Paragraphe remplissage** (§9) : Q_remplissage et purgeur PSA.
5. **Rapport de synthèse** : méthodologie, hypothèses, calculs, justifications, annexes
   catalogue, note de méthodologie / contrôle.
6. **Vérification finale** : validité Re > 4000, k/D ∈ [10⁻⁶ ; 10⁻²], autres contrôles.

---

## 12. Références bibliographiques

- Darcy, H. (1857) — *Recherches expérimentales relatives au mouvement de l'eau dans les
  tuyaux.* Mallet-Bachelier, Paris.
- Weisbach, J. (1845) — *Lehrbuch der Ingenieur- und Maschinen-Mechanik.* Vieweg, Braunschweig.
- Colebrook, C.F. & White, C.M. (1939) — *Experiments with fluid friction in roughened
  pipes.* Proc. Royal Society, London.
- MK_A.A (2026) — *Formule explicite en débit pour le calcul des débits d'air admis en
  casse franche* (dérivée de Darcy-Weisbach et Colebrook-White).
- NF EN 805 (2000) — *Alimentation en eau. Exigences pour les systèmes à l'extérieur des
  bâtiments.*
- NF EN 1074-4 — *Robinetterie pour l'alimentation en eau — Ventouses.*
- ASTEE / FNCCR (2019) — *Guide technique pour la gestion des réseaux d'eau potable.*

---

## 13. Annexes catalogue (organes)

### Annexe A — Clapet d'entrée d'air CEAI (Ramus Industrie, France)

- **Fonction :** admission d'air à grand débit lors de la vidange (normale ou accidentelle).
- **Gamme :** DN 80 à DN 500 · PFA 10/16/25 bars · Certification ACS.
- **Ouverture :** automatique dès dépression de 0,50 à 1,00 mce.
- **Débit nominal assuré à ΔP = −3 mce.**

**Formule de débit :** `Q_CEAI = V_air(ΔP) × S_CEAI`, avec `S_CEAI = π/4 × D_CEAI²`.

Vitesses d'air (laboratoire, Notice CEAI-01-0419-A) :

| Dépression | V_air |
|---|---|
| ΔP = −4 mce | 110 m/s |
| ΔP = −3 mce | **105 m/s** (référence de dimensionnement) |
| ΔP = −2 mce | 90 m/s |

**Débits CEAI (m³/h) :**

| DN CEAI | Section (m²) | Q @ −4 mce | Q @ −3 mce | Q @ −2 mce | Classe |
|---|---|---|---|---|---|
| 80 | 0,0050 | 1 901 | 1 800 | 1 598 | PFA 10/16/25 |
| 100 | 0,0079 | 3 100 | 2 902 | 2 498 | PFA 10/16/25 |
| 150 | 0,0177 | 6 901 | 6 300 | 5 699 | PFA 10/16/25 |
| 200 | 0,0314 | 12 398 | 11 304 | 10 102 | PFA 10/16/25 |
| 250 | 0,0491 | 19 400 | 17 600 | 15 800 | PFA 10/16/25 |
| 300 | 0,0707 | 27 900 | 26 701 | 22 799 | PFA 10/16/25 |
| 350 | 0,0962 | 38 002 | 34 600 | 31 100 | PFA 10/16/25 |
| 400 | 0,1256 | 49 702 | 47 401 | 40 601 | PFA 10/16/25 |
| 500 | 0,1963 | 77 699 | 70 600 | 63 500 | PFA 10/16/25 |

### Annexe B — Ventouse triple fonction TRIFON (FIRM, partenaire Ramus)

- Fonction 1 : dégazage permanent sous pression (petit orifice — tuyère bronze).
- Fonction 2 : admission d'air grand débit à la vidange (flotteur guidé).
- Fonction 3 : échappement grand débit de l'air au remplissage.
- Gamme : DN 40 à DN 300 · PN 10 à 25 bars · Certification ACS.

**Débits TRIFON — grand orifice, admission/vidange (m³/h)** (catalogue FIRM V1/2025, p. 15) :

| DN TRIFON (mm) | Q @ −4 mce | Q @ −3 mce | Q @ −2 mce |
|---|---|---|---|
| 50 | 800 | 750 | 650 |
| 65 | 1 400 | 1 200 | 1 050 |
| 80 | 2 300 | 2 100 | 1 850 |
| 100 | 4 200 | 3 800 | 3 400 |
| 150 | 9 000 | 8 000 | 7 000 |
| 200 | 18 000 | 17 000 | 15 000 |
| 250 | 28 000 | 26 000 | 23 000 |
| 300 | 42 000 | 38 000 | 34 000 |

> Pour DN > 300 : confirmer avec FIRM ou utiliser plusieurs TRIFON DN 300 en parallèle.

### Annexe C — Purgeur Sonic PSA (Ramus Industrie, France)

- **Fonction :** évacuation **contrôlée** de l'air lors du **remplissage**.
- Vitesse max de sortie d'air : **200 m/s** · Vitesse de remplissage recommandée : **2 m/s**.
- Gamme : DN 80 à DN 250 · PFA 10/16 bars · Certification ACS.

**Débits de remplissage et PSA requis (à V_eau = 2 m/s)** :

| Branche | DN | Q_remplissage (m³/h) | Modèle PSA recommandé | Nb PSA 250 (3 500 m³/h) | Nb PSA 200 (2 200 m³/h) |
|---|---|---|---|---|---|
| BR1 | DN 1400 | 11 084 | 4 × PSA 250 | 4 | 6 |
| BR2 | DN 1600 | 14 476 | 5 × PSA 250 | 5 | 7 |
| BR3 | DN 2000 | 22 619 | 7 × PSA 250 | 7 | 11 |

---

## 14. Roadmap — Évolutions prévues

> Les évolutions sont portées par des **numéros de version applicative** (V0x). La version
> **actuelle** est la **V05** (saisie manuelle + **import Excel**, calcul, dimensionnement,
> vérifications, flambement, perte de charge, champ PN, exports docx/xlsx/croquis,
> nomenclature).
> La version **V05** est **livrée** — voir §15.2.

### 14.1 V05 — Import d'un fichier Excel de données projet

**Statut : ✅ livré (Septembre 2026) — fonctionnalité §15.2**

**Objectif :** à partir d'un simple fichier Excel rempli par le projeteur, l'application
**importe toutes les données projet**, applique le socle de calcul fixe (§3–§7) et génère
**automatiquement** l'ensemble des livrables (rapport, exports docx/xlsx, croquis PNG,
nomenclature) — sans ressaisie manuelle dans l'interface.

**Faisabilité : ✅** toutes les données (§4) existent déjà dans le modèle (`EtatApplication`)
et la bibliothèque **openpyxl** (déjà utilisée pour les exports) permet la lecture. L'import
alimente le même pipeline que la saisie manuelle : `calculer()` → `générer_rapport()` →
exports. Aucune évolution du socle de calcul n'est requise.

**Comportement livré (depuis l'application) :**
1. Remplir le fichier Excel (`Donnees_projet.xlsx`) selon le modèle ci-dessous.
2. Depuis l'application : bouton **« Importer Excel »** (ou glisser-déposer) → sélection du fichier.
3. L'application **pré-remplit** tous les champs, lance le calcul et affiche la conformité.
4. Les boutons d'export produisent les livrables directement depuis les données importées.
5. Un **contrôle de validité** signale les valeurs manquantes/dépassements de plage.

### 14.2 Exemple de données à saisir dans le fichier Excel (modèle V05)

Le fichier est organisé en **plusieurs blocs** (une ligne par paramètre, colonnes
`Paramètre | Valeur | Unité | Description`). La 1ʳᵉ ligne de chaque bloc est une **en-tête
de section** (gras). Deux feuilles : **« Données projet »** et **« Organes client »**.

**Feuille « Données projet » :**

| Paramètre | Valeur (exemple) | Unité | Description |
|---|---|---|---|
| *— 1. Identification —* | | | |
| Maître d'ouvrage | XXXX | — | §4.1 |
| Projet / marché | XXXXXXXXXXXXXXXX · Marché N° XXXXXX | — | §4.1 |
| Référence document | NC_mk_aa_2026-BR2-TR1 | — | §4.1 |
| Branches étudiées | BR1, BR2, BR3 | — | §4.1 |
| *— 2. Conduite —* | | | |
| Diamètre nominal DN | 1600 | mm | §4.2 |
| Température de l'eau | 15 | °C | §4.3 (ν corrigé si ≠ 15) |
| Pression nominale PN | 16 | bar | flambement / nomenclature |
| *— 3. Profil en long —* | | | |
| Schéma de vidange | 3A | — | §5 (1A…4B) |
| Z_Vi1 | 100,00 | m | point bas amont |
| Z_PI1 | (vide si absent) | m | point intermédiaire amont |
| Z_Ve | 87,68 | m | point haut (ventouse) |
| Z_PI2 | (vide si absent) | m | point intermédiaire aval |
| Z_Vi2 | 4,86 | m | point bas aval |
| L₁ (Vi1→Ve) | 73,55 | m | si schéma sans PI |
| L₂ (Ve→Vi2) | 361,82 | m | si schéma sans PI |
| a / b / c / d | selon schéma à PI | m | §4.4 |
| *— 4. Casse franche —* | | | |
| H_z dénivelé géométrique | auto (Z_Ve − point bas) | mCE | casse franche / Q_eau |
| DN vanne de sectionnement | 1600 | mm | 0 si non renseigné |

> **H_z auto (onglet 8 · Cumul des débits, mode Brèche)** : la valeur par défaut (10,0 m)
> est un simple placeholder — l'application la remplace automatiquement par
> `Z_Ve − point bas du profil` (dénivelé max vers la rupture, côté(s) actif(s) du schéma).
> Le champ reste **modifiable** : toute valeur saisie (≠ 10) est conservée pour le
> calcul (ex. rupture non située au point bas).

**Feuille « Organes client » (une ligne par organe proposé) :**

| Type | DN (mm) | Nombre | Position | Fournisseur |
|---|---|---|---|---|
| trifon | 250 | 2 | amont | TRIFON |
| ceai | 400 | 1 | amont | SNH |
| ceai | 400 | 1 | aval | SNH |
| psa | 250 | 1 | amont | SNH |
| vanne | 1600 | 1 | — | — |

> **Type** : `trifon` (ventouse) · `ceai` (clapet admission) · `psa` (purgeur remplissage) ·
> `vanne` (vanne de sectionnement, renseigne `dn_vanne_sectionnement` sans entrer dans les
> organes d'air). **Position** : `amont` / `aval` / vide.

**Gabarit vierge fourni avec l'application :** un fichier `Donnees_projet_vide.xlsx` est
distribué à côté de l'EXE afin que le projeteur parte d'un modèle propre.

### 14.3 Backlog cumulé (au-delà de V05)

- **V05 b** — Écran d'aperçu des données importées avant calcul (tableau récapitulatif éditable).
- **V05 c** — Miroir croquis multi-tronçons : extension de l'« épure » au profil complet en long (chaîne de tronçons) — profil + points seuls, organes vus dans l'onglet Vérification et le récap Fs ; harmonisation commentaires/titres + tests de non-présence d'organes. *Orientation à trancher demain : épure stricte vs annotations par point Ve/PI (clapets dédiés PI1/PI2).*
- **V06** — Exports **groupés en un seul dossier** (rapport + docx + xlsx + PNG + nomenclature) à partir de l'import.
- **V07** — Mémorisation du fichier Excel utilisé (chemin) pour re-import rapide « dernière version ».

---

## Rappel — Règle de conception fondamentale

> **Les bases de calcul (§3–§7) sont FIXES et communes à tous les projets.**
> Seules les **données projet (§4)** — maître d'ouvrage / références, DN de la
> canalisation principale, températures, altimétrie — sont modifiables par l'utilisateur.
> Tout nouveau projet réutilise le **même socle de calcul**, garantissant une méthodologie
> unique, vérifiable et conforme à la note technique MK_A.A 2026.

---

## 15. Historique des versions livrées

### 15.1 V02 — Profil complet (Ve/PI) · CAS PARTICULIER · purgeur sonique SNH

**Date :** Septembre 2026
**Origine :** portage de MK_ALLOUANE_2026 (V02 identique, seuls les noms branding diffèrent).

#### 15.1.1 Fonctionnalités livrées

| # | Fonctionnalité | Détail |
|---|---|---|
| 1 | **Profil complet** | Calcul par tronçon (Vi1→PI1→Ve→PI2→Ve→Vi2) avec gestion indépendante amont/aval |
| 2 | **CAS PARTICULIER Ve/PI** | Détecte les points intermédiaires au-dessus de la ligne piézométrique (H ≥ 3 m) |
| 3 | **Décomposition Ve/PI** | Ventouse ajoutée = TRIFON ; autre organe = clapet SNH ; DN par défaut : TRIFON DN300 / SNH DN250 |
| 4 | **Sélection optimisée** | L'option couvrant le manque avec le **MOINS** d'unités (égalité → TRIFON) |
| 5 | **Purgeur sonique NSH/SNH** | DN 1500 au catalogue (capacité sonique ~10 m³/h) — un à l'amont de **chaque** point haut (Ve et PI) |
| 6 | **Marge Fs** | Fs = ×1,15 ÷ 0,90 ≈ 1,2778 (marge directe +15 %, plafond 90 %) |
| 7 | **Vitesse d'air** | 105 m/s au clapet CEAI (capacité catalogue à −3 mce) **ET** 40 m/s dans la conduite/vanne (anti-blocage sonique) — les deux coexistent |
| 8 | **Maquette DOCX** | `BR2_TR2_ve_pi_V02.docx/xlsx/txt` — 16 organes, 12 verdicts, CAS PARTICULIER PI |
| 9 | **Récap Fs par point haut** | Exports Profil complet (txt/docx/xlsx) : implantation réelle (ventouses→Ve, clapets→PI), Fs = capacité/besoin, avis ≥ 1,20 CONFORME · [1,00 ; 1,20) ADMISSIBLE non recommandé + suggestion d'ajout · < 1,00 NON CONFORME ; purgeurs (dégazage) exclus du Fs |
| 10 | **Organes dédiés par point PI** | Onglet Vérification : positions **PI1/PI2** (chaque PI vérifié contre ses propres organes, même base données) ; Profil complet : colonnes « Clap. PI1 » / « Clap. PI2 » ; repli automatique sur l'historique si non saisi |
| 11 | **Croquis épuré** | Le croquis PNG du tronçon unique ne représente plus les organes installés (profil + points seuls) |

#### 15.1.2 Règle de décomposition Ve/PI (CAS PARTICULIER)

```
Pour chaque point intermédiaire PI où H ≥ 3 m :
  1. Ventouse ajoutée → TRIFON (double fonction admission + évacuation)
  2. Tout autre organe → clapet d'admission SNH
  3. DN par défaut : TRIFON DN300 · SNH DN250
  4. Sélection = option couvrant le besoin Q_PI avec le MOINS d'unités
  5. Égalité → ventouse TRIFON
```

#### 15.1.3 Vitesse d'air — deux seuils complémentaires

| Seuil | Source | Application |
|---|---|---|
| **105 m/s** | Notice CEAI-01-0419-A | Capacité du clapet CEAI à dépression = −3 mCE (col du clapet) |
| **40 m/s** | AWWA M51 | Conduite, vanne de vidange, collecteur — limite anti-blocage sonique |

> Les deux seuils sont **complémentaires**, pas contradictoires. Le clapet CEAI assure 105 m/s à sa section propre ; la vanne/collecteur ne doit jamais dépasser 40 m/s.

#### 15.1.4 Purgeur sonique NSH (SNH)

- **Emplacement :** à l'amont de chaque point haut (Ve et PI)
- **Capacité catalogue :** ~10 m³/h (goulot ≈ 200 m/s)
- **Modèle physique :** détendeur sonique orifice convergent, ancré sur le catalogue NSH
- **Formule :** `Q_fill = q_capacity × (P_fill / P_svc)` (P_svc = 10 bar abs)

#### 15.1.5 Tests & validation

| Scénario | Résultat |
|---|---|
| 37 tests moteur (schemas.py + profil_complet.py) | ✅ OK |
| 91 tests profil complet (scénarios Ve + PI + organes dédiés) | ✅ OK |
| Tests Vérification des organes (dont clapets dédiés PI1/PI2) | ✅ OK |
| Build V02 (`MK_AA_2026_V02.spec`) | ✅ Compilé → `dist_MK_AA_2026_V02\MK_AA_2026_V02.exe` + `valve_database.json` |
| Démarrage V02 | ✅ Titre « MK_A.A 2026 — Débits d'air admis en conduites AEP » |

#### 15.1.8 Organes dédiés par point PI (PI1/PI2) · croquis épuré


| Fonctionnalité | Détail |
|---|---|
| Onglet Vérification — position PI1/PI2 | Menu « Pos » étendu : Amont / Aval / **PI1** / **PI2** — chaque PI est vérifié contre ses propres organes (même base de données `capacite_organe` / `valve_database.json`), via `decomposition_pi` (porté du tronçon unique MK AL_A.A) |
| Profil complet — clapets dédiés | Nouvelles colonnes « Clap. PI1 » / « Clap. PI2 » de la proposition client (clés `clapet_pi1` / `clapet_pi2`) |
| Règle de priorité | Si un clapet dédié est saisi → le PI est vérifié contre son propre organe ; sinon repli sur la règle historique (excédent ventouses + clapets partagés au prorata) — rétro-compatibilité totale des notes existantes |
| Verdicts | « CAS PARTICULIER — PI1/PI2 (débit d'air à admettre) » : « N × clapet DN… (dédié PI1/PI2) », capacité propre, complément TRIFON/SNH si manque |
| Récap Fs | Si organes dédiés → Ve = ventouses + clapet (Ve), chaque PI = son propre clapet, « Groupe (Ve + PI) » = Σ capacités / Σ besoins ; sinon prorata historique |
| Croquis | Le croquis PNG du tronçon unique ne dessine plus les organes installés (profil en long + points seuls) — les organes sont vus dans l'onglet Vérification et le récapitulatif par point haut |

#### 15.1.9 Refonte du rapport de synthèse — vérification SANS majoration


| Fonctionnalité | Détail |
|---|---|
| §5 TXT / DOCX / XLSX | Le « Dimensionnement des organes (théorique de référence) » est supprimé : le rapport s'ouvre sur le remplissage, l'implantation (Amont / Aval / PI1 / PI2), le plan XYZ (X/Z réels des PI), puis la vérification |
| Tableau de vérification 10 colonnes | `Repére \| Demande (m³/h) \| Catégorie \| DN (mm) \| Nbr \| Implantation \| Fournisseur \| Capacité (m³/h) \| Fs \| Verdict` — produit par `tableau_verification_organes()` |
| Fs sans majoration | `Fs = Capacité / Demande` (Q brut) ; les majorations ×1,15 / ÷0,90 restent réservées aux CAS PARTICULIER PI |
| Besoin réel du tronçon | Bilan DOCX/XLSX = Σ capacités / (Q_Ve + Q_PI1 + Q_PI2) ; verdict « COUVERT / INSUFFISANT » si Fs ≥ 1,0 + vanne conforme + vitesse ≤ 40 m/s |
| Verdicts | « Conforme / Non conforme » (purgeurs : demande/capacité/fs = `—`) |
| 4.3 DOCX/XLSX | « Proposition du client et dimensionnement retenu » → « Dimensionnement corrigé — groupe retenu » (Tableau 1 supprimé) |
| Débits cumulés (XLSX) | Lignes refondues : Q MK_A.A requise, Q_PI1/Q_PI2, « Besoin réel du tronçon — sans majoration », « Fs du groupe d'admission (Capacité / Besoin réel) » |

Tests : moteur 37/37, profil complet 91 OK / 0 FAIL, vérification OK — régression `tableau_verification_organes` ajoutée.

#### 15.1.6 Fichiers livrés

```
MK_AA_2026/
├── app/core/profil_complet.py          ← moteur V02 (profil complet + CAS PARTICULIER)
├── app/core/dimensionnement.py         ← purgeur sonique SNH + Fs 1,2778
├── tests/test_profil_complet.py        ← 91 tests profil complet
├── MK_AA_2026_V02.spec                ← spec PyInstaller V02
├── dist_MK_AA_2026_V02/               ← EXE V02 livré
│   ├── MK_AA_2026_V02.exe
│   └── valve_database.json
└── docs/maquettes_V02/                 ← maquette de contrôle
    ├── BR2_TR2_ve_pi_V02.docx
    ├── BR2_TR2_ve_pi_V02.xlsx
    └── BR2_TR2_ve_pi_V02.txt
```


### 15.2 V05 — Import d'un fichier Excel de données projet

**Date :** Septembre 2026

| Fonctionnalité | Détail |
|---|---|
| Gabarits livrés | `Donnees_projet_vide.xlsx` (vierge) et `Donnees_projet_Exemple.xlsx` (exemple  · LGV , schéma 3A, DN 1600) — à la racine du projet **et** recopiés à côté de l'EXE dist_MK_AA_2026_V02 |
| Feuille « Données projet » | Une ligne par paramètre (`Paramètre \| Valeur \| Unité \| Description`), 4 blocs : 1. Identification · 2. Conduite · 3. Profil en long · 4. Casse franche — cellules jaunes à saisir, décimale virgule (100,00), `H_z` « auto » ou explicite, schéma 1A…4B |
| Feuille « Organes client » | Une ligne par organe (`Type \| DN (mm) \| Nombre \| Position \| Fournisseur`) — type `trifon`/`ceai`/`psa`/`vanne` ; la ligne `vanne` renseigne `dn_vanne_sectionnement` sans entrer dans les organes d'air |
| Lecteur `app/utils/excel_import.py` | normalisation sans accents des libellés, rapprochement par préfixe (tolère « Diamètre nominal DN (mm) », décimale virgule, « auto »…), retour dict au format `EtatApplication.to_dict()` ; contrôle de validité : schéma manquant/inconnu, distances absentes (selon `DISTANCES_PAR_CAS`), Z_Ve/profil manquant, DN d'organes invalides |
| Intégration application | Menu **Fichier → « Importer Excel… »** (MK_A.A) : sélection du `.xlsx` → `EtatApplication.appliquer_excel()` (mutation en place) → pré-remplissage de tous les champs → déclenchement du calcul → messagebox des avertissements éventuels |
| Pipeline inchangé | Le socle de calcul (§3–§7) est identique à la saisie manuelle : `calculer()` → `générer_rapport()` → exports docx/xlsx/txt/PNG |
| Tests | `tests/test_excel_import.py` — **32 OK / 0 FAIL** (lecture de l'exemple livré, décimale française, H_z auto, organes dont vanne, contrôle de validité, intégration `appliquer_excel` + calcul) |

---

### 15.3 V05 b — Analyse piézométrique (fenêtre de tracé dédiée)

**Date :** Septembre 2026

| Fonctionnalité | Détail |
|---|---|
| Moteur générique | `app/utils/trace_piezometrique.py` : `tracer_profil(etat, chemin_png=None, dep=3.0, taille=(15,7))` → `(fig, infos)` + `charger_depuis_json()` + CLI `python app\utils\trace_piezometrique.py <projet.json> <sortie.png>` |
| Les 8 schémas | Profil en long + ligne piézométrique pour 1A…4B selon `ORDRE_POINTS` (portée en abcisses : seul point haut ou distances a/b/c/d/l1/l2) |
| Piézométrie | Amont : droite `(Z_Ve−DEP → Z_Vi1)` ; aval : `(Z_Ve−DEP → Z_Vi2)` ; H₁ au PI1 et H₂ au PI2 = cote profil − ligne ; critère **H ≥ 3 m → organe requis** (rouge) sinon CAS NORMAL (vert) |
| Fenêtre « 11 · Analyse piézométrique » | Saisie manuelle (identification, DN, température, schéma, altimétrie, distances), boutons « Calculer & tracer (.png) » · « Ouvrir le tracé » · « Reprendre les données » ; aperçu PNG intégré ; résultats Q_Ve/Q_PI1/Q_PI2 + H₁/H₂ + verdicts ; journal Allouane complet |
| `analysis_oued.py` (racine) | Relié au moteur générique — exemple Oued Nfifikh : `python analysis_oued.py` → `profile_oued_nfifikh.png` (Q_Ve = 127 094,4 m³/h ; H₁ = +14,72 m → CAS PARTICULIER) |
| Tests | `tests/test_trace_piezometrique.py` — **32 OK / 0 FAIL** (PNG sur les 8 schémas, verdicts H1/H2 selon la position des PI, chargement JSON) — suites existantes inchangées (moteur 37/37 · profil_complet 91 OK/0 FAIL · import Excel 32/0 · vérification OK) |

---

*Fin de la spécification — MK_A.A · Septembre 2026 (trame) — Usage opérationnel interne.*
