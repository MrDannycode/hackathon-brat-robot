# Etapa 3: verificare offline a viziunii

Implementarea HSV foloseste `cv2.cvtColor` si `cv2.inRange`, conform
[documentatiei OpenCV](https://docs.opencv.org/4.x/da/d97/tutorial_threshold_inRange.html).
Nu se conecteaza la brat. Pragurile sunt in `common/config.json`.

Pe Pi, OpenCV 4.10.0 a detectat exact red/yellow/green/blue in fiecare dintre
imaginile reale `calibration_20261030_040121_899264.jpg` si
`calibration_20261030_040351_136556.jpg`. In prima, rosu si galben ating marginea;
in a doua toate cele patru componente sunt complet vizibile.

Operatorul a confirmat a doua configuratie: red=2,1; yellow=2,3;
green=3,1; blue=3,3. Acestea sunt referinte de calibrare, nu test independent.

Test independent: `calibration_20261030_040930_440650.jpg`, fara refacerea
geometriei. Rezultatul automat coincide cu aranjamentul cerut si vizibil in
fotografie: red=2,2; blue=2,3; green=3,1; yellow=3,3, restul fara culoare
detectata. Toate cele patru componente sunt complet vizibile si departe de
limitele celulelor in planul calibrat. Raport si overlay pe Pi:
`artifacts/independent_arrangement.json` si `.jpg`. Acest test verifica doar
aranjamentul respectiv; primul rand, toate culorile in toate celulele si
siguranta miscarilor raman nevalidate. Flagurile globale raman false.

Al doilea test independent: `calibration_20261030_041144_560656.jpg`, doar
rosul mutat in 1,2. Detectorul a raportat red=1,2; blue=2,3; green=3,1;
yellow=3,3, conform imaginii. Rosul este complet in cadru, dar incepe la y=4 px:
marja foarte mica sus, fara garantie pentru celulele 1,1 si 1,3. Raportul si
overlay-ul sunt `artifacts/first_row_test.json` / `.jpg`. Geometria si flagurile
de validare nu au fost modificate.

Test colturi: `calibration_20261030_041448_118301.jpg`, red=1,1;
blue=1,3; green=2,2; yellow=3,2. Initial, un fragment albastru de 1799,5 px
pe fata laterala a cubului verde a produs un candidat suplimentar; centrul
a fost refuzat ca ambiguu. Dovezile initiale raman pe Pi in
`artifacts/corners_test_before_filter.json` / `.jpg`.

Pragul configurabil `vision.detector.min_area_fraction` a fost ajustat de la
0,005 la 0,015 (4608 px la 640x480). Cea mai mica fata reala din cele patru
cadre de regresie are 8491,5 px. Cu acest filtru, toate cele patru configuratii
(o referinta si trei aranjamente) au tabelele asteptate, iar cadrul gol nu
produce candidati. Raport: `artifacts/vision_filter_regression.json`. Testul
colturilor a fost folosit la reglaj: necesita un NOU aranjament independent.
Filtrul presupune dimensiunile actuale ale cuburilor in imagine; nu elimina
generic toate desenele de pe fetele laterale si trebuie reevaluat dupa
schimbarea distantei camerei, rezolutiei sau dimensiunii cuburilor.

Verificare independenta DUPA reglarea filtrului:
`calibration_20261030_041827_271967.jpg`. Fara ajustari ale pragurilor sau
geometriei, rezultatul a fost blue=2,1; green=1,2; yellow=2,2; red=3,3,
cu celelalte cinci celule fara culoare detectata. Inspectia vizuala a
`artifacts/post_filter_independent_test.jpg` confirma amplasarea; raportul
este in fisierul `.json` cu acelasi nume. Cea mai mica fata detectata are
7556,5 px. Nu s-a facut test de miscare. Acest succes este limitat la
aranjamentele si iluminarea observate; flagurile globale nu autorizeaza proba
autonoma sau manipularea. Cadrele din primul rand au margine de doar 3–5 px.

Perspectiva mesei nu este perspectiva fetelor de sus. Folosim o transformare
separata din centrele componentelor colorate spre centrele celulelor confirmate.
Transformarea provizorie ramane in `artifacts/source_face_geometry.provisional.json`;
nu marcheaza configuratia principala ca validata. Sunt presupuse cuburi de aceeasi
inaltime, centrate, camera si foaia fixe. Fetele laterale colorate pot deplasa
centrul componentei (vizibil la verde); aceasta versiune necesita validare pe
aranjamente noi si poate necesita segmentarea suplimentara a fetei superioare.

Exemplu pe Pi:

```sh
python3 vision_check.py --image artifacts/calibration_20261030_040351_136556.jpg --geometry artifacts/source_face_geometry.provisional.json --output artifacts/vision_check
```

Fara geometria fetelor, toate celulele raman necunoscute. Cu geometrie provizorie,
raportul contine `proposed_cells`; `empty` inseamna doar absenta unei componente
de culoare acceptata. Nu exclude un cub de culoare necunoscuta, ascuns sau slab
iluminat. Componentele decupate, aproape de limite sau multiple in aceeasi celula
produc avertismente. Detectorul nu autorizeaza miscari (`ready_for_motion=false`).

Restante: alte aranjamente, toate cele 9 celule, obiecte
necunoscute, repetabilitate lumina/camera si destinatie. Calibrarea mecanica
home/transit/gripper/pick/place ramane separata si nevalidata.
