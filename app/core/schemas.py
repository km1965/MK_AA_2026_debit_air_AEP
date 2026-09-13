"""Moteur de calcul des 8 schémas de vidange — §5, §6, §7 de la note.

Chaque cas correspond à une configuration de vidange. Le débit d'air admis est
déterminé en appliquant la Formule MK_A.A (2026) côté amont et/ou aval,
avec gestion des points intermédiaires (CAS NORMAL / CAS PARTICULIER).

Convention de signe (§6.3) :
    - Q_PI < 0 → flux entrant compense le drainage → Q_PI = 0.
    - ΔH ≤ 0 → Q = 0.
"""

from dataclasses import dataclass, field
from typing import Optional

from . import mk_aa


@dataclass
class ResultatTroncon:
    """Résultat du calcul d'un tronçon via la Formule MK_A.A."""
    label: str
    q_m3h: float
    q_m3s: float
    dh: float
    l: float
    v: float
    re: float
    details: dict = field(default_factory=dict)


@dataclass
class ResultatSchema:
    """Résultat global d'un schéma de vidange."""
    cas: str
    q_ve_m3h: float = 0.0
    q_am_m3h: float = 0.0
    q_av_m3h: float = 0.0
    q_pi1_m3h: float = 0.0
    q_pi2_m3h: float = 0.0
    troncons: list = field(default_factory=list)      # [ResultatTroncon]
    journal: list = field(default_factory=list)        # [str] étapes pas-à-pas
    h1: Optional[float] = None
    h2: Optional[float] = None
    cas_pi1: Optional[str] = None
    cas_pi2: Optional[str] = None
    validite_ok: bool = True
    messages: list = field(default_factory=list)


def _al(dh, l, d, nu, label):
    """Wrapper safe : retourne (ResultatTroncon, message_validation_ou_None)."""
    res = mk_aa.formule_mk_aa(dh, l, d, nu, verification=False)
    tr = ResultatTroncon(
        label=label,
        q_m3h=mk_aa.q_m3h(res["q"]),
        q_m3s=res["q"],
        dh=dh, l=l, v=res["v"], re=res["re"], details=res,
    )
    return tr


