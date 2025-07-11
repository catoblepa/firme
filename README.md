# Verifica Firme Digitali

**Verifica Firme Digitali** è una semplice applicazione GTK4 per GNOME che permette di verificare file firmati digitalmente in formato `.p7m` (CAdES) e visualizzare i dettagli delle firme digitali contenute.

## Funzionalità

- **Apertura e verifica di file .p7m**  
  Seleziona un file firmato digitalmente e verifica la validità della firma tramite OpenSSL.
- **Visualizzazione dettagli firmatari**  
  Mostra l’elenco dei firmatari e i dettagli delle firme digitali rilevate.
- **Estrazione del file originale**  
  Permette di aprire il file estratto dal pacchetto firmato.
- **Interfaccia moderna**  
  Basata su GTK4, con headerbar e layout responsive.

## Come si usa

1. **Avvia l’applicazione.**
2. **Clicca su “Apri”** e seleziona un file `.p7m`.
3. **Visualizza i dettagli delle firme** nella finestra principale.
4. **Apri il file estratto** cliccando su “Apri file estratto” (se la verifica ha successo).

## Requisiti

- Python 3
- GTK 4 e PyGObject
- OpenSSL installato nel sistema
- Modulo Python `signers.py` (deve contenere la funzione `analizza_busta`)

## Installazione tramite Flatpak

Per installare l’applicazione in ambiente isolato tramite Flatpak:

```bash
flatpak-builder --user --install --force-clean build-dir it.gnome.Firme.yaml
```

## Licenza

[GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html)
