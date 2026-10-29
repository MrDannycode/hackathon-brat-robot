# Roboți Industriali — Dofbot / Raspberry Pi 4

Proiect construit incremental. **Etapa curentă: 1, verificare hardware nefinalizată.**
Nu rula încă probe de concurs. Controlul mecanic nu este validat.

## Situația verificată pe 29 octombrie 2026

- Raspberry Pi accesibil prin SSH; Debian 13 Trixie, Python 3.13.5.
- `/dev/i2c-1` disponibil; utilizatorul aparține grupurilor `i2c` și `video`.
- Placa răspunde la adresa I2C `0x15`.
- OpenCV 4.10.0, numpy 2.2.4, smbus, smbus2 și Picamera2 sunt deja instalate.
- `Arm_Lib` nu este instalată; niciun fișier `Arm_Lib.py` găsit în directoarele investigate din `/home/rpxdanutsrl` și `/opt`.
- Cameră USB Microdia `0c45:6340`, `/dev/video0`; captură reală 640×480 verificată vizual.
- Camera nu expune prin `v4l2-ctl --list-ctrls` controale standard de expunere manuală sau balans de alb. Fixarea lor rămâne neverificată.
- Cinci teste automate de siguranță trecute pe Python 3.13 de pe Pi, fără hardware în teste.
- **Testul real de mișcare a eșuat:** țintă S1 94,95°, feedback 92,95°, fără mișcare observată de operator. Comanda de revenire a fost trimisă.
- Operatorul a raportat ulterior că brațul a căzut cu vârful pe masă. Momentul exact și cauza nu sunt stabilite. Ultima stare raportată: stabil, alimentat, fără deteriorări vizibile.
- Nu a fost trimisă comanda globală de cuplu și nu a fost comandat `home`.

**Testele fizice sunt oprite.** Înainte de repoziționarea manuală, brațul trebuie susținut și alimentarea externă a plăcii oprită. Nu activa cuplul și nu executa o revenire automată din poziția căzută. Reluarea necesită verificarea fizică împreună cu operatorul.

## Fișiere existente

- `dofbot/hardware_check.py`: inventar fără mișcare, codificare I2C și test explicit pe un singur servo.
- `dofbot/common/config.json`: parametri I2C, limite nominale, parametri pentru test; `home` este intenționat `null`.
- `dofbot/test_hardware_check.py`: verificări pentru limite, protocol, feedback nemodificat, Ctrl+C și revenirea exclusivă a servoului testat.
- `dofbot/docs/protocol-i2c.md`: protocolul și proveniența implementării.

Pe Pi, fișierele au fost copiate în `/home/rpxdanutsrl/dofbot-concurs`.
Imaginea reală este salvată acolo ca `artifacts/stage1_camera.jpg`; copia locală și inventarul sunt în `.local/` (ignorate de Git).

## Dependențe și verificări fără mișcare

Dependențele sunt deja disponibile pe Pi. Pentru o instalare nouă, pe Debian/Raspberry Pi OS:

```sh
sudo apt update
sudo apt install python3-opencv python3-numpy python3-smbus python3-smbus2 v4l-utils usbutils
```

Picamera2 este necesar numai pentru o cameră CSI; camera detectată aici este USB.
Nu instala pachete cu `sudo pip` în Python-ul de sistem. Dacă va fi nevoie de pachete suplimentare, folosește un mediu virtual cu `--system-site-packages` pentru acces la OpenCV din distribuție.

```sh
cd ~/dofbot-concurs
python3 hardware_check.py
python3 hardware_check.py --servo-test --dry-run
python3 -m unittest -v test_hardware_check
```

Prima comandă inventariază modulele și dispozitivele video, fără acces de control la braț. `--dry-run` nu deschide I2C.
Combinația `--servo-test` fără `--dry-run` comandă hardware real; **nu o executa în starea actuală**.

## Protocol și limite ale etapei 1

Am implementat direct subsetul I2C necesar diagnosticului, folosind `smbus`; nu am instalat distribuția terță Arm-Lib doar pentru a ocoli absența bibliotecii Yahboom.
Erorile de comunicație sunt propagate. Limitele din config sunt limite nominale ale servourilor, nu limite mecanice calibrate și nu garantează evitarea coliziunilor.

În testul inițial, toleranța de 2° a permis incorect un rezultat favorabil pentru o comandă de doar 2°. Toleranța a fost corectată la 0,75° și cazul a primit un test automat. Repetarea pe hardware a raportat corect eșecul.

În acest diagnostic, Ctrl+C încearcă revenirea **numai a servoului testat** la unghiul citit înainte de test și închide magistrala. Nu comandă celelalte articulații, nu eliberează cleștele și nu folosește un `home` inventat. Această recuperare nu este încă mecanismul final de oprire al probelor de concurs. O problemă de alimentare sau I2C poate împiedica și revenirea.

## Pașii următori, în ordinea cerută

1. Stabilizare fizică și diagnostic al controlului/cuplului/alimentării. Confirmarea unui test lent cu feedback și observație fizică.
2. `common/arm.py`, `common/camera.py`, scheletul configurației complete și `calibrate.py`; oprire pentru calibrarea fizică.
3. HSV și grile în `vision.py`, validate pe imagini reale. Nu există încă detecție de culori sau celule validată.
4. `task1.py`: detecție, o mutare, apoi aranjamentul complet, cu verificare și retry în bugetul de timp.
5. `task2.py` separat, apoi optimizare de viteză după validare mecanică.

## Presupuneri încă neverificate

- Starea cuplului, stabilitatea alimentării sub sarcină și cauza căderii.
- Corectitudinea feedbackului ca reprezentare a poziției fizice; răspunsul `0xDA` nu dovedește existența cuplului.
- Limitele mecanice individuale, traseele fără coliziuni, `home`, deschiderea/închiderea cleștelui și forța de prindere.
- Pozițiile celor 18 celule, pozițiile de apropiere/retragere, înălțimea cubului și pozițiile pentru fiecare nivel al turnului. Înălțimea în milimetri nu se adună direct la unghiuri servo.
- Vizibilitatea ambelor grile, geometria camerei și stabilitatea culorilor la iluminarea concursului.
- Păstrarea feței superioare la transfer, stabilitatea turnului și fezabilitatea tuturor pozițiilor până la cinci niveluri.
- Numărul de cuburi și convenția probei 1: transfer din sursă în destinație sau copiere cu un stoc separat. Aceasta trebuie clarificată înaintea planificatorului.
- Încadrarea într-o probă autonomă de cinci minute. Nu există încă o rulare de concurs validată.
