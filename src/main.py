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

from signers import analizza_busta

class FirmeApp(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="com.github.catoblepa.firme",
            flags=Gio.ApplicationFlags.HANDLES_OPEN
        )
        
    def do_activate(self):
        win = FirmeWindow(self)
        win.present()

    def do_open(self, files, n_files, hint):
        file_path = files[0].get_path() if n_files > 0 else None
        win = FirmeWindow(self, file_path)
        win.present()

class FirmeWindow(Gtk.ApplicationWindow):
    def __init__(self, app, file_p7m=None):
        super().__init__(application=app)
        self.set_title("Verifica Firme Digitali")
        self.set_icon_name("org.gnome.Firme")
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
            self.verifica_firma(file_p7m)

    def aggiorna_ui(self):
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
                    self.pulisci_sezioni()
                    self.verifica_firma(file_p7m)
            except GLib.Error as e:
                self.file_verificato = False
                self.aggiorna_ui()

        file_dialog.open(self, None, on_file_selected)

    def pulisci_sezioni(self):
        self.label_info_file.set_markup('<span size="medium" color="#444444">Nessun file selezionato.</span>')
        self.elenco_firme_buffer.set_text("")

    def verifica_firma(self, file_p7m):
        self.pulisci_sezioni()
        self.btn_apri_estratto.set_sensitive(False)
        self.file_estratto = None
        self.file_verificato = False
        self.aggiorna_ui()

        # Crea una directory temporanea
        if self.tempdir:
            self.tempdir.cleanup()
        self.tempdir = tempfile.TemporaryDirectory()

        # Nome file estratto senza .p7m
        base_name = os.path.basename(file_p7m)
        if base_name.lower().endswith('.p7m'):
            base_name = base_name[:-4]
        file_output = os.path.join(self.tempdir.name, base_name)

        cmd = [
            "openssl", "smime", "-verify",
            "-in", file_p7m,
            "-inform", "DER",
            "-noverify",
            "-out", file_output
        ]

        self.label_info_file.set_markup(f'<span size="medium" color="#444444">{file_p7m}</span>')

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                self.btn_apri_estratto.set_sensitive(True)
                self.file_verificato = True
                self.aggiorna_ui()
                self.mostra_info_firma(file_p7m)
            else:
                self.label_info_file.set_markup(f'<span size="medium" color="#cc0000">Errore nella verifica della firma:\n{result.stderr}</span>')
        except Exception as e:
            self.label_info_file.set_markup(f'<span size="medium" color="#cc0000">Errore generico: {e}</span>')

    def mostra_info_firma(self, file_p7m):
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
        except Exception as e:
            self.elenco_firme_buffer.set_text(f"Errore info firma: {e}")

    def on_apri_estratto_clicked(self, widget):
        if self.file_estratto and os.path.exists(self.file_estratto):
            try:
                if sys.platform.startswith("linux"):
                    subprocess.Popen(["xdg-open", self.file_estratto])
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", self.file_estratto])
                elif sys.platform == "win32":
                    os.startfile(self.file_estratto)
            except Exception as e:
                self.label_info_file.set_markup(f'<span size="medium" color="#cc0000">Errore apertura file: {e}</span>')

def main():
    app = FirmeApp()
    app.run(sys.argv)

if __name__ == "__main__":
    main()
