"""Synthetic labelled corpus for redaction quality. All names, numbers and addresses are invented.

Each case: (language, text, [pii strings that must disappear], [clinical strings that must stay]).
"""

CASES: list[tuple[str, str, list[str], list[str]]] = [
    (
        "de",
        "Patientin Anna Schmidt, geb. 03.04.1961, klagt seit drei Tagen über Husten.",
        ["Anna Schmidt", "03.04.1961"],
        ["seit drei Tagen", "Husten"],
    ),
    (
        "de",
        "Herr Markus Weber stellt sich mit Brustschmerzen vor. Versichertennummer A123456789.",
        ["Markus Weber", "A123456789"],
        ["Brustschmerzen"],
    ),
    (
        "de",
        "Rückruf unter +49 170 1234567 vereinbart. Patient nimmt Metformin 500 mg zweimal täglich.",
        ["+49 170 1234567"],
        ["Metformin 500 mg", "zweimal täglich"],
    ),
    (
        "de",
        "Überweisung von Frau Dr. Petra Hoffmann aus Hamburg. Kontrolle in 2 Wochen.",
        ["Petra Hoffmann", "Hamburg"],
        ["Kontrolle in 2 Wochen"],
    ),
    (
        "de",
        "Erstattung auf IBAN DE89 3704 0044 0532 0130 00 beantragt. Keine bekannten Allergien.",
        ["DE89 3704 0044 0532 0130 00"],
        ["Keine bekannten Allergien"],
    ),
    (
        "de",
        "Wiedervorstellung am 15.11.2026. Patient Jonas Becker wohnt in Köln.",
        ["15.11.2026", "Jonas Becker", "Köln"],
        ["Wiedervorstellung"],
    ),
    (
        "de",
        "Kontakt per E-Mail lena.fischer@beispiel.de möglich. Blutdruck 150/95 mmHg.",
        ["lena.fischer@beispiel.de"],
        ["Blutdruck 150/95 mmHg"],
    ),
    (
        "de",
        "Geburtsdatum: 12.08.1975. Beschwerden seit 5 Tagen, Fieber bis 38,9 Grad.",
        ["12.08.1975"],
        ["seit 5 Tagen", "Fieber bis 38,9 Grad"],
    ),
    (
        "de",
        "Die Ehefrau, Sabine Krause, begleitet den Patienten. Er nimmt Ramipril 5 mg morgens.",
        ["Sabine Krause"],
        ["Ramipril 5 mg"],
    ),
    (
        "de",
        "Termin in der Praxis in Stuttgart, Tel. 0711 456789. Verdacht auf Bronchitis.",
        ["Stuttgart", "0711 456789"],
        ["Verdacht auf Bronchitis"],
    ),
    (
        "de",
        "Patient Felix Neumann, geboren am 7. März 1988, berichtet über Rückenschmerzen.",
        ["Felix Neumann", "7. März 1988"],
        ["Rückenschmerzen"],
    ),
    (
        "de",
        "KVNR: B987654321. Therapie mit Ibuprofen 400 mg bei Bedarf empfohlen.",
        ["B987654321"],
        ["Ibuprofen 400 mg"],
    ),
    (
        "en",
        "Mr. John Carter (DOB: 14 March 1975) reports cough for 3 days.",
        ["John Carter", "14 March 1975"],
        ["cough for 3 days"],
    ),
    (
        "en",
        "Patient Emily Johnson was seen in Boston on 2026-09-30 with chest pain.",
        ["Emily Johnson", "Boston", "2026-09-30"],
        ["chest pain"],
    ),
    (
        "en",
        "Call back at (555) 123-4567. Takes lisinopril 10 mg once daily.",
        ["(555) 123-4567"],
        ["lisinopril 10 mg", "once daily"],
    ),
    (
        "en",
        "Contact the patient at michael.brown@example.org if results change.",
        ["michael.brown@example.org"],
        ["results change"],
    ),
    (
        "en",
        "Referred by Dr. Susan Miller from Chicago. Follow-up in 2 weeks.",
        ["Susan Miller", "Chicago"],
        ["Follow-up in 2 weeks"],
    ),
    (
        "en",
        "Patient David Wilson, born on January 5, 1968, denies shortness of breath.",
        ["David Wilson", "January 5, 1968"],
        ["denies shortness of breath"],
    ),
    (
        "en",
        "Appointment on 03/14/2026. No known drug allergies. Plan: start amoxicillin 500 mg.",
        ["03/14/2026"],
        ["No known drug allergies", "amoxicillin 500 mg"],
    ),
    (
        "en",
        "Her husband Robert Taylor lives in Denver and brought her in. Pain 6/10.",
        ["Robert Taylor", "Denver"],
        ["Pain 6/10"],
    ),
    (
        "en",
        "Transfer papers list IBAN GB29 NWBK 6016 1331 9268 19 for billing.",
        ["GB29 NWBK 6016 1331 9268 19"],
        ["billing"],
    ),
    (
        "en",
        "Patient reports headache for two days and nausea. No fever.",
        [],
        ["headache for two days", "nausea", "No fever"],
    ),
    (
        "de",
        "Patient berichtet über Kopfschmerzen seit zwei Tagen und Übelkeit. Kein Fieber.",
        [],
        ["Kopfschmerzen seit zwei Tagen", "Übelkeit", "Kein Fieber"],
    ),
    (
        "en",
        "Jessica Lee, 29, phone 555-867-5309, presents with sore throat.",
        ["Jessica Lee", "555-867-5309"],
        ["sore throat"],
    ),
]