class NoteMKAA:
    """Calculateur principal : détient les données projet et exécute un schéma."""

    def __init__(self, donnes_conduite, nu, depot3=3.0):
        self.dc = donnes_conduite
        self.nu = nu
        self.depot3 = depot3  # seuil de dépression admissible (mce)

    # ------------------------------------------------------------------
    # Charges H₁ / H₂ aux points intermédiaires (§6.1)
    # ------------------------------------------------------------------
    def h1(self, z_vi1, z_pi1, z_ve, a, b) -> float:
        """H₁ = Z_PI1 − (a/(a+b))·Z_Ve + 3a/(a+b) − (b/(a+b))·Z_Vi1"""
        ab = a + b
        return z_pi1 - (a / ab) * z_ve + (self.depot3 * a / ab) - (b / ab) * z_vi1

    def h2(self, z_ve, z_pi2, z_vi2, c, d) -> float:
        """H₂ = Z_PI2 − (d/(c+d))·Z_Ve + 3d/(c+d) − (c/(c+d))·Z_Vi2"""
        cd = c + d
        return z_pi2 - (d / cd) * z_ve + (self.depot3 * d / cd) - (c / cd) * z_vi2

    # ------------------------------------------------------------------
    # Côté amont (avec ou sans PI1)
    # ------------------------------------------------------------------
    def _cote_amont(self, z_vi1, z_pi1, z_ve, a, b, l1, with_pi):
        troncons, journal = [], []
        cond = z_ve - self.depot3 - z_vi1
        if cond <= 0:
            journal.append(f"[amont] Z_Ve−3−Z_Vi1 = {cond:.2f} ≤ 0 → pas d'aspiration (Q_am = 0)")
            return 0.0, 0.0, None, troncons, journal

        if not with_pi:
            tr = _al(cond, l1, self.dc.d, self.nu, "Q_am (direct)")
            troncons.append(tr)
            journal.append(f"[amont] CAS DIRECT : Q_am = MK_A.A(ΔH={cond:.2f}, L={l1}) = {tr.q_m3h:.1f} m³/h")
            return tr.q_m3h, 0.0, None, troncons, journal

        # avec PI1 : calculer H₁
        h1 = self.h1(z_vi1, z_pi1, z_ve, a, b)
        journal.append(f"[amont] H₁ = {h1:.2f} m")
        if h1 < self.depot3:
            tr = _al(cond, a + b, self.dc.d, self.nu, "Q_am (normal, a+b)")
            troncons.append(tr)
            journal.append(f"[amont] H₁={h1:.2f} < 3 → CAS NORMAL : Q_am = MK_A.A(ΔH={cond:.2f}, L=a+b={a+b}) = {tr.q_m3h:.1f} m³/h , Q_PI1=0")
            return tr.q_m3h, 0.0, "normal", troncons, journal

        # CAS PARTICULIER (poche d'air en PI1)
        tr_am = _al(z_ve - z_pi1, b, self.dc.d, self.nu, "Q_am (PI1→Ve, L=b)")
        tr_a = _al(z_pi1 - self.depot3 - z_vi1, a, self.dc.d, self.nu, "Q_A (Vi1→PI1, L=a)")
        troncons += [tr_am, tr_a]
        q_pi1 = max(0.0, tr_a.q_m3h - tr_am.q_m3h)
        journal.append(f"[amont] H₁={h1:.2f} ≥ 3 → CAS PARTICULIER (poche d'air en PI1)")
        journal.append(f"        Q_am = MK_A.A(Z_Ve−Z_PI1={z_ve - z_pi1:.2f}, L=b={b}) = {tr_am.q_m3h:.1f} m³/h")
        journal.append(f"        Q_A  = MK_A.A(Z_PI1−3−Z_Vi1={z_pi1 - self.depot3 - z_vi1:.2f}, L=a={a}) = {tr_a.q_m3h:.1f} m³/h")
        journal.append(f"        Q_PI1 = max(0 ; Q_A−Q_am) = {q_pi1:.1f} m³/h (air à admettre en PI1)")
        return tr_am.q_m3h, q_pi1, "particulier", troncons, journal

    # ------------------------------------------------------------------
    # Côté aval (avec ou sans PI2) — symétrique
    # ------------------------------------------------------------------
    def _cote_aval(self, z_ve, z_pi2, z_vi2, c, d, l2, with_pi):
        troncons, journal = [], []
        cond = z_ve - self.depot3 - z_vi2
        if cond <= 0:
            journal.append(f"[aval] Z_Ve−3−Z_Vi2 = {cond:.2f} ≤ 0 → pas d'aspiration (Q_av = 0)")
            return 0.0, 0.0, None, troncons, journal

        if not with_pi:
            tr = _al(cond, l2, self.dc.d, self.nu, "Q_av (direct)")
            troncons.append(tr)
            journal.append(f"[aval] CAS DIRECT : Q_av = MK_A.A(ΔH={cond:.2f}, L={l2}) = {tr.q_m3h:.1f} m³/h")
            return tr.q_m3h, 0.0, None, troncons, journal

        h2 = self.h2(z_ve, z_pi2, z_vi2, c, d)
        journal.append(f"[aval] H₂ = {h2:.2f} m")
        if h2 < self.depot3:
            tr = _al(cond, c + d, self.dc.d, self.nu, "Q_av (normal, c+d)")
            troncons.append(tr)
            journal.append(f"[aval] H₂={h2:.2f} < 3 → CAS NORMAL : Q_av = MK_A.A(ΔH={cond:.2f}, L=c+d={c + d}) = {tr.q_m3h:.1f} m³/h , Q_PI2=0")
            return tr.q_m3h, 0.0, "normal", troncons, journal

        tr_av = _al(z_ve - z_pi2, c, self.dc.d, self.nu, "Q_av (Ve→PI2, L=c)")
        tr_b = _al(z_pi2 - self.depot3 - z_vi2, d, self.dc.d, self.nu, "Q_B (PI2→Vi2, L=d)")
        troncons += [tr_av, tr_b]
        q_pi2 = max(0.0, tr_b.q_m3h - tr_av.q_m3h)
        journal.append(f"[aval] H₂={h2:.2f} ≥ 3 → CAS PARTICULIER (poche d'air en PI2)")
        journal.append(f"        Q_av = MK_A.A(Z_Ve−Z_PI2={z_ve - z_pi2:.2f}, L=c={c}) = {tr_av.q_m3h:.1f} m³/h")
        journal.append(f"        Q_B  = MK_A.A(Z_PI2−3−Z_Vi2={z_pi2 - self.depot3 - z_vi2:.2f}, L=d={d}) = {tr_b.q_m3h:.1f} m³/h")
        journal.append(f"        Q_PI2 = max(0 ; Q_B−Q_av) = {q_pi2:.1f} m³/h (air à admettre en PI2)")
        return tr_av.q_m3h, q_pi2, "particulier", troncons, journal

    # ------------------------------------------------------------------
    # Exécution par cas
    # ------------------------------------------------------------------
    def calculer(self, cas: str, alt: dict, avec_pi1: bool, avec_pi2: bool) -> ResultatSchema:
        """Exécute le schéma demandé.

        alt : dictionnaire avec clés z_vi1, z_pi1, z_ve, z_pi2, z_vi2, a, b, c, d, l1, l2.
        """
        z_vi1 = alt["z_vi1"]; z_pi1 = alt["z_pi1"]; z_ve = alt["z_ve"]
        z_pi2 = alt["z_pi2"]; z_vi2 = alt["z_vi2"]
        a = alt["a"]; b = alt["b"]; c = alt["c"]; d = alt["d"]
        l1 = alt["l1"]; l2 = alt["l2"]

        res = ResultatSchema(cas=cas)
        troncons, journal = [], []
        h1 = h2 = None
        cas_pi1 = cas_pi2 = None

        # Déterminer les côtés actifs selon le groupe du cas
        amont_only = cas in ("1A", "1B")
        aval_only = cas in ("2A", "2B")
        amont_et_aval = cas in ("3A", "3B", "4A", "4B")

        q_am = q_av = q_pi1 = q_pi2 = 0.0

        # Côté amont
        handle_am = amont_only or amont_et_aval
        if handle_am:
            use_pi_am = avec_pi1
            if cas == "4A":
                use_pi_am = True
            elif cas == "4B":
                use_pi_am = False
            q_am, q_pi1, cas_pi1, t, j = self._cote_amont(
                z_vi1, z_pi1, z_ve, a, b, l1, with_pi=use_pi_am)
            troncons += t; journal += j
            if cas_pi1:
                if cas_pi1 == "normal":
                    h1 = self.h1(z_vi1, z_pi1, z_ve, a, b)
                res.cas_pi1 = cas_pi1

        # Côté aval
        handle_av = aval_only or amont_et_aval
        if handle_av:
            use_pi_av = avec_pi2
            if cas == "4A":
                use_pi_av = False
            elif cas == "4B":
                use_pi_av = True
            q_av, q_pi2, cas_pi2, t, j = self._cote_aval(
                z_ve, z_pi2, z_vi2, c, d, l2, with_pi=use_pi_av)
            troncons += t; journal += j
            if cas_pi2:
                if cas_pi2 == "normal":
                    h2 = self.h2(z_ve, z_pi2, z_vi2, c, d)
                res.cas_pi2 = cas_pi2

        # Q_Ve = max(Q_am ; Q_av) pour les cas combinés, sinon le côté actif
        if isinstance(q_am, (int, float)) and isinstance(q_av, (int, float)):
            if amont_et_aval:
                q_ve = max(q_am, q_av)
                journal.append(f"Q_Ve = max(Q_am={q_am:.1f} ; Q_av={q_av:.1f}) = {q_ve:.1f} m³/h")
            elif amont_only:
                q_ve = q_am
                journal.append(f"Q_Ve (amont seul) = {q_ve:.1f} m³/h")
            else:  # aval only
                q_ve = q_av
                journal.append(f"Q_Ve (aval seul) = {q_ve:.1f} m³/h")
        else:
            q_ve = 0.0

        res.q_ve_m3h = q_ve
        res.q_am_m3h = q_am
        res.q_av_m3h = q_av
        res.q_pi1_m3h = q_pi1
        res.q_pi2_m3h = q_pi2
        res.troncons = troncons
        res.journal = journal
        res.h1 = h1
        res.h2 = h2
        return res
