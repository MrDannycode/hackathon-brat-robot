# Transfer mecanic direct

`transfer_direct.py` executa un singur transfer folosind approach/contact din
config, fara Enter intre miscari si fara trecere prin home/transit. Operatorul
a cerut explicit omiterea parcursului gol pentru prima mutare 2,2 -> 3,2.

```sh
cd ~/dofbot-concurs
python3 transfer_direct.py --source 2,2 --target 3,2
```

Inainte de pornire: cubul este la sursa, destinatia libera, clestele gol si
deschis, iar `calibrate.py` este inchis. Pozitia initiala trebuie sa corespunda
unui approach/contact salvat al uneia dintre cele doua celule. Din contact,
se retrage intai la approach-ul aceleiasi celule. Din alta pozitie, pornirea
este refuzata fara miscare. Pornirea cu gripper inchis este refuzata pentru
a nu elibera un cub suspendat. Se mentin verificarile de feedback, limitele
de unghi si oprirea la erori. Ctrl+C pastreaza cuplul si starea gripperului;
nu comanda revenire sau deschidere pe trasee nevalidate.

Validare: 36 de teste automate au trecut local; cele 6 teste dedicate au
trecut pe Pi. Simularea cu configuratia fizica salvata pe Pi a parcurs intreaga
secventa. Transferul real nu a fost inca executat/confirmat. Aceasta nu este
proba task1/task2: nu include verificare vizuala dupa plasare sau retry.
