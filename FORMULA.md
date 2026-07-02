# Formule pour les rayons lumineux à travers une fenêtre

Voici une décomposition complète du problème, avec les rebords de mur (embrasure) et une éventuelle obstruction extérieure.

## Données d'entrée

**Position du soleil** (calculée à partir de la latitude, date, heure) :
- **h** = hauteur solaire (angle au-dessus de l'horizon)
- **As** = azimut solaire (mesuré depuis le nord)

**Orientation du mur :**
- **An** = azimut de la normale à la façade (perpendiculaire au mur, vers l'extérieur)

**Fenêtre et mur :**
- W, H = largeur et hauteur de la fenêtre
- e = épaisseur du mur au droit de la fenêtre (profondeur de l'embrasure)

**Obstruction extérieure (optionnelle) :**
- D = distance horizontale fenêtre → obstruction
- Hm = hauteur du sommet de l'obstruction (par rapport au point de référence choisi sur la fenêtre)

## 1. Azimut relatif à la façade

**γ = As − An**

Si |γ| > 90°, le soleil est derrière le mur : aucun rayon direct.

## 2. Angle d'incidence sur le vitrage

**cos θ = cos h · cos γ**

θ sert à calculer l'énergie reçue (flux ∝ cos θ, loi de Lambert).

## 3. Angle de profil (la clé de tout le reste)

**tan hp = tan h / cos γ**

C'est l'angle apparent du soleil "vu de côté", dans le plan vertical perpendiculaire à la façade. Toutes les ombres portées (linteau, mur écran, auvent) se calculent avec cet angle.

## 4. Effet des rebords du mur (embrasure)

**Jambages latéraux** (masque dû à γ) — ombre horizontale portée :
```
d_lat = e · tan γ
W_utile = W − d_lat   (borné entre 0 et W)
```

**Linteau / allège** (masque dû à hp) — ombre verticale portée :
```
d_vert = e · tan hp
H_utile = H − d_vert   (borné entre 0 et H)
```

Surface effectivement éclairée : **S_utile ≈ W_utile × H_utile**

## 5. Mur écran extérieur (distance D, hauteur Hm)

Condition d'occultation : le mur bloque le soleil si

**hp_limite = arctan(Hm / D)**

- hp < hp_limite → point à l'ombre du mur
- hp ≥ hp_limite → le soleil passe au-dessus

Pour savoir *quelle partie* de la fenêtre est éclairée (du bas vers le haut), on calcule la hauteur d'ombre projetée sur le plan de la fenêtre :

**y_ombre = Hm − D · tan hp**

Tout point de la fenêtre avec y < y_ombre est à l'ombre ; au-dessus, il reçoit le soleil (sous réserve des masques du §4).

## 6. Synthèse : un point (x, y) de la fenêtre reçoit un rayon direct si

1. |γ| < 90°
2. x ∈ W_utile et y ∈ H_utile (pas masqué par les rebords)
3. y > y_ombre (pas masqué par le mur écran)

Et l'énergie reçue est alors **E ∝ cos h · cos γ**, sinon E = 0.

---

Il te manque encore les formules pour obtenir h et As à partir de la latitude/date/heure (déclinaison solaire, angle horaire) — tu veux que je les ajoute ? Je peux aussi te construire un petit simulateur interactif (tu entres orientation, dimensions, épaisseur de mur, distance/hauteur du mur écran, date/heure, et ça calcule/dessine directement quelle surface de la fenêtre est éclairée).
