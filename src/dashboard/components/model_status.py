"""Model status and warning banner component."""

from __future__ import annotations

import streamlit as st


def render_model_status(model_mode: str = "iid") -> None:
    """Render model mode indicator with appropriate warning."""
    if model_mode == "iid":
        st.markdown(
            '<div class="model-banner model-iid">'
            '<strong>Modell: IID (Independent Draws)</strong><br>'
            'Jeder Pull ist eine unabhaengige Ziehung gegen die aktuelle Drop-Rate-Tabelle. '
            'Nichts ist mathematisch "faellig". Vergangene Pulls beeinflussen zukuenftige '
            'Ergebnisse NICHT. Beobachtete Abweichungen von publizierten Odds sind '
            'statistisches Rauschen, solange der chi²-Test nicht signifikant ist.'
            '</div>',
            unsafe_allow_html=True,
        )
    elif model_mode == "pool":
        st.markdown(
            '<div class="model-banner model-pool">'
            '<strong>Modell: Finite Pool (Inventory-Sensitive)</strong><br>'
            'Es wurde ein signifikanter Pool-/Inventory-Effekt erkannt. '
            'Odds kooennen sich real verschieben, wenn bestimmte Karten aus '
            'dem Pool gezogen wurden. Restocks aendern die Odds ebenfalls. '
            'Dieses Modell ist INDIKATIV — Annahmen koennen nicht vollstaendig '
            'verifiziert werden.'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.info(
            "Modell: Auto-Detection — System prueft automatisch ob IID "
            "oder Pool-basierte Mechanik vorliegt."
        )
