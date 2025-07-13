#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 Davide Truffa <davide@catoblepa.org>

from asn1crypto import cms, x509
import sys

def estrai_certificati(signed_data):
    certs = []
    if 'certificates' in signed_data and signed_data['certificates'] is not None:
        for cert in signed_data['certificates']:
            if cert.name == 'certificate':
                certs.append(cert.chosen)
    return certs

def cerca_certificato_per_serial(cert_list, serial):
    for cert in cert_list:
        if cert.serial_number == serial:
            return cert
    return None

def estrai_nome_cognome(subject):
    cn = subject.native.get('common_name', '')
    gn = subject.native.get('given_name', '')
    sn = subject.native.get('surname', '')
    if gn and sn:
        return f"{gn} {sn}"
    return cn

def mostra_info_firma(signer, cert_list):
    """
    Estrae e ritorna informazioni del firmatario come dizionario.
    """
    info = {}
    sid = signer['sid']
    serial = None
    if sid.name == 'issuer_and_serial_number':
        serial = sid.chosen['serial_number'].native
    cert = cerca_certificato_per_serial(cert_list, serial)
    if cert:
        subject = cert.subject
        info['Identità'] = estrai_nome_cognome(subject)
        info['Identificativo'] = subject.native.get('serial_number', '') or subject.native.get('dn_qualifier', '')
        info['Scadenza'] = cert['tbs_certificate']['validity']['not_after'].native
        info['Verificato da'] = cert.issuer.human_friendly
    else:
        info['Errore'] = "Certificato non trovato per questa firma."
    if 'signed_attrs' in signer and signer['signed_attrs'] is not None:
        for attr in signer['signed_attrs']:
            if attr['type'].native == 'signing_time':
                info['Data firma'] = attr['values'].native[0]
    return info

def analizza_busta(data, livello=1):
    risultati = []
    try:
        content_info = cms.ContentInfo.load(data)
        if content_info['content_type'].native == 'signed_data':
            signed_data = content_info['content']
            cert_list = estrai_certificati(signed_data)
            signer_infos = signed_data['signer_infos']
            for idx, signer in enumerate(signer_infos, 1):
                info_firma = mostra_info_firma(signer, cert_list)
                info_firma['firmatario_idx'] = idx
                info_firma['livello_busta'] = livello
                risultati.append(info_firma)
            # Cerca dati annidati (content)
            encap_content = signed_data['encap_content_info']['content']
            if encap_content is not None:
                try:
                    risultati += analizza_busta(encap_content.native, livello + 1)
                except Exception:
                    pass
    except Exception:
        pass
    return risultati

def stampa_risultati(risultati):
    for info in risultati:
        print(f"\n--- Firmatario {info.get('firmatario_idx', '?')} (Livello busta {info.get('livello_busta', '?')}) ---")
        for chiave, valore in info.items():
            if chiave not in ('firmatario_idx', 'livello_busta'):
                print(f"{chiave}: {valore}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python estrai_firme.py file.p7m")
        sys.exit(1)
    else:
        with open(sys.argv[1], 'rb') as f:
            data = f.read()
        risultati = analizza_busta(data)
        stampa_risultati(risultati)
