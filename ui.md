J'ai construit un simulateur interactif complet. Ce qu'il fait :

**Entrées** : latitude, date, heure solaire, orientation de la façade (compas ou azimut libre), largeur/hauteur de la fenêtre, épaisseur du mur (embrasure), et un mur écran optionnel (distance D + hauteur Hm).

**Calculs** (formules du message précédent) :
- Position du soleil (altitude h, azimut As) à partir de la déclinaison terrestre
- Écart azimutal γ, angle d'incidence θ, angle de profil hp
- Ombre portée des tableaux latéraux et du linteau (dues à l'épaisseur du mur)
- Ligne d'ombre projetée par le mur écran extérieur
- % de surface vitrée réellement éclairée

**Visualisation** : vue en plan (masque latéral, direction du rayon) + coupe verticale (partie éclairée en ambre, partie à l'ombre en gris-bleu), qui se mettent à jour en temps réel.

Deux limites à connaître : le modèle ignore l'équation du temps et la réfraction atmosphérique (l'heure entrée est une heure solaire approximative, pas l'heure légale) — si tu veux, je peux affiner avec la longitude et le fuseau horaire pour convertir une vraie heure locale.
