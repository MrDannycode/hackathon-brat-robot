# Subset I2C pentru diagnosticul inițial

Nu este un protocol UART. Magistrală Linux 1, adresă de 7 biți `0x15`.

Surse consultate:

- [Documentația Yahboom despre biblioteca driver](https://www.yahboom.net/public/upload/upload-html/1699255422/8.Driver%20library%20and%20communication.html).
- [Depozitul oficial dofbot-Pi](https://github.com/YahboomTechnology/dofbot-Pi), care indică arhivele de curs în `Annex_Download_Link.txt`.
- [Distribuția publică Arm-Lib 1.0.0 de pe PyPI](https://pypi.org/project/Arm-Lib/1.0.0/), autor declarat Hanson, fișier intern `Arm_Lib/Arm_Lib.py` marcat V0.0.5. **Distribuție terță, proveniență oficială Yahboom neconfirmată.** Arhiva a fost citită pentru verificarea implementării, fără instalare sau executarea codului ei; SHA-256 a fost verificat față de metadatele PyPI.

Driverul de diagnostic este implementat în proiect și transmite numai comenzile descrise mai jos. Constantele de protocol și parametrii testului sunt în `common/config.json`.

## Scrierea unui singur servo

ID permis: 1–6; ID 0/broadcast nu este permis în diagnostic.

`write_i2c_block_data(0x15, 0x10 + id, [pos_H, pos_L, time_H, time_L])`

Poziția și durata în milisecunde sunt valori de 16 biți, octet superior primul.
Durata trebuie să fie 1–65535 ms. Testul inițial impune minimum 2000 ms și maximum 3° deplasare relativă.

- S1, S2, S3, S4, S6: `raw = int(900 + angle * 2200 / 180)`.
- Pentru S2, S3, S4, unghiul este inversat înainte de conversie: `angle = 180 - angle`.
- S5: `raw = int(380 + angle * 3320 / 270)`.

Limitele nominale sunt 0–180°, respectiv 0–270° la S5; acestea nu sunt limite mecanice validate pe montaj.

## Citirea feedbackului

1. `write_byte_data(0x15, 0x30 + id, 0)` solicită feedbackul; nu este o comandă de poziționare.
2. Așteptare configurată de 10 ms.
3. `read_word_data(0x15, 0x30 + id)`.
4. Inversarea octeților rezultatului SMBus, apoi conversia inversă în grade și inversarea pentru S2–S4.

Valori brute în afara domeniului sunt erori. Nu se înlocuiesc cu un unghi implicit pentru mișcare reală.

## Verificarea stării unui servo

`write_byte_data(0x15, 0x38, id)`, pauză, `read_byte_data(0x15, 0x38)`.
S1 a răspuns `0xDA`. Această verificare confirmă comunicația conform implementării consultate; nu confirmă starea cuplului sau siguranța poziției.

## Cuplu — documentat, neexecutat

Distribuția consultată folosește `write_byte_data(0x15, 0x1A, 1)` pentru activare globală și valoarea 0 pentru dezactivare globală. Nu oferă în această interfață o activare individuală a cuplului sau o citire a stării cuplului.

Aceste comenzi **nu au fost trimise**. Activarea poate mobiliza toate articulațiile, iar dezactivarea poate lăsa brațul să cadă. Nu sunt folosite pentru recuperarea automată după incident.

## Dovezi și limite

I2C a răspuns; citirile tuturor celor șase servouri au furnizat valori în domeniu. Scrierea unei ținte mici la S1 nu a produs o deplasare confirmată. Prin urmare, protocolul de scriere nu este încă validat pe hardware-ul acestui montaj, iar cauza eșecului rămâne deschisă.

Nu extrapolăm un test de comunicație la un control mecanic funcțional. Nu trimitem resetări, schimbări de ID, configurări de offset sau comenzi de cuplu pentru a încerca recuperarea fără verificare fizică.
