# Oprire calibrare S3

Operatorul a confirmat fizic intregul ciclu home–transit: deplasari line.
Durata minima de 3000 ms folosita in test a fost pastrata in configuratia de
lucru. Aceasta valideaza doar traseul scurt observat, cu clestele gol; nu
valideaza traseele spre celule sau transportul cu cub. Recovery ramane oprit.

Controler actualizat dupa confirmarea operatorului ca ridicarea cu corectie a
fost lina. Corectia este optionala in `motion.s3_correction`, limitata la o
singura comanda suplimentara, maximum 2 grade, numai S3 in sens crescator,
tinte si pozitii initiale intre 26 si 32 grade, deplasare initiala 3–5,1 grade.
Se refuza corectia la deriva, feedback instabil, depasirea limitelor, eroare
mare sau la alte articulatii. Toleranta ramane 1 grad. Nu se schimba cuplul.
Cele 30 de teste au trecut local si pe Pi in simulare, inclusiv 9 regresii
pentru corectie. Configuratiile fizice au fost pastrate la instalare.

Pozitia transit a fost salvata din feedbackul confirmat fizic: S3=31,582 grade,
restul articulatiilor ca home. Test real cu controlerul actualizat, un ciclu
transit -> home -> transit, durata minima temporara 3000 ms:
home a raportat S3=26,836 grade; transit S3=31,582 grade dupa corectia limitata
cu comanda 33,055 grade. Testul a trecut verificarile de feedback; asteapta
confirmarea fizica pentru intregul ciclu. Recuperarea automata ramane oprita.
Raport pe Pi: `artifacts/home_transit_cycle.json`.

Test diagnostic cu o corectie limitata, dupa confirmarea fizica a revenirii:
ridicare cu tinta S3=31,673 grade. Prima comanda a produs din nou 30,273 grade.
La feedback stabil si fara deriva a celorlalte articulatii, s-a permis exact
o corectie a comenzii cu eroarea observata (+1,4 grade), sub plafonul de 2 grade:
comanda 33,073 grade, 3000 ms. Feedbackul a ajuns la 31,582 grade si a ramas
stabil in doua citiri; eroare fata de tinta fizica 0,091 grade, in toleranta
nemodificata de 1 grad. Nu s-a schimbat cuplul, nici codul controlerului de
productie. Jurnal: `artifacts/s3_bounded_correction.json`. Acesta este un singur
test reusit, nu validare generala a compensarii pe toate pozitiile/sarcinile.

Alimentator raportat de operator: FY-1250, intrare AC100–240V 50–60Hz,
iesire DC12V 5A. Valorile nominale coincid cu cele din depozitul oficial
Yahboom dofbot-Pi; tensiunea sub sarcina nu a fost masurata.
S-a testat apoi numai S3 in sens opus, 30,273 -> home 26,673 grade, 3000 ms.
Cele trei citiri dupa asteptare au fost 26,918; 26,755; 26,755 grade;
abaterea finala aproximativ 0,082 grade, in toleranta neschimbata de 1 grad.
Celelalte articulatii au ramas stabile. Acest test NU este o executie completa
de home prin transit, care ramane necalibrat. Jurnal pe Pi:
`artifacts/s3_return_home.json`. Succesul la coborare nu rezolva abaterea
observata la ridicare; cauza ramane nestabilita.

Operatorul a confirmat: cresterea S3 ridica clestele. O singura retrimitere a
aceleiasi tinte de 31,673 grade, in 3000 ms, a lasat S3 la 30,273 grade;
abaterea de 1,4 grade persista. Celelalte articulatii sunt stabile. Raport pe
Pi: `artifacts/s3_repeat_same_target.json`. Transit nu a fost salvat/validat.

Test suplimentar cerut explicit de operator: +5 grade printr-o singura comanda
de 3000 ms, tinta 31,673 grade. S3 s-a deplasat de la 26,673 la 30,273 grade,
valoare stabila in trei citiri dupa asteptarea de 4 secunde. Deplasare observata
3,6 grade; abatere fata de tinta 1,4 grade, peste toleranta de 1 grad.
Testul s-a oprit cu eroare; toleranta nu a fost modificata. Celelalte
articulatii au ramas stabile. Nu s-a comandat revenire.
Jurnal pe Pi: `artifacts/s3_single_step_5deg.log` / `.json`.

Actualizare: operatorul a confirmat absenta unui obstacol vizibil. Aceeasi
tinta S3=28,673 grade a fost testata printr-o singura comanda de 2000 ms,
fara interpolare. Dupa 3 secunde si trei citiri, S3 a ramas la 26,673 grade;
celelalte articulatii au ramas stabile. Testul a esuat cu toleranta
neschimbata. Eliminarea interpolarii nu a rezolvat problema.
Jurnal pe Pi: `artifacts/s3_single_step.log` / `.json`.
Nu s-au trimis alte miscari sau comenzi de cuplu in acest test.

Pe 2026-10-30, dupa iesirea operatorului din `calibrate.py`, diagnosticul I2C
a raportat toate cele 6 servouri cu raspuns `0xda` si trei esantioane stabile.
S3 era la 26,673 grade. Prinderea salvata: open=98,1; closed=109,227 grade.
Home este salvat; transit lipseste, recovery ramane dezactivat.

S-a reprodus un pas S3 de +2 grade cu durata minima 2000 ms, fara modificarea
configuratiei de miscare persistente. Tinta a fost 28,673 grade, dar feedbackul
final a ramas 26,673 grade. Controlerul a ridicat RuntimeError si a oprit
operatia. Nu s-au comandat revenire, alte articulatii sau modificari de cuplu.
Jurnal pe Pi: `artifacts/s3_calibration_attempt.log` si `.json`.

Cauza nu este stabilita. Raspunsul la diagnostic nu demonstreaza executarea
miscarilor. Nu se valideaza transit si nu se relaxeaza toleranta pentru a ascunde
eroarea. Este necesara observatia fizica a operatorului (miscare, zgomot,
obstacole/cabluri) inainte de alte teste de miscare.

Operatorul a raportat doar o tresarire a cotului. Verificari ulterioare fara
miscare: `fuser /dev/i2c-1` nu a gasit descriptor deschis; lista proceselor
nu a aratat alt controler robotic activ; serviciile nu au aratat un serviciu
Yahboom/robotic relevant. `vcgencmd get_throttled` a raportat `0x0`.
Aceasta indica absenta indicatorilor de subtensiune/throttling raportati de
Pi; nu masoara alimentarea servourilor. Nu este stabilita o cauza mecanica,
electrica sau de control. Nu s-au relaxat tolerantele si nu s-a schimbat cuplul.
