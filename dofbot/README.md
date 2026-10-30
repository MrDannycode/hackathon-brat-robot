# Dofbot — Roboți Industriali

Actualizare etapa 3: `common/vision.py` si `vision_check.py` detecteaza cele patru
culori in doua fotografii reale pe Pi. Geometria fetelor este provizorie si
asteapta un aranjament independent; nu exista inca miscare autonoma validata.
Vezi [rezultate si limite](docs/vision-stage3.md).

Proiect incremental pentru Raspberry Pi 4, Debian Trixie, Python 3.13.
**Etapa curentă: calibrare fizică.** Nu există încă probe autonome validate.

## Ce a fost verificat

- Pi: Debian 13.7, Python 3.13.5; acces la grupurile `i2c` și `video`.
- Placa răspunde pe magistrala 1, adresa de 7 biți `0x15`; octet versiune raportat: 2.
- Toate cele șase servouri răspund `0xDA`; citirile urmăresc repoziționarea fizică.
- După setarea țintelor la unghiurile curente și activarea cuplului global: S1 start 93,03°, țintă 95,03°, feedback 94,58°; revenire comandată la 93,03°, feedback 93,68°. Operatorul a confirmat rotația, revenirea și stabilitatea restului brațului.
- Camera este USB Microdia `0c45:6340`, la `/dev/video0`; captură reală 640×480 salvată și inspectată.
- OpenCV 4.10.0, numpy 2.2.4, smbus, smbus2 și Picamera2 sunt instalate. `Arm_Lib` lipsește; folosim `smbus` direct. Vezi [protocolul și sursele](docs/protocol-i2c.md).
- Testele automate verifică simularea, limitele, refuzul pozițiilor necalibrate, ordinea pick/place, deriva articulațiilor necomandate, inițializarea cuplului și izolarea salvărilor dry-run. Nu înlocuiesc validarea mecanică.

Etapa 2 a fost verificată pe Pi: **21 de teste trecute**, `calibrate.py --dry-run --smoke` reușit, meniul real executat numai cu `read`, `status`, `exit`, fără mișcare. `common/camera.py` a salvat `artifacts/stage2_camera.jpg` la 640×480; copia locală și raportul sunt în `.local/`. Imaginea arată tavanul: poziția camerei trebuie corectată înainte de calibrarea grilei. Anti-pâlpâirea la 50 Hz a fost aplicată și recitită; expunerea/balansul fixe rămân indisponibile prin controalele standard.

Anterior, operatorul a raportat căderea vârfului pe masă. Brațul a fost oprit, repoziționat și repornit, fără deteriorări vizibile raportate. **Cauza căderii nu este stabilită.** Păstrăm [raportul inițial](docs/stage1-initial.md) ca istoric.

## Fișiere și instalare

`common/arm.py` controlează brațul; `common/protocol.py` implementează subsetul I2C; `common/camera.py` asigură captură și flush; `common/settings.py` salvează atomic configurația; `common/config.json` păstrează toți parametrii, pragurile inițiale și pozițiile încă necalibrate. `calibrate.py` este meniul de calibrare, iar `hardware_check.py` diagnosticul. Importarea modulelor nu pornește hardware-ul.

Local, lucrează din `dofbot/`. Pe Pi, proiectul este în `~/dofbot-concurs/`.

Dependențele sunt deja disponibile pe Pi. Pentru o instalare nouă cu cameră USB:

```sh
sudo apt update
sudo apt install python3-opencv python3-numpy python3-smbus python3-smbus2 v4l-utils usbutils
```

Pentru alte pachete folosește un mediu virtual cu `--system-site-packages`, fără `sudo pip`. Picamera2 este necesar numai pentru CSI; ramura CSI nu este testată pe hardware în acest proiect.

## Rulare

```sh
cd ~/dofbot-concurs
python3 -m unittest discover -p 'test_*.py' -q
python3 calibrate.py --dry-run --smoke
python3 calibrate.py --dry-run
```

`--dry-run` simulează numai brațul. Comenzile preview folosesc camera reală dacă le alegi. Salvările simulate merg în `common/config.dry-run.json`, marcat `simulated` și refuzat de controlul real.

Pentru calibrare reală, într-un terminal al desktopului Pi deschis prin VNC:

```sh
cd ~/dofbot-concurs
python3 calibrate.py
```

Conectarea și `read` nu comandă mișcare și nu schimbă cuplul. Meniul și diagnosticul folosesc aceeași blocare exclusivă `.arm.lock`; nu porni alt controler simultan.

## Calibrare, în ordine

