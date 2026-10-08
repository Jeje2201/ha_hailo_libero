# Hailo Libero pour Home Assistant

Projet independant maintenu par [Jeje2201](https://github.com/Jeje2201).
Integration personnalisee locale du Hailo Libero 3.0, installable par ZIP.
Ce projet n'est pas officiel Hailo. HACS et un compte PyPI ne sont pas requis.

## Architecture

Le client HTTP dans `src/aiohailo_libero` ne depend pas de Home Assistant.
En developpement, `custom_components/hailo_libero/api` reexporte la bibliotheque
installee avec `pip install -e .`. Le generateur de ZIP remplace ce pont par
les sources autonomes du client : tout est inclus pour l'installation sur HA.
Copier uniquement `custom_components` depuis le workspace n'est pas une
installation autonome : utiliser le ZIP genere. Aucune publication PyPI
n'est necessaire.

## Credits

Le protocole et le comportement initial ont ete etudies a partir de :

- [ha_hailolibero par voldemarpanso](https://github.com/voldemarpanso/ha_hailolibero).
- [hailolibero par Nick Dawson](https://github.com/Neonkoala/hailolibero)
  et [les adaptations de voldemarpanso](https://github.com/voldemarpanso/hailolibero).

Le code de ce projet est une nouvelle implementation, pas un fork Git.
Les notices MIT des references sont conservees dans `THIRD_PARTY_NOTICES.md`.

## Fonctions

- Bouton d'ouverture : declenche le mecanisme, sans pretendre connaitre
  la position physique de la poubelle.
- Luminosite LED, force d'ouverture et distance de detection : valeurs entieres
  et limites fournies par le firmware, sans unite physique supposee.
- Bouton de redemarrage, desactive par defaut dans le registre des entites.
- Reauthentification, reconfiguration et recuperation apres une indisponibilite.
- Interrogation locale toutes les 60 secondes lorsque des entites sont actives.

Le proprietaire a confirme les essais sur son Hailo Libero 3.0 : ouverture,
reglages, coupure/reconnexion et propagation des changements de l'interface
web vers HA. IPv6, decouverte automatique et mise a jour du firmware
ne sont pas implementes.

## Installation sur HA OS

1. Effectuer une sauvegarde Home Assistant.
2. Generer l'archive avec `python scripts/build_release.py` ou utiliser l'archive
  disponible dans `dist/hailo-libero-0.1.0.zip` apres generation.
3. Extraire l'archive sur le PC. Via un partage Samba ou un outil de fichiers
  HA OS, placer le dossier `hailo_libero` dans
  `/config/custom_components/hailo_libero`. Ne pas creer un niveau
  `custom_components/custom_components` et ne pas copier seulement le ZIP.
4. Redemarrer Home Assistant, puis ouvrir Parametres > Appareils et services >
  Ajouter une integration > Hailo Libero.
5. Saisir l'adresse IP locale, le port 81 et le mot de passe de l'interface web
  Hailo. Le mot de passe est obligatoire, sans valeur par defaut imposee.
6. Tester d'abord le bouton Ouvrir avec la zone de mouvement degagee, puis
  chaque reglage en notant sa valeur initiale. Le redemarrage est facultatif.

Si l'integration n'apparait pas, verifier le chemin, redemarrer Home Assistant
et rafraichir le navigateur. Home Assistant affichera l'avertissement habituel
pour une integration personnalisee. HACS n'est ni requis ni utilise.

Si l'ancien projet est installe, le desactiver avant ces essais pour eviter
deux clients concurrents. Les domaines sont differents : aucune migration
automatique des anciennes entites ou automatisations n'est effectuee.

## Depannage et securite

Verifier depuis le reseau local que `http://ADRESSE:81/` affiche l'interface Hailo.
La communication est HTTP non chiffree : ne jamais exposer le port sur Internet.
Home Assistant stocke le mot de passe dans ses entrees de configuration ;
proteger les sauvegardes. Le client ne conserve pas les identifiants Wi-Fi
lus dans la page et ne journalise ni mot de passe ni contenu HTML.

Une erreur de connexion provoque des tentatives de reprise et l'indisponibilite
des entites. Sans commande, une coupure est detectee au prochain controle
periodique : compter environ 60 secondes, plus le delai reseau de 10 secondes.
Une commande echouee pour une erreur de connexion rend les entites
indisponibles immediatement, sans attendre ce controle. Un refus de commande
par un appareil joignable ne suffit pas a le declarer hors ligne.
Un mot de passe refuse lance une reauthentification. Une page
incompatible produit une erreur explicite plutot que des valeurs supposees.
Apres une erreur de commande, verifier physiquement l'appareil avant de
reessayer : une reponse perdue ne signifie pas que l'ouverture n'a pas eu lieu.

Pour remonter un probleme, fournir la version HA, le firmware, le modele et
l'erreur, jamais le mot de passe ni le HTML brut (il peut contenir la cle Wi-Fi).

Pour retirer l'integration : supprimer son entree dans Appareils et services,
puis supprimer `/config/custom_components/hailo_libero` et redemarrer HA.

## Developpement

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests/test_api.py tests/test_distribution.py
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe scripts/build_release.py
```

Les tests Home Assistant demandent Linux et la version de Python prise en charge
par la version HA installee. Sous Windows, utiliser Docker :

```powershell
docker build -f Dockerfile.test -t jeje2201-hailo-tests .
docker run --rm jeje2201-hailo-tests
```

Le conteneur ne contacte aucun appareil reel. Le paquet de fixtures est fige
a `pytest-homeassistant-custom-component==0.13.370`, qui utilise
Home Assistant `2026.10.0b4` (beta), avec Python 3.14. Cette verification
ne garantit pas la compatibilite avec une ancienne version sur le Raspberry.
Les tests HTTP locaux sont executes separement : les fixtures Home Assistant
interdisent volontairement les sockets.

## Distribution

La CI du depot teste l'integration et fournit l'archive ZIP en artefact.
Pour partager une version, joindre le ZIP genere a une release GitHub.
Le depot GitHub n'est pas cree ou publie automatiquement par ces scripts.

## Diagnostic facultatif

Pour relever le firmware et verifier l'identifiant, utiliser un outil de
lecture seule. Le mot de passe est demande dans le terminal et non affiche :

```powershell
.\.venv\Scripts\python.exe scripts/probe_device.py --host ADRESSE_IP
```

Ne jamais partager le mot de passe ni enregistrer la page HTML brute.