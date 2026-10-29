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
2. Așteptare configurată de 50 ms. Răspunsul brut zero este reîncercat de maximum trei ori, cu pauză de 50 ms între încercări, fără înlocuire cu o poziție presupusă.
3. `read_word_data(0x15, 0x30 + id)`.
4. Inversarea octeților rezultatului SMBus, apoi conversia inversă în grade și inversarea pentru S2–S4.

Valori brute în afara domeniului sunt erori. Nu se înlocuiesc cu un unghi implicit pentru mișcare reală.

## Verificarea stării unui servo

`write_byte_data(0x15, 0x38, id)`, pauză, `read_byte_data(0x15, 0x38)`.
Toate cele șase servouri au răspuns `0xDA`. Această verificare confirmă comunicația conform implementării consultate; nu confirmă starea cuplului sau siguranța poziției.

## Cuplu — activare explicită după recuperarea fizică

Distribuția consultată folosește `write_byte_data(0x15, 0x1A, 1)` pentru activare globală și valoarea 0 pentru dezactivare globală. Nu oferă în această interfață o activare individuală a cuplului sau o citire a stării cuplului.

După oprirea, repoziționarea și repornirea fizică de către operator, a fost autorizată explicit activarea globală. Toate unghiurile au fost citite de două ori pentru stabilitate, țintele au fost setate la unghiurile citite, apoi s-a așteptat durata pregătirii și s-a reverificat poziția. Abia apoi s-a trimis valoarea 1 la `0x1A`. Cuplul nu a fost dezactivat la ieșire. Secvența necesită explicit `--servo-test --enable-hold`.

Activarea poate mobiliza toate articulațiile, iar dezactivarea poate lăsa brațul să cadă. Nu există recuperare automată din poziția căzută. Prima citire imediată după pregătire a returnat `raw=0`; procedura s-a oprit înainte de activare. Au fost adăugate temporizarea pregătirii și reîncercările limitate înaintea încercării reușite.

## Dovezi și limite

I2C a răspuns, iar toate cele șase citiri au fost în domeniu. După activarea controlată a cuplului, testul S1 de la 93,03° la 95,03° a raportat 94,58°, iar revenirea la 93,03° a raportat 93,68°. Operatorul a confirmat rotația, revenirea și stabilitatea. Subsetul de scriere individuală și feedback este validat pentru acest test S1; nu extrapolăm la gripper sau trasee complete.

Nu extrapolăm un test de comunicație la un control mecanic complet funcțional. Nu trimitem resetări, schimbări de ID sau configurări de offset pentru recuperare. Cauza căderii raportate anterior rămâne necunoscută.
