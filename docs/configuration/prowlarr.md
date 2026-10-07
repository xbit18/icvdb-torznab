# Collegare Prowlarr

Collega Prowlarr dalla WebUI e aggiungi Violarr come indexer.

## I due URL hanno direzioni diverse

La configurazione usa due indirizzi distinti:

- **URL Prowlarr**: viene usato da **Violarr → Prowlarr**.
- **URL indexer**: viene salvato in Prowlarr e viene usato da **Prowlarr →
  Violarr**.

Non è quindi detto che i due servizi vedano `localhost` o gli stessi hostname
nello stesso modo.

### Entrambi in Docker sulla stessa rete

Usa normalmente:

```text
URL Prowlarr: http://prowlarr:9696
URL indexer:  http://icvdb-torznab:8000/api
```

### Violarr in Docker e Prowlarr come servizio Windows

Con Docker Desktop, usa normalmente:

```text
URL Prowlarr: http://host.docker.internal:9696
URL indexer:  http://localhost:8000/api
```

Il primo indirizzo permette al container Violarr di raggiungere il PC host. Il
secondo funziona perché Prowlarr gira sull'host e raggiunge la porta `8000`
pubblicata dal container Violarr.

Su Docker Engine Linux `host.docker.internal` potrebbe richiedere una
configurazione esplicita del gateway host.

## Procedura rapida

1. In Prowlarr copia la chiave da **Settings → General → Security → API Key**.
2. Apri **Prowlarr** nella WebUI di Violarr.
3. Inserisci l'**URL Prowlarr** adatto alla tua topologia.
4. Inserisci la **Chiave API**.
5. Inserisci l'**URL indexer visto da Prowlarr**.
6. Premi **Salva impostazioni Prowlarr**, quindi **Verifica connessione**.
7. Quando lo stato è **Connesso**, premi **Aggiungi Violarr a Prowlarr**.

## Diagnostica degli errori

Violarr distingue le fasi principali dell'integrazione.

- Se **Violarr non riesce a raggiungere Prowlarr**, controlla URL, porta,
  firewall e rete Docker.
- Se Prowlarr risponde con `401` o `403`, ricontrolla la API key.
- Se il test dell'indexer fallisce dopo che la connessione a Prowlarr è
  riuscita, il problema è normalmente nella direzione **Prowlarr → Violarr**:
  controlla l'URL indexer.
- Le risposte tecniche sicure restituite da Prowlarr vengono riportate nella
  console del browser per facilitare il debug.

Le API key e i traceback non vengono inclusi nei dettagli esposti alla WebUI.

## Risultato atteso

- La WebUI mostra **Connesso**.
- Prowlarr contiene un indexer chiamato **Violarr**.
- Ripetere l'aggiunta non crea duplicati.

## Modificare la chiave

- Una chiave già salvata resta attiva finché non scegli **Sostituisci chiave** o
  **Cancella la chiave API salvata** e salvi.
- Se il test fallisce, controlla URL, chiave e rete nella
  [risoluzione dei problemi](../troubleshooting).
