/** Fictional example notes for trying the app. All names, dates and numbers are invented. */
export const SAMPLE_NOTES = [
  {
    label: 'German example',
    language: 'de' as const,
    title: 'Husten und Fieber (Beispiel)',
    body: `Patientin Anna Beispiel (geb. 03.04.1961) klagt seit drei Tagen über Husten und Fieber bis 38,9 Grad.
Sie nimmt Ramipril 5 mg morgens. Keine bekannten Allergien.
Beurteilung: Verdacht auf akute Bronchitis.
Plan: Hustensaft und Ruhe, ausreichend trinken.
Kontrolle in 2 Wochen. Rückruf unter +49 170 0000000.`,
  },
  {
    label: 'English example',
    language: 'en' as const,
    title: 'Cough and sore throat (example)',
    body: `Jordan Example (DOB: 14 March 1975) presents with cough for three days and a sore throat.
Takes lisinopril 10 mg once daily. Allergic to penicillin.
Assessment: viral upper respiratory infection suspected.
Plan: rest, fluids and paracetamol 500 mg as needed.
Follow-up in two weeks if symptoms persist.`,
  },
];
