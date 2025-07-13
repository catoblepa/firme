#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 Davide Truffa <davide@catoblepa.org>

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gio
import subprocess
import os
import sys
import tempfile
import io
import contextlib
from pathlib import Path

from estrai_firme import analizza_busta

DEBUG = True  # Imposta a False per disabilitare i messaggi di debug

def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

class FirmeApp(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="com.github.catoblepa.firme",
            flags=Gio.ApplicationFlags.HANDLES_OPEN
        )
        debug_print("[DEBUG] Applicazione inizializzata")
        
    def do_activate(self):
        debug_print("[DEBUG] do_activate chiamato")
        win = FirmeWindow(self)
        win.present()

    def do_open(self, files, n_files, hint):
        debug_print(f"[DEBUG] do_open chiamato con {n_files} file")
        file_path = files[0].get_path() if n_files > 0 else None
        win = FirmeWindow(self, file_path)
        win.present()

class FirmeWindow(Gtk.ApplicationWindow):
    def __init__(self, app, file_p7m=None):
        super().__init__(application=app)
        debug_print("[DEBUG] Creazione finestra principale")
        self.set_title("Verifica Firme Digitali")
        self.set_icon_name("com.github.catoblepa.firme")
        self.file_estratto = None
        self.tempdir = None
        self.file_verificato = False

        headerbar = Gtk.HeaderBar()
        title_label = Gtk.Label()
        title_label.set_markup("<b>Firme</b>")
        headerbar.set_title_widget(title_label)

        btn_apri = Gtk.Button.new_with_label("Apri")
        btn_apri.connect("clicked", self.on_file_chooser_clicked)
        headerbar.pack_start(btn_apri)

        self.btn_apri_estratto = Gtk.Button.new_with_label("Apri file estratto")
        self.btn_apri_estratto.set_sensitive(False)
        self.btn_apri_estratto.connect("clicked", self.on_apri_estratto_clicked)
        headerbar.pack_end(self.btn_apri_estratto)

        self.set_titlebar(headerbar)
        self.set_default_size(700, 400)
        self.set_margin_top(10)
        self.set_margin_bottom(10)
        self.set_margin_start(10)
        self.set_margin_end(10)

        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_child(self.vbox)

        # SEZIONE 1: Titolo e info file
        self.label_info_title = Gtk.Label()
        self.label_info_title.set_markup('<span size="large" weight="bold" color="#336699">File verificato</span>')
        self.label_info_title.set_halign(Gtk.Align.START)
        self.label_info_title.set_margin_bottom(2)

        self.label_info_file = Gtk.Label()
        self.label_info_file.set_markup('<span size="medium" color="#444444">Nessun file selezionato.</span>')
        self.label_info_file.set_halign(Gtk.Align.START)
        self.label_info_file.set_selectable(True)

        # SEZIONE 2: Titolo firme
        self.label_firme_title = Gtk.Label()
        self.label_firme_title.set_markup('<span size="large" weight="bold" color="#336699">Firme digitali rilevate</span>')
        self.label_firme_title.set_halign(Gtk.Align.START)
        self.label_firme_title.set_margin_top(12)
        self.label_firme_title.set_margin_bottom(2)

        # SEZIONE 3: Elenco firme (scrollabile)
        self.elenco_firme_textview = Gtk.TextView()
        self.elenco_firme_textview.set_editable(False)
        self.elenco_firme_textview.set_wrap_mode(Gtk.WrapMode.WORD)
        self.elenco_firme_textview.set_hexpand(True)
        self.elenco_firme_textview.set_vexpand(True)
        self.elenco_firme_buffer = self.elenco_firme_textview.get_buffer()

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_min_content_height(100)
        self.scrolled.set_hexpand(True)
        self.scrolled.set_vexpand(True)
        self.scrolled.set_child(self.elenco_firme_textview)

        # Immagine e label iniziale
        self.image = Gtk.Image.new_from_icon_name("dialog-information")
        self.image.set_pixel_size(96)
        self.image.set_margin_top(24)

        self.label = Gtk.Label()
        self.label.set_margin_top(24)
        self.label.set_markup('<b>Seleziona un file .p7m da verificare</b>')
        self.label.set_justify(Gtk.Justification.CENTER)
        self.label.set_halign(Gtk.Align.CENTER)
        self.label.set_valign(Gtk.Align.CENTER)

        self.aggiorna_ui()

        if file_p7m:
            debug_print(f"[DEBUG] File passato all'avvio: {file_p7m}")
            self.verifica_firma(file_p7m)

    def aggiorna_ui(self):
        debug_print(f"[DEBUG] aggiorna_ui chiamato, file_verificato={self.file_verificato}")
        for child in list(self.vbox):
            self.vbox.remove(child)
        if not self.file_verificato:
            self.vbox.append(self.image)
            self.vbox.append(self.label)
        else:
            self.vbox.append(self.label_info_title)
            self.vbox.append(self.label_info_file)
            self.vbox.append(self.label_firme_title)
            self.vbox.append(self.scrolled)

    def on_file_chooser_clicked(self, widget):
        debug_print("[DEBUG] Pulsante 'Apri' cliccato, apro file dialog")
        file_dialog = Gtk.FileDialog()
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filter_p7m = Gtk.FileFilter()
        filter_p7m.set_name("File .p7m")
        filter_p7m.add_pattern("*.p7m")
        filters.append(filter_p7m)
        file_dialog.set_filters(filters)

        def on_file_selected(dialog, result):
            try:
                file = dialog.open_finish(result)
                if file:
                    file_p7m = file.get_path()
                    debug_print(f"[DEBUG] File selezionato: {file_p7m}")
                    self.pulisci_sezioni()
                    self.verifica_firma(file_p7m)
            except GLib.Error as e:
                debug_print(f"[DEBUG] Errore apertura file: {e}")
                self.file_verificato = False
                self.aggiorna_ui()

        file_dialog.open(self, None, on_file_selected)

    def pulisci_sezioni(self):
        debug_print("[DEBUG] pulisci_sezioni chiamato")
        self.label_info_file.set_markup('<span size="medium" color="#444444">Nessun file selezionato.</span>')
        self.elenco_firme_buffer.set_text("")

    def verifica_firma(self, file_p7m):
        debug_print(f"[DEBUG] verifica_firma chiamato con file: {file_p7m}")
        self.pulisci_sezioni()
        self.btn_apri_estratto.set_sensitive(False)
        self.file_estratto = None
        self.file_verificato = False
        self.aggiorna_ui()

        # Crea una directory temporanea
        if self.tempdir:
            debug_print("[DEBUG] Pulizia directory temporanea precedente")
            self.tempdir.cleanup()
            self.tempdir = None
        self.tempdir = tempfile.TemporaryDirectory()
        debug_print(f"[DEBUG] Creata directory temporanea: {self.tempdir.name}")

        # Nome file estratto senza .p7m
        base_path = Path(file_p7m)
        base_name = base_path.name
        while base_name.lower().endswith('.p7m'):
            base_name = base_name[:-4]
        base_name = base_name.strip()
        file_output = os.path.join(self.tempdir.name, base_name)
        debug_print(f"[DEBUG] File estratto sarà: {file_output}")

        cmd = [
            "openssl", "smime", "-verify",
            "-in", file_p7m,
            "-inform", "DER",
            "-noverify",
            "-out", file_output
        ]

        self.label_info_file.set_markup(f'<span size="medium" color="#444444">{file_p7m}</span>')

        try:
            debug_print(f"[DEBUG] Eseguo comando: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            debug_print(f"[DEBUG] Return code: {result.returncode}")
            debug_print(f"[DEBUG] stdout: {result.stdout}")
            debug_print(f"[DEBUG] stderr: {result.stderr}")
            if result.returncode == 0:
                self.file_estratto = file_output
                debug_print(f"[DEBUG] File estratto impostato a: {self.file_estratto}")
                self.btn_apri_estratto.set_sensitive(True)
                self.file_verificato = True
                self.aggiorna_ui()
                self.mostra_info_firma(file_p7m)
            else:
                self.label_info_file.set_markup(f'<span size="medium" color="#cc0000">Errore nella verifica della firma:\n{result.stderr}</span>')
                debug_print(f"[DEBUG] Errore openssl: {result.stderr}")
        except Exception as e:
            self.label_info_file.set_markup(f'<span size="medium" color="#cc0000">Errore generico: {e}</span>')
            debug_print(f"[DEBUG] Eccezione in verifica_firma: {e}")

    def mostra_info_firma(self, file_p7m):
        debug_print(f"[DEBUG] mostra_info_firma chiamato per file: {file_p7m}")
        try:
            with open(file_p7m, 'rb') as f:
                data = f.read()
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                analizza_busta(data)
            output = buf.getvalue()

            # SEZIONE 3: Elenco firme
            lines = output.splitlines()
            elenco = []
            in_firme = False
            for line in lines:
                if line.strip().startswith("--- Firmatario"):
                    in_firme = True
                if in_firme:
                    elenco.append(line)
            self.elenco_firme_buffer.set_text("\n".join(elenco))
            debug_print(f"[DEBUG] Informazioni firma mostrate per {file_p7m}")
        except Exception as e:
            self.elenco_firme_buffer.set_text(f"Errore info firma: {e}")
            debug_print(f"[DEBUG] Eccezione in mostra_info_firma: {e}")

    def on_apri_estratto_clicked(self, widget):
        debug_print(f"[DEBUG] Cliccato su 'Apri file estratto'. file_estratto = {self.file_estratto}")
        if self.file_estratto:
            debug_print(f"[DEBUG] Verifico esistenza file: {self.file_estratto}")
            if os.path.exists(self.file_estratto):
                debug_print("[DEBUG] File esiste, verifico tipo MIME")
                try:
                    content_type, uncertain = Gio.content_type_guess(self.file_estratto, None)
                    debug_print(f"[DEBUG] Tipo MIME del file estratto: {content_type}, incerto: {uncertain}")
                    if content_type and content_type != "application/octet-stream":
                        uri = GLib.filename_to_uri(self.file_estratto, None)
                        debug_print(f"[DEBUG] Apro il file con URI: {uri}")
                        launched = Gio.AppInfo.launch_default_for_uri(uri, None)
                        if not launched:
                            debug_print("[DEBUG] Launch default non riuscito, provo con launch_uris")
                            Gio.AppInfo.launch_uris([uri], None)
                        debug_print(f"[DEBUG] File aperto con successo: {uri}")
                    else:
                        debug_print("[DEBUG] Tipo MIME sconosciuto o generico, non posso aprire con app predefinita")
                        self.label_info_file.set_markup('<span size="medium" color="#cc0000">Tipo file non riconosciuto, impossibile aprire automaticamente.</span>')
                except Exception as e:
                    self.label_info_file.set_markup(f'<span size="medium" color="#cc0000">Errore apertura file: {e}</span>')
                    debug_print(f"[DEBUG] Eccezione in on_apri_estratto_clicked: {e}")
            else:
                debug_print(f"[DEBUG] File NON esiste: {self.file_estratto}")
                self.label_info_file.set_markup(f'<span size="medium" color="#cc0000">Il file estratto non esiste: {self.file_estratto}</span>')
        else:
            debug_print("[DEBUG] file_estratto non impostato.")
            self.label_info_file.set_markup('<span size="medium" color="#cc0000">Nessun file estratto da aprire.</span>')

    # def xdg_on_apri_estratto_clicked(self, widget):
    #     debug_print(f"[DEBUG] Cliccato su 'Apri file estratto'. file_estratto = {self.file_estratto}")
    #     if self.file_estratto:
    #         debug_print(f"[DEBUG] Verifico esistenza file: {self.file_estratto}")
    #         if os.path.exists(self.file_estratto):
    #             debug_print("[DEBUG] File esiste, verifico tipo MIME")
    #             try:
    #                 content_type, uncertain = Gio.content_type_guess(self.file_estratto, None)
    #                 debug_print(f"[DEBUG] Tipo MIME del file estratto: {content_type}, incerto: {uncertain}")
    #                 if content_type and content_type != "application/octet-stream":
    #                     # Provo ad aprire il file con xdg-open
    #                     try:
    #                         subprocess.run(["xdg-open", self.file_estratto], check=False)
    #                         debug_print(f"[DEBUG] Aperto con xdg-open: {self.file_estratto}")
    #                     except Exception as e:
    #                         debug_print(f"[DEBUG] Errore aprendo con xdg-open: {e}")
    #                         self.label_info_file.set_markup(f'<span size="medium" color="#cc0000">Errore aprendo con xdg-open: {e}</span>')
    #                 else:
    #                     debug_print("[DEBUG] Tipo MIME sconosciuto o generico, non posso aprire con app predefinita")
    #                     self.label_info_file.set_markup('<span size="medium" color="#cc0000">Tipo file non riconosciuto, impossibile aprire automaticamente.</span>')
    #             except Exception as e:
    #                 self.label_info_file.set_markup(f'<span size="medium" color="#cc0000">Errore apertura file: {e}</span>')
    #                 debug_print(f"[DEBUG] Eccezione in on_apri_estratto_clicked: {e}")
    #         else:
    #             debug_print(f"[DEBUG] File NON esiste: {self.file_estratto}")
    #             self.label_info_file.set_markup(f'<span size="medium" color="#cc0000">Il file estratto non esiste: {self.file_estratto}</span>')
    #     else:
    #         debug_print("[DEBUG] file_estratto non impostato.")
    #         self.label_info_file.set_markup('<span size="medium" color="#cc0000">Nessun file estratto da aprire.</span>')


def main():
    debug_print("[DEBUG] main() chiamato")
    app = FirmeApp()
    app.run(sys.argv)

if __name__ == "__main__":
    main()