1. Fixează brațul și grilele, cu zona liberă și acces la întrerupător. Nu opri alimentarea unui braț nesusținut și nu forța articulațiile alimentate. După repornire nu presupune că există cuplu: meniul nu îl activează. Cere reluarea inițializării controlate dacă brațul nu menține poziția.
2. `read` afișează S1 baza, S2 umărul, S3 cotul, S4 înclinarea încheieturii, S5 rotația încheieturii, S6 gripperul. `j ID UNGHI` primește un unghi absolut numeric, la maximum 60° de citirea curentă. La primul test al unui servo netestat folosește circa 1° și observă sensul. Nu copia unghiurile de simulare pe hardware.
3. `limit ID MIN MAX` salvează limite conservative, fără mișcare. Limitele inițiale sunt nominale, nu mecanice validate. Nu explora automat extremele.
4. Construiește gradual o poziție sigură și salvează `save home`. Salvează separat `save transit`, deasupra obstacolelor. Verifică fizic traseele, nu doar capetele. `goto NUME` trece prin `transit`; nu există încă planificator de coliziuni.
5. Reglează gradual S6: `grip open` salvează citirea curentă la deschiderea suficientă; `grip closed` la prinderea blândă a cubului. Aceste comenzi salvează fără mișcare. Ulterior `open`/`close` execută unghiurile salvate. Evită strângerea forțată.
6. Așază camera astfel încât întreaga grilă sursă și fețele superioare să fie vizibile; `save view_source`. Repetă pentru destinație cu `save view_destination`. `preview` deschide camera; S salvează un cadru în `artifacts/`, Q închide.
7. Pentru prima celulă sursă, centrează cleștele deasupra cubului, la înălțime sigură: `save source 1,1 approach`. Coboară gradual la prindere, fără să împingi masa/cubul: `save source 1,1 contact`. Repetă cu `save destination 1,1 approach` și `save destination 1,1 contact`. Pozițiile conțin cinci articulații; gripperul este separat.
8. Verifică întâi traseele de retragere/tranzit/home fără cub. După calibrare și verificare fizică, `recovery on` permite recuperarea automată. `test 1,1 1,1` execută un singur pick/place mecanic. **Nu are încă verificare vizuală automată.** Oprește-te pentru verificare fizică înainte de restul celulelor.
9. Completează approach/contact pentru cele 9 celule sursă și 9 destinație. Liniile și coloanele sunt 1..3; convenția trebuie să fie aceeași în pozițiile servo și în imagini.
10. Din poziția vizuală corespunzătoare: `grid source` sau `grid destination`; click pe colțurile exterioare în ordinea stânga-sus, dreapta-sus, dreapta-jos, stânga-jos. S salvează, R reia, Q anulează. Nu muta camera înainte să salvezi și imaginea de referință.
11. `hsv red 1`, `hsv red 2`, `hsv yellow`, `hsv green`, `hsv blue` reglează HSV live. H: 0..179, S/V: 0..255. Roșul are două benzi; S salvează banda, Q anulează. Acesta este preview de mască, nu detectorul de celule din etapa 3.

`status` arată ce lipsește. Salvările sunt atomice și păstrează versiunea precedentă în `config.json.bak`. Existența unghiurilor nu marchează automat calibrarea drept validată.

## Oprire

Mișcările folosesc interpolare smoothstep, viteză și durate din config. Țintele și feedbackul final sunt validate. Deriva unei articulații necomandate peste toleranță oprește operația. Aceste măsuri nu detectează toate coliziunile.

Cu `recovery_enabled=false`, Ctrl+C oprește operația fără alte mișcări; **cuplul este păstrat**. Nu există home sau gripper implicit.

După calibrarea și verificarea traseelor, `recovery on` permite la Ctrl+C retragerea prin approach-ul activ, tranzitul, deschiderea gripperului și revenirea home. La eroare de I2C/feedback, meniul se oprește fără recuperare oarbă. Închiderea programului nu dezactivează cuplul. Susține brațul înainte de a-i întrerupe alimentarea.

`hardware_check.py --feedback` solicită numai măsurări/stări. `--servo-test` comandă hardware real. `--enable-hold` activează explicit cuplul global după pregătirea țintelor curente; nu este o recuperare universală. Se folosește numai după verificarea fizică a brațului.

## Turn și continuare

Configurația rezervă approach/contact pentru toate cele 9 ținte, la nivelurile 1..5. `height MM` salvează înălțimea cubului și diferențele nivelurilor față de primul nivel. `save tower RAND,COL NIVEL approach|contact` salvează unghiuri măsurate. Milimetrii nu se adună la unghiuri; nu există încă model cinematic validat.

După calibrare: `vision.py` pe imagini reale, apoi `task1.py` separat (detecție → o mutare → aranjament complet, verificare/retry), apoi `task2.py` cu `--order`/`--target`, timer și optimizare. Aceste scripturi nu sunt încă implementate; nu declarăm probele funcționale înaintea validării.

## Verificări restante și presupuneri

- În afara testului bazei, mișcările individuale, interpolarea pe hardware, gripperul, traseele și pick/place nu sunt încă validate fizic.
- Preview-ul și trackbar-urile VNC trebuie verificate în sesiunea grafică a operatorului.
- Camera USB nu expune controale standard pentru expunere manuală și balans de alb. Modulul raportează lipsa; nu pretinde că le-a fixat. `require_fixed_controls=true` refuză camera fără toate controalele. Trebuie validată stabilitatea culorilor în iluminarea concursului sau folosită altă cameră cu respectivele controale.
- Cele 18 celule, pozițiile de privire, colțurile grilelor, pragurile HSV și turnul sunt necalibrate. Pragurile livrate sunt valori de pornire.
- Vizibilitatea întregii grile și paralaxa dintre planul mesei și fețele superioare trebuie evaluate pe imagini reale.
- Păstrarea feței superioare, forța de prindere, stabilitatea turnului și accesul la cinci niveluri nu sunt demonstrate.
- Proba 1 necesită clarificare: transferul cuburilor sursă sau copiere folosind stoc separat.
- Nicio probă autonomă de cinci minute nu a fost rulată. Planificarea mutărilor, verificarea după plasare și retry vor fi validate ulterior.
