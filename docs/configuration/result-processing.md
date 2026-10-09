# Elaborazione dei risultati

Scegli in **Elaborazione risultati** cosa mostrare a Prowlarr. Parti da **Senza
filtri** e cambia preset solo quando sai quali risultati vuoi favorire o
nascondere.

- **Senza filtri** — scelta iniziale; include tutti i risultati nell'ordine
  originale.
- **Italiano preferito** — porta in alto le versioni probabilmente italiane
  senza nascondere le altre.
- **Solo italiano** — mostra solo titoli con indicatori italiani espliciti.
- **Personalizzato** — applica le
  [regole personalizzate](../features/custom-filters).

Premi **Salva elaborazione risultati** e attendi il messaggio di conferma.

::: warning Selezione downstream

L'ordine dei risultati ICVDB non garantisce che Radarr o Sonarr scelgano il
primo elemento: applicano profili, punteggi e regole di disponibilità propri.

:::

::: danger I filtri rigidi nascondono risultati

**Solo italiano** e le regole **Escludi** rimuovono i risultati prima che
Prowlarr possa riceverli.

:::

Approfondisci la [priorità italiana](../features/italian-ranking) o i
[dettagli tecnici](../how-it-works/result-processing).

## Correzione lingua

L'opzione **Correggi il riconoscimento dei sottotitoli italiani** è disattivata
per impostazione predefinita. Se attivata, evita che le release con marcatori
espliciti come `SUB ITA`, `SUB.ITA`, `SUB-ITA` o `ITA.SUBBED` vengano
riconosciute come audio italiano soltanto per via dei sottotitoli.

La correzione è euristica: per i casi riconosciuti Violarr comunica
`language=English` nei metadati Torznab; **non verifica la traccia audio reale**.
Per prudenza non forza la lingua se nel titolo compaiono indicatori audio
italiani separati oppure `MULTI`/`DUAL`. I titoli e i magnet restano invariati.
Con l'opzione attiva, anche i preset italiani evitano di considerare italiani
i risultati corretti.
