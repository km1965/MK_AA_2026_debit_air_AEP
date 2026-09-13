"""Catalogue des organes — données alimentées par la base externe valve_database.json.

Point d'entrée unique pour le moteur : TRIFON, CEAI, PSA, DEPRESSION_NOMINALE.
Les données proviennent de app.data.valve_db (base JSON modifiable sans recompiler).
En l'absence de valve_database.json, le catalogue interne (méthode fixe du README §13)
est automatiquement utilisé.
"""

from .valve_db import (
    TRIFON,
    CEAI,
    PSA,
    DEPRESSION_NOMINALE,
    FOURNISSEURS,
    racharger as _racharger,
    source_base as _source_base,
)

# Expositions supplémentaires utiles
source_base = _source_base
racharger = _racharger
